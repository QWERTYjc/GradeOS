"""辅助批改 API 路由

提供深度作业分析和智能纠错功能，不依赖评分标准。

API 端点：
- POST /assistant/analyze - 单份作业分析
- POST /assistant/analyze/batch - 批量分析
- GET /assistant/report/{analysis_id} - 获取分析报告
- GET /assistant/status/{analysis_id} - 获取分析状态
- WebSocket /assistant/ws/{analysis_id} - 实时进度推送
"""

import uuid
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from starlette.websockets import WebSocketState
from pydantic import BaseModel, Field, field_validator

from src.orchestration.base import Orchestrator, RunStatus
from src.api.dependencies import get_orchestrator
from src.graphs.state import create_initial_assistant_state
from src.models.assistant_models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ReportResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["辅助批改"])


# ==================== WebSocket 连接管理 ====================


# 存储活跃的 WebSocket 连接
active_connections: Dict[str, List[WebSocket]] = {}


def _is_ws_connected(websocket: WebSocket) -> bool:
    """检查 WebSocket 是否连接"""
    return (
        websocket.client_state == WebSocketState.CONNECTED
        and websocket.application_state == WebSocketState.CONNECTED
    )


def _discard_connection(analysis_id: str, websocket: WebSocket) -> None:
    """移除 WebSocket 连接"""
    connections = active_connections.get(analysis_id)
    if not connections:
        return
    try:
        connections.remove(websocket)
    except ValueError:
        return
    if not connections:
        active_connections.pop(analysis_id, None)


async def _broadcast_message(analysis_id: str, message: Dict[str, Any]) -> None:
    """广播消息到所有连接的客户端"""
    connections = active_connections.get(analysis_id, [])
    if not connections:
        return

    disconnected = []
    for ws in connections:
        if not _is_ws_connected(ws):
            disconnected.append(ws)
            continue
        try:
            await ws.send_json(message)
        except Exception as e:
            logger.warning(f"[AssistantWS] 发送消息失败: {e}")
            disconnected.append(ws)

    # 清理断开的连接
    for ws in disconnected:
        _discard_connection(analysis_id, ws)


