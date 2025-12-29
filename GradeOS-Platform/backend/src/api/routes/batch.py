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
from datetime import datetime

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

# 存储每个批次的累积状态（用于最终结果）
batch_states: Dict[str, Dict[str, Any]] = {}


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
    import time
    start_time = time.time()
    
    logger.info(f"[_pdf_to_images] 开始: path={pdf_path}, dpi={dpi}")
    
    pdf_doc = fitz.open(pdf_path)
    page_count = len(pdf_doc)
    logger.info(f"[_pdf_to_images] PDF 页数: {page_count}")
    
    images = []
    
    for page_num in range(page_count):
        page = pdf_doc[page_num]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        images.append(img_bytes.getvalue())
        
        if (page_num + 1) % 10 == 0:
            logger.info(f"[_pdf_to_images] 进度: {page_num + 1}/{page_count} 页")
    
    pdf_doc.close()
    
    elapsed = time.time() - start_time
    logger.info(f"[_pdf_to_images] 完成: {page_count} 页, 耗时 {elapsed:.2f} 秒")
    
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
    """批量提交试卷并进行批改（使用 LangGraph Orchestrator）"""
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not exam_id:
        exam_id = str(uuid.uuid4())

    batch_id = str(uuid.uuid4())
    
    logger.info(f"收到批量提交（LangGraph）: batch_id={batch_id}, exam_id={exam_id}")
    
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
        
        # 转换 PDF 为图像（降低分辨率以提高性能）
        logger.info(f"开始转换 PDF 为图像: batch_id={batch_id}")
        logger.info(f"  评分标准文件大小: {len(rubric_content)} bytes")
        logger.info(f"  学生作答文件大小: {len(answer_content)} bytes")
        
        loop = asyncio.get_event_loop()
        
        # 转换评分标准（使用 72 DPI 以减少数据量）
        logger.info(f"  开始转换评分标准 PDF...")
        try:
            rubric_images = await asyncio.wait_for(
                loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 72),
                timeout=120.0  # 2分钟超时
            )
            logger.info(f"  ✓ 评分标准转换完成: {len(rubric_images)} 页")
        except asyncio.TimeoutError:
            logger.error(f"  ✗ 评分标准转换超时")
            raise HTTPException(status_code=504, detail="评分标准 PDF 转换超时")
        
        # 转换学生作答
        logger.info(f"  开始转换学生作答 PDF...")
        try:
            answer_images = await asyncio.wait_for(
                loop.run_in_executor(None, _pdf_to_images, str(answer_path), 72),
                timeout=180.0  # 3分钟超时
            )
            logger.info(f"  ✓ 学生作答转换完成: {len(answer_images)} 页")
        except asyncio.TimeoutError:
            logger.error(f"  ✗ 学生作答转换超时")
            raise HTTPException(status_code=504, detail="学生作答 PDF 转换超时")
        
        total_pages = len(answer_images)
        
        logger.info(f"PDF 转换全部完成: batch_id={batch_id}, rubric_pages={len(rubric_images)}, answer_pages={total_pages}")
        
        # 初始化批次状态
        batch_states[batch_id] = {
            "total_pages": total_pages,
            "rubric_pages": len(rubric_images),
            "grading_results": [],
            "parsed_rubric": None,
            "student_results": []
        }
        
        # 使用 LangGraph Orchestrator 启动批改流程
        logger.info(f"准备启动 LangGraph 批改流程: batch_id={batch_id}")
        logger.info(f"  Payload 包含: rubric_images={len(rubric_images)}页, answer_images={len(answer_images)}页")
        
        payload = {
            "batch_id": batch_id,
            "exam_id": exam_id,
            "pdf_path": str(answer_path),
            "rubric_images": rubric_images,
            "answer_images": answer_images,
            "api_key": api_key,
            "inputs": {
                "pdf_path": str(answer_path),
                "rubric": "",
                "auto_identify": auto_identify
            }
        }
        
        logger.info(f"调用 orchestrator.start_run...")
        run_id = await orchestrator.start_run(
            graph_name="batch_grading",
            payload=payload,
            idempotency_key=batch_id
        )
        
        logger.info(f"✓ LangGraph 批改流程已启动: batch_id={batch_id}, run_id={run_id}")
        
        # 启动后台任务监听进度（原有的事件流方式）
        logger.info(f"准备启动后台任务: stream_langgraph_progress")
        task = asyncio.create_task(
            stream_langgraph_progress(
                batch_id=batch_id,
                run_id=run_id,
                orchestrator=orchestrator,
                total_pages=total_pages
            )
        )
        logger.info(f"后台任务已创建: task={task}")
        
        # 启动备用的轮询保存任务（确保结果不丢失）
        asyncio.create_task(
            poll_and_save_results(
                batch_id=batch_id,
                run_id=run_id,
                orchestrator=orchestrator
            )
        )
        
        return BatchSubmissionResponse(
            batch_id=batch_id,
            status=SubmissionStatus.UPLOADED,
            total_pages=total_pages,
            estimated_completion_time=total_pages * 3
        )
        
    except Exception as e:
        logger.error(f"批量提交失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量提交失败: {str(e)}")


