#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Push To Class System Agent - 班级系统推送器
调用班级系统API并保存到PostgreSQL
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第11节
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
import asyncio

from ..state import GradingState

logger = logging.getLogger(__name__)


class PushToClassSystemAgent:
    """
    班级系统推送器
    
    职责:
    1. 调用班级系统API推送评分数据
    2. 保存到PostgreSQL数据库
    3. 处理推送失败和重试
    4. 记录推送日志
    """
    
    def __init__(self, class_system_api_url: str, db_connection_string: str, 
                 max_retries: int = 3, timeout: int = 30):
        """
        初始化推送器
        
        参数:
            class_system_api_url: 班级系统API URL
            db_connection_string: PostgreSQL连接字符串
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）
        """
        self.api_url = class_system_api_url
        self.db_connection_string = db_connection_string
        self.max_retries = max_retries
        self.timeout = timeout
    
    async def __call__(self, state: GradingState) -> GradingState:
        """
        推送数据到班级系统
        
        参数:
            state: 包含export_payload的完整状态
        
        返回:
            更新后的状态
        """
        logger.info(f"开始推送数据到班级系统 - 任务ID: {state.get('task_id')}")
        
        try:
            export_payload = state.get('export_payload')
            if not export_payload:
                logger.error("export_payload为空，无法推送")
                state['errors'].append({'step': 'push_to_class', 'error': 'export_payload为空', 'timestamp': str(datetime.now())})
                return state
            
            # 推送到班级系统API
            api_success, api_response = await self._push_to_api(export_payload)
            
            # 保存到PostgreSQL
            db_success = await self._save_to_database(state, export_payload, api_response)
            
            # 更新状态
            if api_success and db_success:
                state['push_status'] = 'success'
                state['push_timestamp'] = str(datetime.now())
                state['current_step'] = '数据推送完成'
                state['progress_percentage'] = 100.0
                logger.info(f"数据推送成功 - 任务ID: {state.get('task_id')}")
            else:
                state['push_status'] = 'failed'
                state['errors'].append({
                    'step': 'push_to_class',
                    'error': f'API推送: {api_success}, DB保存: {db_success}',
                    'timestamp': str(datetime.now())
                })
            
            return state
            
        except Exception as e:
            logger.error(f"数据推送失败: {e}")
            state['push_status'] = 'error'
            state['errors'].append({'step': 'push_to_class', 'error': str(e), 'timestamp': str(datetime.now())})
            return state
    
    async def _push_to_api(self, payload: Dict) -> tuple:
        """
        推送数据到班级系统API
        
        返回:
            (成功标志, 响应数据)
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"API推送尝试 {attempt + 1}/{self.max_retries}")
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.api_url}/api/grading/submit",
                        json=payload,
                        headers={
                            'Content-Type': 'application/json',
                            'X-API-Version': payload.get('api_version', 'v1')
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info("API推送成功")
                        return True, response.json()
                    else:
                        logger.warning(f"API推送失败: HTTP {response.status_code}")
                        if attempt == self.max_retries - 1:
                            return False, {'error': f'HTTP {response.status_code}', 'detail': response.text}
                
            except httpx.TimeoutException:
                logger.warning(f"API请求超时 (尝试 {attempt + 1})")
                if attempt == self.max_retries - 1:
                    return False, {'error': 'Timeout'}
            
            except Exception as e:
                logger.error(f"API请求异常: {e}")
                if attempt == self.max_retries - 1:
                    return False, {'error': str(e)}
            
            # 等待后重试
            await asyncio.sleep(2 ** attempt)  # 指数退避
        
        return False, {'error': 'Max retries exceeded'}
    
    async def _save_to_database(self, state: GradingState, payload: Dict, api_response: Dict) -> bool:
        """
        保存到PostgreSQL数据库
        
        返回:
            成功标志
        """
        try:
            # 这里应该使用SQLAlchemy或其他ORM
            # 示例代码（需要根据实际数据库模型调整）
            logger.info("保存到PostgreSQL数据库")
            
            # TODO: 实现实际的数据库保存逻辑
            # 示例结构:
            # - 保存到grading_results表
            # - 保存到student_evaluations表
            # - 保存到annotations表
            # - 更新task_status表
            
            # 模拟数据库操作
            db_record = {
                'task_id': state.get('task_id'),
                'student_id': payload.get('student', {}).get('student_id'),
                'total_score': payload.get('student', {}).get('total_score'),
                'grade_level': payload.get('student', {}).get('grade_level'),
                'export_payload': payload,
                'api_response': api_response,
                'created_at': datetime.now(),
                'status': 'completed'
            }
            
            logger.info(f"数据库记录准备完成: {db_record.get('task_id')}")
            
            # 实际项目中应该执行:
            # async with get_db_session() as session:
            #     result = GradingResult(**db_record)
            #     session.add(result)
            #     await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"数据库保存失败: {e}")
            return False
    
    def _build_db_record(self, state: GradingState, payload: Dict, api_response: Dict) -> Dict:
        """构建数据库记录"""
        return {
            'task_id': state.get('task_id'),
            'student_id': payload.get('student', {}).get('student_id'),
            'student_name': payload.get('student', {}).get('student_name'),
            'assignment_id': payload.get('metadata', {}).get('assignment_id'),
            'class_id': payload.get('metadata', {}).get('class_id'),
            'teacher_id': payload.get('metadata', {}).get('teacher_id'),
            'total_score': payload.get('student', {}).get('total_score'),
            'max_score': payload.get('student', {}).get('max_score'),
            'percentage': payload.get('student', {}).get('percentage'),
            'grade_level': payload.get('student', {}).get('grade_level'),
            'mode': payload.get('mode'),
            'question_count': len(payload.get('questions', [])),
            'annotation_count': len(payload.get('annotations', [])),
            'export_payload': payload,
            'api_response': api_response,
            'push_timestamp': datetime.now(),
            'status': 'completed'
        }


class PushToClassSystemMock:
    """Mock版本的推送器（用于测试）"""
    
    async def __call__(self, state: GradingState) -> GradingState:
        """模拟推送"""
        logger.info(f"[MOCK] 模拟推送数据 - 任务ID: {state.get('task_id')}")
        
        # 模拟延迟
        await asyncio.sleep(0.5)
        
        state['push_status'] = 'success_mock'
        state['push_timestamp'] = str(datetime.now())
        state['current_step'] = '数据推送完成（模拟）'
        state['progress_percentage'] = 100.0
        
        logger.info("[MOCK] 推送成功")
        return state


def create_push_to_class_system_agent(class_system_api_url: str = None, 
                                      db_connection_string: str = None,
                                      use_mock: bool = False) -> Any:
    """
    创建PushToClassSystemAgent实例
    
    参数:
        class_system_api_url: 班级系统API URL
        db_connection_string: PostgreSQL连接字符串
        use_mock: 是否使用Mock版本
    
    返回:
        Agent实例
    """
    if use_mock:
        return PushToClassSystemMock()
    
    if not class_system_api_url or not db_connection_string:
        logger.warning("缺少配置，使用Mock模式")
        return PushToClassSystemMock()
    
    return PushToClassSystemAgent(
        class_system_api_url=class_system_api_url,
        db_connection_string=db_connection_string
    )