# ==================== API 端点 ====================


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_assignment(
    request: AnalyzeRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    单份作业深度分析

    功能：
    - 理解作业内容（知识点、解题思路）
    - 识别各类错误（计算、逻辑、概念、书写）
    - 生成改进建议
    - 深度分析评估
    - 生成分析报告

    不需要：
    - 评分标准（Rubric）
    - 标准答案

    Args:
        request: 分析请求
        orchestrator: LangGraph 编排器

    Returns:
        分析响应（包含 analysis_id）
    """
    try:
        # 生成分析 ID
        analysis_id = f"ana_{uuid.uuid4().hex[:12]}"

        logger.info(
            f"[AssistantAPI] 收到分析请求: analysis_id={analysis_id}, images={len(request.images)}"
        )

        # 创建初始状态
        initial_state = create_initial_assistant_state(
            analysis_id=analysis_id,
            images=request.images,
            submission_id=request.submission_id,
            student_id=request.student_id,
            subject=request.subject,
            context_info=request.context_info,
        )

        # 启动 LangGraph 工作流
        config = {
            "configurable": {
                "thread_id": analysis_id,
            },
            "recursion_limit": 10,
        }

        # 异步启动工作流（不等待完成）
        asyncio.create_task(
            _run_analysis_workflow(
                orchestrator=orchestrator,
                analysis_id=analysis_id,
                initial_state=initial_state,
                config=config,
            )
        )

        logger.info(f"[AssistantAPI] 分析任务已启动: analysis_id={analysis_id}")

        return AnalyzeResponse(
            analysis_id=analysis_id,
            status="processing",
            message="分析任务已启动，请通过 WebSocket 或轮询接口获取进度",
            estimated_time_seconds=60,  # 预估 1 分钟
        )

    except Exception as e:
        logger.error(f"[AssistantAPI] 启动分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动分析失败: {str(e)}")


@router.post("/analyze/batch", response_model=BatchAnalyzeResponse)
async def batch_analyze_assignments(
    request: BatchAnalyzeRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    批量作业分析

    Args:
        request: 批量分析请求
        orchestrator: LangGraph 编排器

    Returns:
        批量分析响应
    """
    try:
        batch_id = f"batch_ana_{uuid.uuid4().hex[:12]}"
        analysis_ids = []

        logger.info(
            f"[AssistantAPI] 收到批量分析请求: batch_id={batch_id}, count={len(request.analyses)}"
        )

        # 为每个任务创建独立的分析
        for idx, analyze_request in enumerate(request.analyses):
            analysis_id = f"ana_{batch_id}_{idx:03d}"
            analysis_ids.append(analysis_id)

            # 创建初始状态
            initial_state = create_initial_assistant_state(
                analysis_id=analysis_id,
                images=analyze_request.images,
                submission_id=analyze_request.submission_id,
                student_id=analyze_request.student_id,
                subject=analyze_request.subject,
                context_info=analyze_request.context_info,
            )

            # 异步启动工作流
            config = {
                "configurable": {
                    "thread_id": analysis_id,
                },
                "recursion_limit": 10,
            }

            asyncio.create_task(
                _run_analysis_workflow(
                    orchestrator=orchestrator,
                    analysis_id=analysis_id,
                    initial_state=initial_state,
                    config=config,
                )
            )

        logger.info(
            f"[AssistantAPI] 批量分析任务已启动: batch_id={batch_id}, count={len(analysis_ids)}"
        )

        return BatchAnalyzeResponse(
            batch_id=batch_id,
            total_count=len(analysis_ids),
            analysis_ids=analysis_ids,
            message=f"已启动 {len(analysis_ids)} 个分析任务",
        )

    except Exception as e:
        logger.error(f"[AssistantAPI] 批量分析启动失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量分析启动失败: {str(e)}")


@router.get("/report/{analysis_id}", response_model=ReportResponse)
async def get_analysis_report(
    analysis_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    获取分析报告

    Args:
        analysis_id: 分析任务 ID
        orchestrator: LangGraph 编排器

    Returns:
        分析报告
    """
    try:
        logger.info(f"[AssistantAPI] 获取报告: analysis_id={analysis_id}")

        # 从 Orchestrator 获取工作流状态
        config = {
            "configurable": {
                "thread_id": analysis_id,
            }
        }

        # TODO: 实现从检查点获取状态
        # state = await orchestrator.get_state("assistant_grading", config)

        # 占位实现
        return ReportResponse(
            analysis_id=analysis_id,
            status="processing",
            report=None,
            error_message=None,
            progress={
                "current_stage": "processing",
                "percentage": 50.0,
            },
        )

    except Exception as e:
        logger.error(f"[AssistantAPI] 获取报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取报告失败: {str(e)}")


@router.get("/status/{analysis_id}")
async def get_analysis_status(
    analysis_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    获取分析状态

    Args:
        analysis_id: 分析任务 ID
        orchestrator: LangGraph 编排器

    Returns:
        状态信息
    """
    try:
        logger.info(f"[AssistantAPI] 获取状态: analysis_id={analysis_id}")

        # TODO: 从检查点获取状态

        return {
            "analysis_id": analysis_id,
            "status": "processing",
            "current_stage": "understand",
            "percentage": 25.0,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"[AssistantAPI] 获取状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.websocket("/ws/{analysis_id}")
async def analysis_progress_ws(
    websocket: WebSocket,
    analysis_id: str,
):
    """
    WebSocket 实时进度推送

    连接后会持续接收分析进度更新，直到分析完成或连接断开。

    消息格式：
    ```json
    {
        "type": "progress|error|completed",
        "analysis_id": "ana_xxx",
        "current_stage": "understand|identify_errors|...",
        "percentage": 25.0,
        "timestamp": "2026-01-28T...",
        "data": {...}
    }
    ```

    Args:
        websocket: WebSocket 连接
        analysis_id: 分析任务 ID
    """
    await websocket.accept()

    # 注册连接
    if analysis_id not in active_connections:
        active_connections[analysis_id] = []
    active_connections[analysis_id].append(websocket)

    logger.info(f"[AssistantWS] WebSocket 已连接: analysis_id={analysis_id}")

    try:
        # 发送欢迎消息
        await websocket.send_json(
            {
                "type": "connected",
                "analysis_id": analysis_id,
                "message": "已连接到分析进度推送",
                "timestamp": datetime.now().isoformat(),
            }
        )

        # 保持连接，等待客户端消息或断开
        while True:
            try:
                # 接收客户端消息（心跳等）
                message = await websocket.receive_text()
                logger.debug(f"[AssistantWS] 收到客户端消息: {message}")

                # 响应 ping
                if message == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            except WebSocketDisconnect:
                logger.info(f"[AssistantWS] 客户端断开连接: analysis_id={analysis_id}")
                break

    except Exception as e:
        logger.error(f"[AssistantWS] WebSocket 错误: {e}", exc_info=True)

    finally:
        # 清理连接
        _discard_connection(analysis_id, websocket)
        logger.info(f"[AssistantWS] 连接已清理: analysis_id={analysis_id}")


# ==================== 内部辅助函数 ====================


async def _run_analysis_workflow(
    orchestrator: Orchestrator,
    analysis_id: str,
    initial_state: Dict[str, Any],
    config: Dict[str, Any],
):
    """
    运行分析工作流（内部函数）

    Args:
        orchestrator: LangGraph 编排器
        analysis_id: 分析任务 ID
        initial_state: 初始状态
        config: 配置
    """
    try:
        logger.info(f"[AssistantWorkflow] 开始执行工作流: analysis_id={analysis_id}")

        # 获取工作流图
        from src.graphs.assistant_grading import create_assistant_grading_graph

        graph = create_assistant_grading_graph(
            checkpointer=(
                orchestrator.checkpointer if hasattr(orchestrator, "checkpointer") else None
            )
        )

        # 流式执行工作流
        async for state_update in graph.astream(initial_state, config=config):
            logger.debug(f"[AssistantWorkflow] 状态更新: {state_update}")

            # 提取当前状态信息
            current_state = state_update
            if isinstance(state_update, dict) and len(state_update) == 1:
                # LangGraph 返回的格式可能是 {node_name: state}
                current_state = list(state_update.values())[0]

            # 广播进度更新
            await _broadcast_message(
                analysis_id,
                {
                    "type": "progress",
                    "analysis_id": analysis_id,
                    "current_stage": current_state.get("current_stage", "unknown"),
                    "percentage": current_state.get("percentage", 0.0),
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "understanding": current_state.get("understanding", {}),
                        "errors_count": len(current_state.get("errors", [])),
                        "suggestions_count": len(current_state.get("suggestions", [])),
                    },
                },
            )

        # 工作流完成
        logger.info(f"[AssistantWorkflow] 工作流完成: analysis_id={analysis_id}")

        # 发送完成消息
        await _broadcast_message(
            analysis_id,
            {
                "type": "completed",
                "analysis_id": analysis_id,
                "current_stage": "completed",
                "percentage": 100.0,
                "timestamp": datetime.now().isoformat(),
                "report_url": current_state.get("report_url"),
            },
        )

    except Exception as e:
        logger.error(f"[AssistantWorkflow] 工作流执行失败: {e}", exc_info=True)

        # 广播错误消息
        await _broadcast_message(
            analysis_id,
            {
                "type": "error",
                "analysis_id": analysis_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


# ==================== 健康检查 ====================


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "assistant_grading",
        "active_connections": sum(len(conns) for conns in active_connections.values()),
        "timestamp": datetime.now().isoformat(),
    }