async def poll_and_save_results(
    batch_id: str,
    run_id: str,
    orchestrator: Orchestrator,
    poll_interval: float = 5.0,
    max_wait_time: float = 1800.0  # 30分钟超时
):
    """
    轮询并保存批改结果（备用方案）
    
    这个函数会定期检查工作流程状态，一旦完成就从 orchestrator 获取最终输出并保存到 batch_states。
    这是一个更可靠的方式，不依赖事件流。
    
    Args:
        batch_id: 批次 ID
        run_id: 运行 ID
        orchestrator: 编排器
        poll_interval: 轮询间隔（秒）
        max_wait_time: 最大等待时间（秒）
    """
    print(f"[poll_and_save_results] 开始轮询: batch_id={batch_id}, run_id={run_id}")
    logger.info(f"[poll_and_save_results] 开始轮询: batch_id={batch_id}, run_id={run_id}")
    
    start_time = asyncio.get_event_loop().time()
    
    while True:
        try:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            # 超时检查
            if elapsed > max_wait_time:
                print(f"[poll_and_save_results] 超时: batch_id={batch_id}, elapsed={elapsed:.1f}s")
                logger.warning(f"[poll_and_save_results] 超时: batch_id={batch_id}, elapsed={elapsed:.1f}s")
                break
            
            # 获取状态
            status = await orchestrator.get_status(run_id)
            current_status = status.status.value
            
            print(f"[poll_and_save_results] 状态: {current_status}, elapsed={elapsed:.1f}s")
            
            # 检查是否完成
            if current_status == "completed":
                print(f"[poll_and_save_results] 工作流程完成，获取最终输出...")
                logger.info(f"[poll_and_save_results] 工作流程完成: batch_id={batch_id}")
                
                # 获取最终输出
                final_output = await orchestrator.get_final_output(run_id)
                
                if final_output:
                    print(f"[poll_and_save_results] 获取到最终输出: keys={list(final_output.keys())}")
                    logger.info(f"[poll_and_save_results] 获取到最终输出: batch_id={batch_id}, keys={list(final_output.keys())}")
                    
                    # 保存到 batch_states
                    batch_states[batch_id] = {
                        **batch_states.get(batch_id, {}),
                        "status": "completed",
                        "final_state": final_output,
                        "grading_results": final_output.get("grading_results", []),
                        "student_results": final_output.get("student_results", []),
                        "parsed_rubric": final_output.get("parsed_rubric"),
                        "export_data": final_output.get("export_data"),
                        "completed_at": datetime.now().isoformat()
                    }
                    
                    print(f"[poll_and_save_results] 结果已保存到 batch_states: batch_id={batch_id}")
                    logger.info(f"[poll_and_save_results] 结果已保存: batch_id={batch_id}")
                else:
                    print(f"[poll_and_save_results] 警告：未获取到最终输出")
                    logger.warning(f"[poll_and_save_results] 未获取到最终输出: batch_id={batch_id}")
                
                break
                
            elif current_status in ["failed", "cancelled"]:
                print(f"[poll_and_save_results] 工作流程失败或取消: {current_status}")
                logger.warning(f"[poll_and_save_results] 工作流程 {current_status}: batch_id={batch_id}")
                
                batch_states[batch_id] = {
                    **batch_states.get(batch_id, {}),
                    "status": current_status,
                    "error": status.error,
                    "completed_at": datetime.now().isoformat()
                }
                break
            
            # 等待下一次轮询
            await asyncio.sleep(poll_interval)
            
        except Exception as e:
            print(f"[poll_and_save_results] 轮询异常: {e}")
            logger.error(f"[poll_and_save_results] 轮询异常: batch_id={batch_id}, error={e}")
            await asyncio.sleep(poll_interval)
    
    print(f"[poll_and_save_results] 轮询结束: batch_id={batch_id}")
    logger.info(f"[poll_and_save_results] 轮询结束: batch_id={batch_id}")


