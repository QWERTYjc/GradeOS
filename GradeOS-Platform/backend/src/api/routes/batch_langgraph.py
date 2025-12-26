"""批量提交 API 路由 - 使用 LangGraph Orchestrator

正确的架构：
1. 使用 LangGraph Orchestrator 启动批改流程
2. 通过 LangGraph 的流式 API 实时推送进度
3. 利用 PostgreSQL Checkpointer 实现持久化和断点恢复
"""

import uuid
import logging
import tempfile
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel, Field
import fitz
from PIL import Image
from io import BytesIO
import os

from src.models.enums import SubmissionStatus
from src.orchestration.base import Orchestrator
from src.api.dependencies import get_orchestrator


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["批量提交"])

# 存储活跃的 WebSocket 连接
active_connections: Dict[str, List[WebSocket]] = {}


class BatchSubmissionResponse(BaseModel):
    """批量提交响应"""
    batch_id: str = Field(..., description="批次 ID")
    status: SubmissionStatus = Field(..., description="状态")
    total_pages: int = Field(..., description="总页数")
    estimated_completion_time: int = Field(..., description="预计完成时间（秒）")


class BatchStatusResponse(BaseModel):
    """批量状态查询响应"""
    batch_id: str
    exam_id: str
    status: str
    total_students: int = Field(0, description="识别到的学生数")
    completed_students: int = Field(0, description="已完成批改的学生数")
    unidentified_pages: int = Field(0, description="未识别学生的页数")
    results: Optional[dict] = Field(None, description="批改结果")


def _pdf_to_images(pdf_path: str, dpi: int = 150) -> List[bytes]:
    """将 PDF 转换为图像列表"""
    pdf_doc = fitz.open(pdf_path)
    images = []
    
    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        images.append(img_bytes.getvalue())
    
    pdf_doc.close()
    return images


