#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streaming and Progress Monitoring - 流式输出和进度监控
使用stream_mode='updates'实时推送进度
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第14节
"""

import logging
import asyncio
from typing import Dict, Any, AsyncIterator, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ProgressEvent(Enum):
    """进度事件类型"""
    STARTED = "started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    PROGRESS_UPDATE = "progress_update"
    ERROR = "error"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressMonitor:
    """
    进度监控器
    
    职责:
    1. 监听workflow的流式输出
    2. 解析进度信息
    3. 格式化进度消息
    4. 推送到客户端
    """
    
    def __init__(self, callback: Callable = None):
        """
        初始化监控器
        
        参数:
            callback: 进度回调函数，接收(event_type, data)
        """
        self.callback = callback
        self.start_time = None
        self.current_step = None
        self.progress_history = []
    
    async def monitor_stream(self, graph, initial_state: Dict, config: Dict) -> AsyncIterator[Dict]:
        """
        监控workflow流式输出
        
        参数:
            graph: 编译后的StateGraph
            initial_state: 初始状态
            config: 配置（包含thread_id等）
        
        生成:
            进度事件字典
        """
        self.start_time = datetime.now()
        
        # 发送开始事件
        yield self._create_event(ProgressEvent.STARTED, {
            'task_id': initial_state.get('task_id'),
            'start_time': str(self.start_time)
        })
        
        try:
            # 使用stream_mode='updates'获取每个节点的输出
            async for chunk in graph.astream(initial_state, config=config, stream_mode='updates'):
                # chunk格式: {node_name: state_update}
                for node_name, state_update in chunk.items():
                    event = self._parse_chunk(node_name, state_update)
                    
                    if event:
                        yield event
                        
                        # 调用回调
                        if self.callback:
                            await self._call_callback(event)
            
            # 发送完成事件
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            
            yield self._create_event(ProgressEvent.COMPLETED, {
                'end_time': str(end_time),
                'duration_seconds': duration
            })
            
        except Exception as e:
            logger.error(f"流式监控失败: {e}")
            yield self._create_event(ProgressEvent.FAILED, {
                'error': str(e),
                'timestamp': str(datetime.now())
            })
    
    def _parse_chunk(self, node_name: str, state_update: Dict) -> Dict:
        """
        解析chunk，生成进度事件
        
        参数:
            node_name: 节点名称
            state_update: 状态更新
        
        返回:
            进度事件字典
        """
        current_step = state_update.get('current_step', node_name)
        progress = state_update.get('progress_percentage', 0)
        errors = state_update.get('errors', [])
        
        # 步骤开始
        if self.current_step != current_step:
            self.current_step = current_step
            return self._create_event(ProgressEvent.STEP_STARTED, {
                'step': current_step,
                'node': node_name,
                'timestamp': str(datetime.now())
            })
        
        # 进度更新
        if progress > 0:
            return self._create_event(ProgressEvent.PROGRESS_UPDATE, {
                'step': current_step,
                'progress': progress,
                'timestamp': str(datetime.now())
            })
        
        # 错误
        if errors:
            return self._create_event(ProgressEvent.ERROR, {
                'step': current_step,
                'errors': errors,
                'timestamp': str(datetime.now())
            })
        
        return None
    
    def _create_event(self, event_type: ProgressEvent, data: Dict) -> Dict:
        """创建进度事件"""
        event = {
            'event_type': event_type.value,
            'data': data,
            'timestamp': str(datetime.now())
        }
        
        self.progress_history.append(event)
        return event
    
    async def _call_callback(self, event: Dict):
        """调用回调函数"""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(event['event_type'], event['data'])
            else:
                self.callback(event['event_type'], event['data'])
        except Exception as e:
            logger.error(f"回调执行失败: {e}")


class StreamingWorkflowRunner:
    """
    流式工作流运行器
    
    提供便捷的流式执行接口
    """
    
    def __init__(self, graph, monitor: ProgressMonitor = None):
        """
        初始化运行器
        
        参数:
            graph: 编译后的StateGraph
            monitor: 进度监控器
        """
        self.graph = graph
        self.monitor = monitor or ProgressMonitor()
    
    async def run_with_progress(self, initial_state: Dict, config: Dict = None) -> Dict:
        """
        带进度监控的运行
        
        参数:
            initial_state: 初始状态
            config: 配置
        
        返回:
            最终状态
        """
        if not config:
            config = {"configurable": {"thread_id": initial_state.get('task_id', 'default')}}
        
        final_state = None
        
        async for event in self.monitor.monitor_stream(self.graph, initial_state, config):
            logger.info(f"进度事件: {event['event_type']} - {event['data']}")
            
            # 存储最终状态
            if event['event_type'] == ProgressEvent.COMPLETED.value:
                # 从history中提取最后的state
                pass
        
        # 获取最终状态
        final_state = await self.graph.ainvoke(initial_state, config=config)
        
        return final_state
    
    async def stream_events(self, initial_state: Dict, config: Dict = None) -> AsyncIterator[Dict]:
        """
        流式生成事件
        
        参数:
            initial_state: 初始状态
            config: 配置
        
        生成:
            进度事件
        """
        if not config:
            config = {"configurable": {"thread_id": initial_state.get('task_id', 'default')}}
        
        async for event in self.monitor.monitor_stream(self.graph, initial_state, config):
            yield event


# WebSocket进度推送器
class WebSocketProgressPusher:
    """
    WebSocket进度推送器
    
    用于通过WebSocket实时推送进度到前端
    """
    
    def __init__(self, websocket):
        """
        初始化推送器
        
        参数:
            websocket: WebSocket连接对象
        """
        self.websocket = websocket
    
    async def push_event(self, event_type: str, data: Dict):
        """
        推送事件到WebSocket
        
        参数:
            event_type: 事件类型
            data: 事件数据
        """
        try:
            message = {
                'type': 'progress_update',
                'event': event_type,
                'data': data,
                'timestamp': str(datetime.now())
            }
            
            await self.websocket.send_json(message)
            logger.debug(f"推送进度事件: {event_type}")
            
        except Exception as e:
            logger.error(f"WebSocket推送失败: {e}")


# SSE (Server-Sent Events) 进度推送器
class SSEProgressPusher:
    """
    SSE进度推送器
    
    用于通过Server-Sent Events推送进度
    """
    
    def __init__(self, queue: asyncio.Queue):
        """
        初始化推送器
        
        参数:
            queue: 事件队列
        """
        self.queue = queue
    
    async def push_event(self, event_type: str, data: Dict):
        """
        推送事件到SSE队列
        
        参数:
            event_type: 事件类型
            data: 事件数据
        """
        try:
            sse_data = f"event: {event_type}\ndata: {data}\n\n"
            await self.queue.put(sse_data)
            logger.debug(f"推送SSE事件: {event_type}")
            
        except Exception as e:
            logger.error(f"SSE推送失败: {e}")


# 使用示例
"""
# 1. 基础流式监控
from .streaming import ProgressMonitor, StreamingWorkflowRunner
from .workflow_new import get_production_workflow

workflow = get_production_workflow()
runner = StreamingWorkflowRunner(workflow.graph)

# 运行并监控进度
result = await runner.run_with_progress(initial_state)

# 2. 自定义回调
def progress_callback(event_type, data):
    print(f"{event_type}: {data}")

monitor = ProgressMonitor(callback=progress_callback)
runner = StreamingWorkflowRunner(workflow.graph, monitor=monitor)

# 3. WebSocket实时推送
from .streaming import WebSocketProgressPusher

async def handle_websocket(websocket):
    pusher = WebSocketProgressPusher(websocket)
    monitor = ProgressMonitor(callback=pusher.push_event)
    runner = StreamingWorkflowRunner(workflow.graph, monitor=monitor)
    
    result = await runner.run_with_progress(initial_state)

# 4. 流式事件迭代
async for event in runner.stream_events(initial_state):
    print(event)
"""