async def stream_langgraph_progress(
    batch_id: str,
    run_id: str,
    orchestrator: Orchestrator,
    total_pages: int
):
    """
    流式监听 LangGraph 执行进度并推送到 WebSocket
    
    关键改进：
    1. 累积所有节点的输出状态
    2. 发送详细的节点输出到前端
    3. 正确处理批次进度
    """
    logger.info(f"开始流式监听 LangGraph 进度: batch_id={batch_id}, run_id={run_id}")
    
    # 累积状态
    accumulated_state = batch_states.get(batch_id, {})
    grading_results = []
    completed_batches = set()
    
    try:
        async for event in orchestrator.stream_run(run_id):
            event_type = event.get("type")
            node_name = event.get("node")
            data = event.get("data", {})
            
            logger.info(f"[stream_langgraph_progress] 事件: batch_id={batch_id}, type={event_type}, node={node_name}")
            
            # ========== 节点开始 ==========
            if event_type == "node_start":
                frontend_node = _map_node_to_frontend(node_name)
                await broadcast_progress(batch_id, {
                    "type": "workflow_update",
                    "nodeId": frontend_node,
                    "status": "running",
                    "message": f"正在执行 {_get_node_label(node_name)}..."
                })
            
            # ========== 节点结束 ==========
            elif event_type == "node_end":
                frontend_node = _map_node_to_frontend(node_name)
                output = data.get("output", {})
                
                # 发送节点完成状态
                await broadcast_progress(batch_id, {
                    "type": "workflow_update",
                    "nodeId": frontend_node,
                    "status": "completed",
                    "message": f"{_get_node_label(node_name)} 完成"
                })
                
                # 根据节点类型发送详细输出
                await _handle_node_output(batch_id, node_name, output, accumulated_state)
            
            # ========== 状态更新 ==========
            elif event_type == "state_update":
                state = data.get("state", {})
                
                # 更新累积状态
                for key, value in state.items():
                    if key == "grading_results" and isinstance(value, list):
                        # 批改结果：追加并去重
                        for r in value:
                            page_idx = r.get("page_index")
                            if page_idx is not None:
                                # 检查是否已存在
                                existing = next((x for x in grading_results if x.get("page_index") == page_idx), None)
                                if not existing:
                                    grading_results.append(r)
                                    
                                    # 发送单页批改完成消息
                                    await broadcast_progress(batch_id, {
                                        "type": "page_graded",
                                        "pageIndex": page_idx,
                                        "score": r.get("score", 0),
                                        "maxScore": r.get("max_score", 10),
                                        "feedback": r.get("feedback", ""),
                                        "questionNumbers": r.get("question_numbers", []),
                                        "questionDetails": r.get("question_details", [])
                                    })
                        
                        # 更新批改进度
                        completed_count = len(grading_results)
                        await broadcast_progress(batch_id, {
                            "type": "grading_progress",
                            "completedPages": completed_count,
                            "totalPages": total_pages,
                            "percentage": round(completed_count / total_pages * 100, 1) if total_pages > 0 else 0
                        })
                    else:
                        accumulated_state[key] = value
                
                # 处理特定状态更新
                if "parsed_rubric" in state and state["parsed_rubric"]:
                    await _send_rubric_parsed(batch_id, state["parsed_rubric"])
                
                if "student_results" in state and state["student_results"]:
                    accumulated_state["student_results"] = state["student_results"]
            
            # ========== 错误 ==========
            elif event_type == "error":
                await broadcast_progress(batch_id, {
                    "type": "workflow_error",
                    "message": data.get("error", "Unknown error")
                })
            
            # ========== 完成 ==========
            elif event_type == "completed":
                final_state = data.get("state", {})
                
                # 合并最终状态
                if final_state:
                    for key, value in final_state.items():
                        if key not in accumulated_state or value:
                            accumulated_state[key] = value
                
                # 确保 grading_results 被包含
                if grading_results:
                    accumulated_state["grading_results"] = grading_results
                
                # 获取最终结果
                student_results = accumulated_state.get("student_results", [])
                export_data = accumulated_state.get("export_data", {})
                
                if export_data and export_data.get("students"):
                    student_results = export_data["students"]
                
                # 计算总分
                total_score = 0
                max_total_score = 0
                for r in grading_results:
                    if r.get("status") == "completed":
                        total_score += r.get("score", 0)
                        max_total_score += r.get("max_score", 0)
                
                logger.info(
                    f"工作流完成: batch_id={batch_id}, "
                    f"学生数={len(student_results)}, "
                    f"总分={total_score}/{max_total_score}"
                )
                
                # 保存最终状态到 batch_states（用于后续查询）
                logger.info(f"[stream_langgraph_progress] 保存最终状态到 batch_states: batch_id={batch_id}")
                logger.info(f"  accumulated_state keys: {list(accumulated_state.keys())}")
                logger.info(f"  grading_results count: {len(grading_results)}")
                logger.info(f"  student_results count: {len(student_results)}")
                
                batch_states[batch_id] = {
                    **batch_states.get(batch_id, {}),
                    "status": "completed",
                    "final_state": accumulated_state,
                    "grading_results": grading_results,
                    "student_results": student_results,
                    "export_data": export_data,
                    "total_score": total_score,
                    "max_total_score": max_total_score,
                    "completed_at": datetime.now().isoformat()
                }
                
                logger.info(f"[stream_langgraph_progress] batch_states 已更新，当前 keys: {list(batch_states[batch_id].keys())}")
                
                # 发送完成消息
                await broadcast_progress(batch_id, {
                    "type": "workflow_completed",
                    "message": f"批改完成",
                    "summary": {
                        "totalPages": total_pages,
                        "gradedPages": len(grading_results),
                        "totalScore": total_score,
                        "maxTotalScore": max_total_score,
                        "studentCount": len(student_results)
                    },
                    "results": _format_results_for_frontend(student_results, grading_results),
                    "gradingDetails": _format_grading_details(grading_results)
                })
        
        logger.info(f"LangGraph 进度流式传输完成: batch_id={batch_id}")
        
    except Exception as e:
        logger.error(f"流式传输失败: batch_id={batch_id}, error={str(e)}", exc_info=True)
        await broadcast_progress(batch_id, {
            "type": "workflow_error",
            "message": f"流式传输失败: {str(e)}"
        })
    finally:
        # 保留批次状态以供后续查询
        # 注意：在生产环境中，应该将结果持久化到数据库，然后清理内存
        logger.info(f"保留批次状态以供查询: batch_id={batch_id}")
        # batch_states.pop(batch_id, None)  # 暂时不删除，以便查询结果