async def broadcast_progress(batch_id: str, message: dict):
    """向所有连接的 WebSocket 客户端广播进度"""
    if batch_id in active_connections:
        disconnected = []
        for ws in active_connections[batch_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket 发送失败: {e}")
                disconnected.append(ws)
        
        # 移除断开的连接
        for ws in disconnected:
            active_connections[batch_id].remove(ws)


@router.post("/submit", response_model=BatchSubmissionResponse)
async def submit_batch(
    exam_id: Optional[str] = Form(None, description="考试 ID"),
    rubrics: List[UploadFile] = File(..., description="评分标准 PDF"),
    files: List[UploadFile] = File(..., description="学生作答 PDF"),
    api_key: Optional[str] = Form(None, description="Gemini API Key"),
    auto_identify: bool = Form(True, description="是否自动识别学生身份"),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    批量提交试卷并进行批改（使用 LangGraph Orchestrator）
    
    正确的架构：
    1. 使用 LangGraph Orchestrator 启动 batch_grading Graph
    2. Graph 自动处理：边界检测 → 并行批改 → 聚合 → 持久化 → 通知
    3. 通过 WebSocket 实时推送 LangGraph 的执行进度
    
    Args:
        exam_id: 考试 ID
        rubrics: 评分标准 PDF 文件列表
        files: 学生作答 PDF 文件列表
        api_key: Gemini API Key
        auto_identify: 是否启用自动学生识别
        orchestrator: LangGraph Orchestrator（依赖注入）
        
    Returns:
        BatchSubmissionResponse: 批次信息
    """
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not exam_id:
        exam_id = str(uuid.uuid4())

    batch_id = str(uuid.uuid4())
    
    logger.info(
        f"收到批量提交（LangGraph）: "
        f"batch_id={batch_id}, "
        f"exam_id={exam_id}, "
        f"auto_identify={auto_identify}"
    )
    
    temp_dir = None
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # 保存上传的文件
        rubric_path = temp_path / "rubric.pdf"
        answer_path = temp_path / "answer.pdf"
        
        rubric_content = await rubrics[0].read()
        answer_content = await files[0].read()
        
        with open(rubric_path, "wb") as f:
            f.write(rubric_content)
        with open(answer_path, "wb") as f:
            f.write(answer_content)
        
        # 转换 PDF 为图像
        logger.info(f"转换 PDF 为图像: batch_id={batch_id}")
        loop = asyncio.get_event_loop()
        rubric_images = await loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 150)
        answer_images = await loop.run_in_executor(None, _pdf_to_images, str(answer_path), 150)
        
        total_pages = len(answer_images)
        
        logger.info(
            f"PDF 转换完成: "
            f"batch_id={batch_id}, "
            f"rubric_pages={len(rubric_images)}, "
            f"answer_pages={total_pages}"
        )
        
        # 🚀 使用 LangGraph Orchestrator 启动批改流程
        payload = {
            "batch_id": batch_id,
            "exam_id": exam_id,
            "pdf_path": str(answer_path),
            "rubric_images": rubric_images,
            "answer_images": answer_images,
            "api_key": api_key,
            "inputs": {
                "pdf_path": str(answer_path),
                "rubric": "rubric_content",  # TODO: 解析 rubric
                "auto_identify": auto_identify
            }
        }
        
        # 启动 LangGraph batch_grading Graph
        run_id = await orchestrator.start_run(
            graph_name="batch_grading",
            payload=payload,
            idempotency_key=batch_id
        )
        
        logger.info(
            f"LangGraph 批改流程已启动: "
            f"batch_id={batch_id}, "
            f"run_id={run_id}"
        )
        
        # 启动后台任务监听 LangGraph 进度并推送到 WebSocket
        asyncio.create_task(
            stream_langgraph_progress(
                batch_id=batch_id,
                run_id=run_id,
                orchestrator=orchestrator
            )
        )
        
        return BatchSubmissionResponse(
            batch_id=batch_id,
            status=SubmissionStatus.UPLOADED,
            total_pages=total_pages,
            estimated_completion_time=total_pages * 3  # 估算：每页 3 秒
        )
        
    except Exception as e:
        logger.error(f"批量提交失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量提交失败: {str(e)}")


async def stream_langgraph_progress(
    batch_id: str,
    run_id: str,
    orchestrator: Orchestrator
):
    """
    流式监听 LangGraph 执行进度并推送到 WebSocket
    
    这是实现实时进度推送的关键函数！
    
    Args:
        batch_id: 批次 ID
        run_id: LangGraph 运行 ID
        orchestrator: LangGraph Orchestrator
    """
    logger.info(f"开始流式监听 LangGraph 进度: batch_id={batch_id}, run_id={run_id}")
    
    try:
        # 🔥 使用 LangGraph 的流式 API
        async for event in orchestrator.stream_run(run_id):
            event_type = event.get("type")
            node_name = event.get("node")
            data = event.get("data", {})
            
            logger.debug(
                f"LangGraph 事件: "
                f"batch_id={batch_id}, "
                f"type={event_type}, "
                f"node={node_name}"
            )
            
            # 将 LangGraph 事件转换为前端 WebSocket 消息
            if event_type == "node_start":
                await broadcast_progress(batch_id, {
                    "type": "workflow_update",
                    "nodeId": _map_node_to_frontend(node_name),
                    "status": "running",
                    "message": f"正在执行 {node_name}..."
                })
            
            elif event_type == "node_end":
                await broadcast_progress(batch_id, {
                    "type": "workflow_update",
                    "nodeId": _map_node_to_frontend(node_name),
                    "status": "completed",
                    "message": f"{node_name} 完成"
                })
            
            elif event_type == "state_update":
                # 推送状态更新
                state = data.get("state", {})
                
                # 评分标准解析完成
                if state.get("rubric_parsed"):
                    await broadcast_progress(batch_id, {
                        "type": "rubric_parsed",
                        "totalQuestions": state.get("total_questions", 0),
                        "totalScore": state.get("total_score", 0)
                    })
                
                # 学生边界识别完成
                if state.get("student_boundaries"):
                    await broadcast_progress(batch_id, {
                        "type": "student_identified",
                        "boundaries": state["student_boundaries"]
                    })
                
                # 批次进度更新
                if state.get("progress"):
                    progress = state["progress"]
                    await broadcast_progress(batch_id, {
                        "type": "batch_progress",
                        "batchIndex": progress.get("current_batch", 0),
                        "totalBatches": progress.get("total_batches", 1),
                        "successCount": progress.get("success_count", 0),
                        "failureCount": progress.get("failure_count", 0)
                    })
            
            elif event_type == "error":
                await broadcast_progress(batch_id, {
                    "type": "workflow_error",
                    "message": data.get("error", "Unknown error")
                })
            
            elif event_type == "completed":
                # 工作流完成
                final_state = data.get("state", {})
                results = final_state.get("batch_results", [])
                
                await broadcast_progress(batch_id, {
                    "type": "workflow_completed",
                    "message": f"批改完成，共处理 {len(results)} 名学生",
                    "results": _format_results_for_frontend(results)
                })
        
        logger.info(f"LangGraph 进度流式传输完成: batch_id={batch_id}")
        
    except Exception as e:
        logger.error(
            f"流式传输失败: batch_id={batch_id}, error={str(e)}",
            exc_info=True
        )
        await broadcast_progress(batch_id, {
            "type": "workflow_error",
            "message": f"流式传输失败: {str(e)}"
        })


def _map_node_to_frontend(node_name: str) -> str:
    """将 LangGraph 节点名称映射到前端节点 ID"""
    mapping = {
        "detect_boundaries": "segment",
        "grade_student": "grading",
        "aggregate": "review",
        "batch_persist": "persist",
        "batch_notify": "export"
    }
    return mapping.get(node_name, node_name)


def _format_results_for_frontend(results: List[Dict]) -> List[Dict]:
    """格式化批改结果为前端格式"""
    formatted = []
    for r in results:
        formatted.append({
            "studentName": r.get("student_id", "Unknown"),
            "score": r.get("total_score", 0),
            "maxScore": r.get("max_total_score", 100),
            "questionResults": [
                {
                    "questionId": str(q.get("question_id", "")),
                    "score": q.get("score", 0),
                    "maxScore": q.get("max_score", 0),
                    "feedback": q.get("feedback", ""),
                    "confidence": q.get("confidence", 0)
                }
                for q in r.get("grading_results", [])
            ]
        })
    return formatted


@router.websocket("/ws/{batch_id}")
async def websocket_endpoint(websocket: WebSocket, batch_id: str):
    """
    WebSocket 端点，用于实时推送批改进度
    
    前端通过此端点接收 LangGraph 的实时执行进度
    """
    await websocket.accept()
    
    # 注册连接
    if batch_id not in active_connections:
        active_connections[batch_id] = []
    active_connections[batch_id].append(websocket)
    
    logger.info(f"WebSocket 连接建立: batch_id={batch_id}")
    
    try:
        # 保持连接，等待客户端消息或断开
        while True:
            data = await websocket.receive_text()
            logger.debug(f"收到 WebSocket 消息: batch_id={batch_id}, data={data}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket 连接断开: batch_id={batch_id}")
        active_connections[batch_id].remove(websocket)
        if not active_connections[batch_id]:
            del active_connections[batch_id]


@router.get("/status/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    查询批次状态（从 LangGraph Orchestrator）
    
    Args:
        batch_id: 批次 ID
        orchestrator: LangGraph Orchestrator
        
    Returns:
        BatchStatusResponse: 批次状态
    """
    try:
        # 从 LangGraph Orchestrator 查询状态
        run_info = await orchestrator.get_run_info(batch_id)
        
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        state = run_info.state or {}
        
        return BatchStatusResponse(
            batch_id=batch_id,
            exam_id=state.get("exam_id", ""),
            status=run_info.status.value,
            total_students=len(state.get("student_boundaries", [])),
            completed_students=len(state.get("completed_submissions", [])),
            unidentified_pages=0,
            results=state.get("batch_results")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询批次状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/results/{batch_id}")
async def get_batch_results(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    获取批次批改结果（从 LangGraph Orchestrator）
    
    Args:
        batch_id: 批次 ID
        orchestrator: LangGraph Orchestrator
        
    Returns:
        批改结果
    """
    try:
        run_info = await orchestrator.get_run_info(batch_id)
        
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        state = run_info.state or {}
        results = state.get("batch_results", [])
        
        return {
            "batch_id": batch_id,
            "status": run_info.status.value,
            "results": _format_results_for_frontend(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批改结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")