async def _handle_node_output(
    batch_id: str,
    node_name: str,
    output: Dict[str, Any],
    accumulated_state: Dict[str, Any]
):
    """处理节点输出并发送到前端"""
    
    if node_name == "rubric_parse":
        # 评分标准解析完成
        parsed_rubric = output.get("parsed_rubric")
        if parsed_rubric:
            accumulated_state["parsed_rubric"] = parsed_rubric
            await _send_rubric_parsed(batch_id, parsed_rubric)
    
    elif node_name == "grade_batch":
        # 批次批改完成
        batch_results = output.get("grading_results", [])
        if batch_results:
            # 发送批次完成消息
            batch_scores = [r.get("score", 0) for r in batch_results if r.get("status") == "completed"]
            await broadcast_progress(batch_id, {
                "type": "batch_completed",
                "batchSize": len(batch_results),
                "successCount": len(batch_scores),
                "totalScore": sum(batch_scores),
                "pages": [r.get("page_index") for r in batch_results]
            })
    
    elif node_name in ("index", "segment"):
        # 索引完成（或兼容旧的学生分割节点）
        boundaries = output.get("student_boundaries") or []
        if not boundaries:
            indexed_students = output.get("indexed_students") or []
            boundaries = [
                {
                    "student_key": s.get("student_key", ""),
                    "start_page": s.get("start_page", 0),
                    "end_page": s.get("end_page", 0),
                    "confidence": s.get("confidence", 0),
                    "needs_confirmation": s.get("needs_confirmation", False),
                }
                for s in indexed_students
            ]
        if not boundaries:
            student_results = output.get("student_results") or []
            boundaries = [
                {
                    "student_key": s.get("student_key", ""),
                    "start_page": s.get("start_page", 0),
                    "end_page": s.get("end_page", 0),
                    "confidence": s.get("confidence", 0),
                    "needs_confirmation": s.get("needs_confirmation", False),
                }
                for s in student_results
            ]

        if boundaries:
            accumulated_state["student_boundaries"] = boundaries
            await broadcast_progress(batch_id, {
                "type": "students_identified",
                "studentCount": len(boundaries),
                "students": [
                    {
                        "studentKey": b.get("student_key", "Unknown"),
                        "startPage": b.get("start_page", 0),
                        "endPage": b.get("end_page", 0),
                        "confidence": b.get("confidence", 0),
                        "needsConfirmation": b.get("needs_confirmation", False),
                    }
                    for b in boundaries
                ]
            })

        if node_name == "segment":
            student_results = output.get("student_results", [])
            if student_results:
                accumulated_state["student_results"] = student_results

    elif node_name == "index_merge":
        # 索引聚合完成
        student_results = output.get("student_results", [])
        if student_results:
            accumulated_state["student_results"] = student_results
    
    elif node_name == "review":
        # 审核完成
        review_summary = output.get("review_summary", {})
        if review_summary:
            await broadcast_progress(batch_id, {
                "type": "review_completed",
                "summary": review_summary
            })
    
    elif node_name == "export":
        # 导出完成
        export_data = output.get("export_data", {})
        if export_data:
            accumulated_state["export_data"] = export_data


async def _send_rubric_parsed(batch_id: str, parsed_rubric: Dict[str, Any]):
    """发送评分标准解析结果"""
    questions = parsed_rubric.get("questions", [])
    
    await broadcast_progress(batch_id, {
        "type": "rubric_parsed",
        "totalQuestions": parsed_rubric.get("total_questions", len(questions)),
        "totalScore": parsed_rubric.get("total_score", 0),
        "questions": [
            {
                "id": q.get("id", ""),
                "maxScore": q.get("max_score", 0),
                "criteria": q.get("criteria", []),
                "answerSummary": q.get("answer_summary", "")
            }
            for q in questions
        ]
    })


def _format_results_for_frontend(
    student_results: List[Dict[str, Any]],
    grading_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """格式化结果供前端显示
    
    Args:
        student_results: 学生结果列表
        grading_results: 批改结果列表
        
    Returns:
        前端格式的结果列表
    """
    if student_results:
        # 有学生分割结果
        return [
            {
                "studentName": s.get("student_key", "未知学生"),
                "score": s.get("total_score", 0),
                "maxScore": s.get("max_total_score", 0),
                "percentage": round(
                    s.get("total_score", 0) / s.get("max_total_score", 1) * 100, 1
                ) if s.get("max_total_score", 0) > 0 else 0,
                "startPage": s.get("start_page", 0),
                "endPage": s.get("end_page", 0),
                "confidence": s.get("confidence", 0),
                "needsConfirmation": s.get("needs_confirmation", False),
                "questionResults": [
                    {
                        "questionId": r.get("question_id", f"Q{r.get('page_index', 0)}"),
                        "pageIndex": r.get("page_index", 0),
                        "score": r.get("score", 0),
                        "maxScore": r.get("max_score", 0),
                        "feedback": r.get("feedback", ""),
                        "questionNumbers": r.get("question_numbers", []),
                        "questionDetails": r.get("question_details", [])
                    }
                    for r in s.get("page_results", [])
                    if r.get("status") == "completed"
                ]
            }
            for s in student_results
        ]
    else:
        # 没有学生分割，按页面返回
        total_score = sum(r.get("score", 0) for r in grading_results if r.get("status") == "completed")
        max_score = sum(r.get("max_score", 0) for r in grading_results if r.get("status") == "completed")
        
        return [{
            "studentName": "全部页面",
            "score": total_score,
            "maxScore": max_score,
            "percentage": round(total_score / max_score * 100, 1) if max_score > 0 else 0,
            "questionResults": [
                {
                    "questionId": r.get("question_id", f"Q{r.get('page_index', 0)}"),
                    "pageIndex": r.get("page_index", 0),
                    "score": r.get("score", 0),
                    "maxScore": r.get("max_score", 0),
                    "feedback": r.get("feedback", ""),
                    "questionNumbers": r.get("question_numbers", []),
                    "questionDetails": r.get("question_details", [])
                }
                for r in grading_results
                if r.get("status") == "completed"
            ]
        }]


def _format_grading_details(grading_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """格式化详细批改结果
    
    Args:
        grading_results: 批改结果列表
        
    Returns:
        详细批改结果列表
    """
    return [
        {
            "pageIndex": r.get("page_index", 0),
            "status": r.get("status", "unknown"),
            "score": r.get("score", 0),
            "maxScore": r.get("max_score", 0),
            "confidence": r.get("confidence", 0),
            "feedback": r.get("feedback", ""),
            "questionNumbers": r.get("question_numbers", []),
            "questionDetails": r.get("question_details", []),
            "pageSummary": r.get("page_summary", ""),
            "studentInfo": r.get("student_info"),
            "error": r.get("error") if r.get("status") == "failed" else None
        }
        for r in sorted(grading_results, key=lambda x: x.get("page_index", 0))
    ]


def _get_node_label(node_name: str) -> str:
    """获取节点的中文标签
    
    Args:
        node_name: 节点名称
        
    Returns:
        中文标签
    """
    labels = {
        "intake": "接收文件",
        "preprocess": "图像预处理",
        "index": "索引层",
        "rubric_parse": "解析评分标准",
        "grade_batch": "分批并行批改",
        "grading_fanout_router": "批改任务分发",
        "cross_page_merge": "跨页题目合并",
        "index_merge": "索引聚合",
        "segment": "索引聚合",
        "review": "结果审核",
        "export": "导出结果"
    }
    return labels.get(node_name, node_name)


def _map_node_to_frontend(node_name: str) -> str:
    """将后端节点名称映射到前端节点 ID
    
    Args:
        node_name: 后端节点名称
        
    Returns:
        前端节点 ID
    """
    mapping = {
        "intake": "intake",
        "preprocess": "preprocess",
        "index": "index",
        "rubric_parse": "rubric_parse",
        "grade_batch": "grade_batch",
        "grading_fanout_router": "grade_batch",  # 扇出路由也映射到 grade_batch
        "cross_page_merge": "cross_page_merge",
        "index_merge": "index_merge",
        "segment": "index_merge",
        "review": "review",
        "export": "export"
    }
    return mapping.get(node_name, node_name)


# ==================== WebSocket 端点 ====================

@router.websocket("/ws/{batch_id}")
async def websocket_endpoint(websocket: WebSocket, batch_id: str):
    """WebSocket 端点，用于实时推送批改进度
    
    Args:
        websocket: WebSocket 连接
        batch_id: 批次 ID
    """
    await websocket.accept()
    
    # 注册连接
    if batch_id not in active_connections:
        active_connections[batch_id] = []
    active_connections[batch_id].append(websocket)
    
    logger.info(f"WebSocket 连接已建立: batch_id={batch_id}")
    
    try:
        # 发送连接确认
        await websocket.send_json({
            "type": "connected",
            "message": f"已连接到批次 {batch_id}"
        })
        
        # 保持连接，等待客户端消息或断开
        while True:
            try:
                # 等待客户端消息（心跳或命令）
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # 处理心跳
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except asyncio.TimeoutError:
                # 发送心跳检测
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开连接: batch_id={batch_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: batch_id={batch_id}, error={e}")
    finally:
        # 移除连接
        if batch_id in active_connections:
            if websocket in active_connections[batch_id]:
                active_connections[batch_id].remove(websocket)
            if not active_connections[batch_id]:
                del active_connections[batch_id]


# ==================== REST 端点 ====================

@router.get("/status/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """获取批次状态
    
    Args:
        batch_id: 批次 ID
        orchestrator: 编排器
        
    Returns:
        批次状态信息
    """
    try:
        # 尝试从 orchestrator 获取状态
        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_status(run_id)
        
        # 从累积状态获取详细信息
        state = batch_states.get(batch_id, {})
        student_results = state.get("student_results", [])
        export_data = state.get("export_data") or state.get("final_state")
        
        return BatchStatusResponse(
            batch_id=batch_id,
            exam_id=state.get("exam_id", ""),
            status=run_info.status.value,
            total_students=len(student_results),
            completed_students=len([s for s in student_results if s.get("total_score", 0) > 0]),
            unidentified_pages=0,
            results=export_data
        )
        
    except Exception as e:
        logger.error(f"获取批次状态失败: batch_id={batch_id}, error={e}")
        raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")


@router.get("/results/{batch_id}")
async def get_batch_results(batch_id: str):
    """获取批次批改结果
    
    Args:
        batch_id: 批次 ID
        
    Returns:
        批改结果详情
    """
    state = batch_states.get(batch_id)
    
    if not state:
        raise HTTPException(status_code=404, detail=f"批次不存在或已过期: {batch_id}")
    
    # 过滤掉无法 JSON 序列化的数据（如 bytes 类型的图像）
    def filter_serializable(obj):
        if isinstance(obj, dict):
            return {k: filter_serializable(v) for k, v in obj.items() 
                    if not isinstance(v, bytes)}
        elif isinstance(obj, list):
            return [filter_serializable(item) for item in obj 
                    if not isinstance(item, bytes)]
        elif isinstance(obj, bytes):
            return None
        else:
            return obj
    
    return filter_serializable(state)


@router.get("/debug/batch_states")
async def debug_batch_states():
    """调试端点：查看所有 batch_states"""
    return {
        "count": len(batch_states),
        "batch_ids": list(batch_states.keys()),
        "states": {
            bid: {
                "keys": list(state.keys()),
                "status": state.get("status"),
                "has_final_state": "final_state" in state,
                "has_export_data": "export_data" in state,
                "has_student_results": "student_results" in state,
                "student_count": len(state.get("student_results", []))
            }
            for bid, state in batch_states.items()
        }
    }
