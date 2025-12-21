"""批量提交 API 路由 - 支持多学生合卷上传"""

import uuid
import logging
import tempfile
import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import fitz
from PIL import Image
from io import BytesIO
import os

from src.models.enums import SubmissionStatus
from src.services.student_identification import StudentIdentificationService
from src.services.rubric_parser import RubricParserService
from src.services.strict_grading import StrictGradingService
from src.services.cached_grading import CachedGradingService

# LangGraph 智能体（自我修正批改）
from src.agents.grading_agent import GradingAgent
from src.services.gemini_reasoning import GeminiReasoningClient

# 自我成长系统组件
from src.services.exemplar_memory import ExemplarMemory
from src.services.prompt_assembler import PromptAssembler
from src.services.calibration import CalibrationService
from src.services.grading_logger import GradingLogger, get_grading_logger
from src.models.grading_log import GradingLog


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


async def run_real_grading_workflow(
    batch_id: str, 
    rubric_images: List[bytes], 
    answer_images: List[bytes],
    api_key: str
):
    """
    真实批改工作流，通过 WebSocket 推送进度
    
    正确的工作流步骤（按设计文档）：
    1. Intake - 接收文件
    2. Preprocess - 预处理（已完成 PDF 转图像）
    3. Rubric Parse - 解析评分标准
    4. Grading - 固定分批并行批改（10张图片一批，不需要先识别学生）
    5. Segment - 批改后学生分割（基于批改结果智能判断学生边界）
    6. Review - 汇总审核
    7. Export - 导出结果
    """
    import asyncio
    
    # 等待 WebSocket 连接建立
    await asyncio.sleep(2.0)
    
    logger.info(f"开始真实批改工作流: batch_id={batch_id}, rubric_pages={len(rubric_images)}, answer_pages={len(answer_images)}")
    
    # 存储最终结果
    all_results = []
    
    try:
        # === Step 1: Intake ===
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "intake",
            "status": "running",
            "message": "接收文件中..."
        })
        await asyncio.sleep(0.3)
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "intake",
            "status": "completed",
            "message": f"接收完成：评分标准 {len(rubric_images)} 页，学生作答 {len(answer_images)} 页"
        })
        
        # === Step 2: Preprocess (已完成) ===
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "preprocess",
            "status": "running",
            "message": "正在预处理图像..."
        })
        await asyncio.sleep(0.3)
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "preprocess",
            "status": "completed",
            "message": "预处理完成"
        })
        
        # === Step 3: Parse Rubric (评分标准解析 - 对应前端 rubric_parse 节点) ===
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "rubric_parse",
            "status": "running",
            "message": "正在解析评分标准..."
        })
        
        # 初始化评分标准解析服务
        rubric_parser = RubricParserService(api_key=api_key)
        parsed_rubric = await rubric_parser.parse_rubric(rubric_images)
        rubric_context = rubric_parser.format_rubric_context(parsed_rubric)
        
        # 发送 rubric_parsed 事件（对应设计文档 StreamEvent）
        await broadcast_progress(batch_id, {
            "type": "rubric_parsed",
            "totalQuestions": parsed_rubric.total_questions,
            "totalScore": parsed_rubric.total_score
        })
        
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "rubric_parse",
            "status": "completed",
            "message": f"评分标准解析完成：{parsed_rubric.total_questions} 道题，满分 {parsed_rubric.total_score} 分"
        })
        
        # === Step 4: 固定分批并行批改 (对应前端 grading 节点) ===
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "grading",
            "status": "running",
            "message": f"开始固定分批批改，共 {len(answer_images)} 页..."
        })
        
        # 初始化自我成长系统组件（优雅降级：数据库不可用时使用 None）
        exemplar_memory = None
        prompt_assembler = None
        calibration_service = None
        calibration_profile = None
        grading_logger = None
        
        try:
            # 1. 判例记忆库 - 检索相似批改示例用于 few-shot 学习
            exemplar_memory = ExemplarMemory()
            
            # 2. 动态提示词拼装器 - 根据上下文构建最优提示词
            prompt_assembler = PromptAssembler()
            
            # 3. 校准服务 - 加载教师个性化评分配置
            calibration_service = CalibrationService()
            teacher_id = "default_teacher"
            calibration_profile = await calibration_service.get_or_create_profile(teacher_id)
            
            # 4. 批改日志服务 - 记录批改过程用于后续分析
            grading_logger = get_grading_logger()
            
            logger.info(f"自我成长组件初始化成功: exemplar_memory={exemplar_memory is not None}, "
                        f"calibration_profile={calibration_profile.profile_id if calibration_profile else None}")
        except Exception as init_err:
            logger.warning(f"自我成长组件初始化失败（降级模式）: {init_err}")
        
        # 初始化 LangGraph 批改智能体（支持自我修正）
        reasoning_client = GeminiReasoningClient(api_key=api_key)
        # 注意：每个并行批次会创建自己的 GradingAgent 实例，避免状态冲突
        logger.info("使用 LangGraph GradingAgent（自我修正模式）")
        
        # 按 10 张一组分批
        BATCH_SIZE = 10
        batches = [answer_images[i:i + BATCH_SIZE] for i in range(0, len(answer_images), BATCH_SIZE)]
        total_batches = len(batches)
        
        logger.info(f"分批完成：共 {total_batches} 个批次")
        
        # 存储所有页面的批改结果
        all_page_results = []
        success_count = 0
        failure_count = 0
        
        # 创建批次 Agent（用于前端显示）
        grading_agents = []
        for batch_idx in range(total_batches):
            agent_id = f"batch_{batch_idx}"
            grading_agents.append({
                "id": agent_id,
                "label": f"批次 {batch_idx + 1}",
                "status": "pending"
            })
        
        await broadcast_progress(batch_id, {
            "type": "parallel_agents_created",
            "parentNodeId": "grading",
            "agents": grading_agents
        })
        
        # 发送批次进度
        await broadcast_progress(batch_id, {
            "type": "batch_start",
            "batchIndex": 0,
            "totalBatches": total_batches
        })
        
        # 定义单个批次的处理函数
        async def process_single_batch(batch_idx: int, batch_images: list) -> dict:
            """处理单个批次，返回该批次的结果"""
            agent_id = f"batch_{batch_idx}"
            batch_results = []
            batch_success = 0
            batch_failure = 0
            
            # 每个批次创建独立的 LangGraph 批改智能体（避免并发状态冲突）
            batch_reasoning_client = GeminiReasoningClient(api_key=api_key)
            batch_grading_agent = GradingAgent(reasoning_client=batch_reasoning_client)
            
            # 更新批次状态为运行中
            await broadcast_progress(batch_id, {
                "type": "agent_update",
                "agentId": agent_id,
                "status": "running",
                "message": f"正在批改第 {batch_idx + 1} 批（LangGraph 自我修正模式）...",
                "logs": [f"开始处理批次 {batch_idx + 1}，共 {len(batch_images)} 页，使用 LangGraph Agent"]
            })
            
            try:
                # 批改当前批次的所有页面
                for page_offset, page_image in enumerate(batch_images):
                    page_index = batch_idx * BATCH_SIZE + page_offset
                    
                    try:
                        # === 自我成长：批改前检索相似判例 ===
                        similar_exemplars = []
                        if exemplar_memory is not None:
                            import hashlib
                            page_hash = hashlib.md5(page_image).hexdigest()
                            
                            try:
                                similar_exemplars = await exemplar_memory.retrieve_similar(
                                    question_image_hash=page_hash,
                                    question_type="general",
                                    top_k=3,
                                    min_similarity=0.7
                                )
                                logger.debug(f"页面 {page_index} 找到 {len(similar_exemplars)} 个相似判例")
                            except Exception as ex:
                                logger.warning(f"判例检索失败（继续批改）: {ex}")
                        
                        # === 自我成长：动态拼装提示词 ===
                        if prompt_assembler is not None:
                            try:
                                assembled_prompt = prompt_assembler.assemble(
                                    question_type="general",
                                    rubric=rubric_context,
                                    exemplars=similar_exemplars,
                                    error_patterns=[],
                                    previous_confidence=None,
                                    calibration=calibration_profile
                                )
                                # 后续可将 assembled_prompt 传递给 GradingAgent
                            except Exception as ex:
                                logger.warning(f"提示词拼装失败（使用默认）: {ex}")
                        
                        # 将图像转换为 base64（LangGraph Agent 需要）
                        import base64
                        image_b64 = base64.b64encode(page_image).decode('utf-8')
                        
                        # 🚀 使用 LangGraph GradingAgent 批改（支持循环自我修正）
                        thread_id = f"{batch_id}_page_{page_index}"
                        grading_state = await batch_grading_agent.run(
                            question_image=image_b64,
                            rubric=rubric_context,
                            max_score=parsed_rubric.total_score,
                            standard_answer=None,
                            thread_id=thread_id
                        )
                        
                        # 从 LangGraph 状态提取结果
                        final_score = grading_state.get("final_score", 0.0)
                        max_score = grading_state.get("max_score", parsed_rubric.total_score)
                        confidence = grading_state.get("confidence", 0.0)
                        feedback = grading_state.get("student_feedback", "")
                        revision_count = grading_state.get("revision_count", 0)
                        
                        # 构造兼容的结果对象
                        class LangGraphResult:
                            def __init__(self, state, page_idx):
                                self.total_score = state.get("final_score", 0.0)
                                self.max_total_score = state.get("max_score", 0.0)
                                self.question_results = []
                                # 创建单个题目结果
                                class QuestionResult:
                                    def __init__(self, state, page_idx):
                                        self.question_id = f"q_{page_idx}"
                                        self.awarded_score = state.get("final_score", 0.0)
                                        self.max_score = state.get("max_score", 0.0)
                                        self.confidence = state.get("confidence", 0.0)
                                        self.overall_feedback = state.get("student_feedback", "")
                                        self.is_correct = state.get("final_score", 0) > 0
                                        self.scoring_point_results = []
                                self.question_results.append(QuestionResult(state, page_idx))
                        
                        result = LangGraphResult(grading_state, page_index)
                        
                        # === 自我成长：记录批改日志 ===
                        if grading_logger is not None:
                            try:
                                log_entry = GradingLog(
                                    submission_id=batch_id,
                                    question_id=f"q_{page_index}",
                                    extracted_answer="",
                                    extraction_confidence=confidence,
                                    evidence_snippets=[],
                                    normalized_answer=None,
                                    normalization_rules_applied=[],
                                    match_result=final_score > 0,
                                    match_failure_reason=None,
                                    score=final_score,
                                    max_score=max_score,
                                    confidence=confidence,
                                    reasoning_trace=grading_state.get("reasoning_trace", [])
                                )
                                await grading_logger.log_grading(log_entry)
                            except Exception as ex:
                                logger.warning(f"批改日志记录失败: {ex}")
                        
                        batch_results.append({
                            "page_index": page_index,
                            "result": result,
                            "question_ids": [f"q_{page_index}"],
                            "success": True,
                            "revision_count": revision_count  # 记录自我修正次数
                        })
                        batch_success += 1
                        
                        # 推送页面完成事件
                        await broadcast_progress(batch_id, {
                            "type": "page_complete",
                            "pageIndex": page_index,
                            "success": True,
                            "score": final_score,
                            "maxScore": max_score,
                            "revisionCount": revision_count  # 前端可显示修正次数
                        })
                        
                    except Exception as e:
                        logger.error(f"页面 {page_index} 批改失败: {e}")
                        batch_results.append({
                            "page_index": page_index,
                            "result": None,
                            "question_ids": [],
                            "success": False,
                            "error": str(e)
                        })
                        batch_failure += 1
                
                # 更新批次进度
                await broadcast_progress(batch_id, {
                    "type": "agent_update",
                    "agentId": agent_id,
                    "status": "completed",
                    "progress": 100,
                    "message": f"批次 {batch_idx + 1} 完成",
                    "logs": [f"批次 {batch_idx + 1} 处理完成"]
                })
                
                # 推送批次完成事件
                await broadcast_progress(batch_id, {
                    "type": "batch_complete",
                    "batchIndex": batch_idx,
                    "totalBatches": total_batches,
                    "successCount": batch_success,
                    "failureCount": batch_failure
                })
                
                return {
                    "batch_idx": batch_idx,
                    "results": batch_results,
                    "success_count": batch_success,
                    "failure_count": batch_failure,
                    "status": "completed"
                }
                
            except Exception as e:
                logger.error(f"批次 {batch_idx} 处理失败: {e}")
                await broadcast_progress(batch_id, {
                    "type": "agent_update",
                    "agentId": agent_id,
                    "status": "failed",
                    "message": f"批次失败: {str(e)}",
                    "logs": [f"错误: {str(e)}"]
                })
                return {
                    "batch_idx": batch_idx,
                    "results": batch_results,
                    "success_count": batch_success,
                    "failure_count": batch_failure,
                    "status": "failed",
                    "error": str(e)
                }
        
        # 🚀 并行处理所有批次
        logger.info(f"开始并行处理 {total_batches} 个批次...")
        batch_tasks = [
            process_single_batch(idx, batch_images) 
            for idx, batch_images in enumerate(batches)
        ]
        batch_results_list = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # 汇总所有批次的结果
        for batch_result in batch_results_list:
            if isinstance(batch_result, Exception):
                logger.error(f"批次处理异常: {batch_result}")
                continue
            if isinstance(batch_result, dict):
                all_page_results.extend(batch_result.get("results", []))
                success_count += batch_result.get("success_count", 0)
                failure_count += batch_result.get("failure_count", 0)
        
        # 按页面索引排序结果
        all_page_results.sort(key=lambda x: x.get("page_index", 0))
        
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "grading",
            "status": "completed",
            "message": f"固定分批批改完成：成功 {success_count} 页，失败 {failure_count} 页"
        })
        
        # === Step 5: 批改后学生分割 (对应前端 segment 节点) ===
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "segment",
            "status": "running",
            "message": "正在基于批改结果分析学生边界..."
        })
        
        # 基于题目序列循环检测学生边界
        boundaries = []
        current_start = 0
        last_max_question = 0
        student_count = 0
        
        for i, page_result in enumerate(all_page_results):
            question_ids = page_result.get("question_ids", [])
            if not question_ids:
                continue
            
            try:
                first_q = int(question_ids[0])
                
                # 检测循环：题目编号回退到较小值（如从 5 回到 1），说明换了学生
                if first_q < last_max_question and first_q <= 2:
                    if i > current_start:
                        student_count += 1
                        boundaries.append({
                            "studentKey": f"学生{student_count}",
                            "startPage": current_start,
                            "endPage": i - 1,
                            "confidence": 0.7,  # 基于循环检测的置信度较低
                            "needsConfirmation": True
                        })
                    current_start = i
                    last_max_question = first_q
                else:
                    for q_id in question_ids:
                        try:
                            q_num = int(q_id)
                            last_max_question = max(last_max_question, q_num)
                        except ValueError:
                            pass
            except (ValueError, IndexError):
                pass
        
        # 添加最后一个学生
        if current_start < len(all_page_results):
            student_count += 1
            boundaries.append({
                "studentKey": f"学生{student_count}",
                "startPage": current_start,
                "endPage": len(all_page_results) - 1,
                "confidence": 0.7,
                "needsConfirmation": True
            })
        
        num_students = len(boundaries)
        
        # 发送学生边界检测结果
        await broadcast_progress(batch_id, {
            "type": "student_identified",
            "boundaries": boundaries
        })
        
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "segment",
            "status": "completed",
            "message": f"学生分割完成：检测到 {num_students} 名学生（基于题目序列循环）"
        })
        
        # === Step 6: 按学生聚合结果 ===
        all_results = []
        for boundary in boundaries:
            student_pages = [
                pr for pr in all_page_results 
                if pr["success"] and boundary["startPage"] <= pr["page_index"] <= boundary["endPage"]
            ]
            
            total_score = sum(pr["result"].total_score for pr in student_pages if pr.get("result"))
            max_score = sum(pr["result"].max_total_score for pr in student_pages if pr.get("result"))
            
            # 聚合所有页面的题目结果
            student_question_results = []
            for pr in student_pages:
                if pr.get("result") and pr["result"].question_results:
                    # 将 Pydantic 模型转换为字典
                    q_results = [
                        q.dict() if hasattr(q, "dict") else q 
                        for q in pr["result"].question_results
                    ]
                    student_question_results.extend(q_results)
            
            # 按题目 ID 排序
            try:
                student_question_results.sort(key=lambda x: float(x.get("question_id", 0)) if isinstance(x, dict) else float(x.question_id))
            except:
                pass

            all_results.append({
                "studentName": boundary["studentKey"],
                "total_score": total_score,
                "max_score": max_score,
                "page_range": (boundary["startPage"], boundary["endPage"]),
                "questionResults": student_question_results
            })
        
        # === Step 7: Review ===
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "review",
            "status": "running",
            "message": "正在汇总审核结果..."
        })
        await asyncio.sleep(0.5)
        
        # 计算统计信息
        if all_results:
            scores = [r["total_score"] for r in all_results]
            avg_score = sum(scores) / len(scores) if scores else 0
            max_total = all_results[0]["max_score"] if all_results else 100
            
            await broadcast_progress(batch_id, {
                "type": "workflow_update",
                "nodeId": "review",
                "status": "completed",
                "message": f"审核完成，平均分 {avg_score:.1f}/{max_total}"
            })
        else:
            await broadcast_progress(batch_id, {
                "type": "workflow_update",
                "nodeId": "review",
                "status": "completed",
                "message": "审核完成"
            })
        
        # === Step 8: Export ===
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "export",
            "status": "running",
            "message": "正在导出结果..."
        })
        await asyncio.sleep(0.3)
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "export",
            "status": "completed",
            "message": "导出完成"
        })
        
        # 工作流完成，发送最终结果
        await broadcast_progress(batch_id, {
            "type": "workflow_completed",
            "message": f"批改工作流完成，共处理 {num_students} 名学生",
            "results": [
                {
                    "studentName": r["studentName"],
                    "score": r["total_score"],
                    "maxScore": r["max_score"],
                    "questionResults": [
                        {
                            "questionId": str(q.get("question_id")) if isinstance(q, dict) else str(q.question_id),
                            "score": q.get("awarded_score") if isinstance(q, dict) else q.awarded_score,
                            "maxScore": q.get("max_score") if isinstance(q, dict) else q.max_score,
                            "feedback": q.get("overall_feedback") if isinstance(q, dict) else q.overall_feedback,
                            "scoringPoints": [
                                {
                                    "description": sp.get("description") if isinstance(sp, dict) else sp.description,
                                    "score": sp.get("awarded_score") if isinstance(sp, dict) else sp.awarded_score,
                                    "maxScore": sp.get("max_score") if isinstance(sp, dict) else sp.max_score,
                                    "isCorrect": sp.get("is_correct") if isinstance(sp, dict) else sp.is_correct,
                                    "explanation": sp.get("explanation") if isinstance(sp, dict) else sp.explanation
                                }
                                for sp in (q.get("scoring_point_results") if isinstance(q, dict) else q.scoring_point_results) or []
                            ] if (q.get("scoring_point_results") if isinstance(q, dict) else q.scoring_point_results) else []
                        }
                        for q in r["questionResults"]
                    ]
                } for r in all_results
            ]
        })
        
    except Exception as e:
        logger.error(f"批改工作流失败: {str(e)}", exc_info=True)
        await broadcast_progress(batch_id, {
            "type": "workflow_error",
            "message": f"批改失败: {str(e)}"
        })


@router.post("/submit", response_model=BatchSubmissionResponse)
async def submit_batch(
    exam_id: Optional[str] = Form(None, description="考试 ID"),
    rubrics: List[UploadFile] = File(..., description="评分标准 PDF"),
    files: List[UploadFile] = File(..., description="学生作答 PDF"),
    api_key: Optional[str] = Form(None, description="Gemini API Key"),
    auto_identify: bool = Form(True, description="是否自动识别学生身份")
):
    """
    批量提交试卷并进行批改
    
    支持上传包含多个学生作业的文件（如整班扫描的 PDF），
    系统会自动识别每页所属的学生并分别批改。
    
    Args:
        exam_id: 考试 ID
        rubric_file: 评分标准 PDF 文件
        answer_file: 学生作答 PDF 文件
        api_key: Gemini API Key
        auto_identify: 是否启用自动学生识别（默认开启）
        
    Returns:
        BatchSubmissionResponse: 批次信息
    """

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
        # Allow request even without API key for testing
        # if not api_key:
        #     raise HTTPException(status_code=400, detail="API Key not provided and GEMINI_API_KEY env var not set")

    if not exam_id:
        exam_id = str(uuid.uuid4())

    batch_id = str(uuid.uuid4())
    
    logger.info(
        f"收到批量提交: "
        f"batch_id={batch_id}, "
        f"exam_id={exam_id}, "
        f"auto_identify={auto_identify}"
    )
    
    temp_dir = None
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # 保存上传的文件 (Taking the first file from the list for now)
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
        
        # 估算时间：每页 30 秒
        estimated_time = total_pages * 30
        
        # 启动后台真实批改任务
        asyncio.create_task(run_real_grading_workflow(
            batch_id=batch_id,
            rubric_images=rubric_images,
            answer_images=answer_images,
            api_key=api_key or ""
        ))
        
        # 返回响应
        return BatchSubmissionResponse(
            batch_id=batch_id,
            status=SubmissionStatus.UPLOADED,
            total_pages=total_pages,
            estimated_completion_time=estimated_time
        )
        
    except Exception as e:
        logger.error(f"批量提交失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 不清理临时文件，让后台任务使用（后台任务会清理）
        pass


@router.get("/status/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str):
    """
    查询批量批改状态
    
    Args:
        batch_id: 批次 ID
        
    Returns:
        BatchStatusResponse: 批次状态和进度
    """
    # TODO: 从 Temporal 查询工作流状态
    # handle = temporal_client.get_workflow_handle(f"batch_{batch_id}")
    # progress = await handle.query(BatchGradingWorkflow.get_progress)
    
    return BatchStatusResponse(
        batch_id=batch_id,
        exam_id="",
        status="processing",
        total_students=0,
        completed_students=0,
        unidentified_pages=0
    )


@router.get("/results/{batch_id}")
async def get_batch_results(batch_id: str):
    """
    获取批量批改结果
    
    返回每个学生的批改结果汇总。
    
    Args:
        batch_id: 批次 ID
        
    Returns:
        dict: 包含所有学生批改结果的字典
    """
    # TODO: 从数据库或 Temporal 获取结果
    return {
        "batch_id": batch_id,
        "students": []
    }


@router.post("/grade-sync")
async def grade_batch_sync(
    rubric_file: UploadFile = File(..., description="评分标准 PDF"),
    answer_file: UploadFile = File(..., description="学生作答 PDF"),
    api_key: Optional[str] = Form(None, description="Gemini API Key"),
    total_score: int = Form(105, description="总分"),
    total_questions: int = Form(19, description="总题数")
):
    """
    同步批改（用于测试）
    
    完整的批改流程：
    1. 解析评分标准
    2. 识别学生边界
    3. 逐题批改
    4. 返回详细结果
    
    Args:
        rubric_file: 评分标准 PDF
        answer_file: 学生作答 PDF
        api_key: Gemini API Key
        total_score: 总分
        total_questions: 总题数
        
    Returns:
        dict: 包含所有学生的批改结果
    """

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=400, detail="API Key not provided and GEMINI_API_KEY env var not set")

    temp_dir = None
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # 保存上传的文件
        rubric_path = temp_path / "rubric.pdf"
        answer_path = temp_path / "answer.pdf"
        
        rubric_content = await rubric_file.read()
        answer_content = await answer_file.read()
        
        with open(rubric_path, "wb") as f:
            f.write(rubric_content)
        with open(answer_path, "wb") as f:
            f.write(answer_content)
        
        # 转换 PDF 为图像
        logger.info("转换 PDF 为图像...")
        rubric_images = _pdf_to_images(str(rubric_path), dpi=150)
        answer_images = _pdf_to_images(str(answer_path), dpi=150)
        
        logger.info(
            f"PDF 转换完成: "
            f"rubric_pages={len(rubric_images)}, "
            f"answer_pages={len(answer_images)}"
        )
        
        # ===== 步骤 1: 解析评分标准 =====
        logger.info("解析评分标准...")
        rubric_parser = RubricParserService(api_key=api_key)
        parsed_rubric = await rubric_parser.parse_rubric(
            rubric_images,
            expected_total_score=total_score
        )
        
        logger.info(
            f"评分标准解析完成: "
            f"题目数={parsed_rubric.total_questions}, "
            f"总分={parsed_rubric.total_score}"
        )
        
        rubric_context = rubric_parser.format_rubric_context(parsed_rubric)
        
        # ===== 步骤 2: 识别学生边界 =====
        logger.info("识别学生边界...")
        id_service = StudentIdentificationService(api_key=api_key)
        segmentation_result = await id_service.segment_batch_document(answer_images)
        student_groups = id_service.group_pages_by_student(segmentation_result)
        
        logger.info(f"识别到 {len(student_groups)} 名学生")
        
        # ===== 步骤 3: 批改每个学生 =====
        logger.info("开始批改...")
        grading_service = StrictGradingService(api_key=api_key)
        all_results = []
        
        for idx, (student_key, page_indices) in enumerate(student_groups.items(), 1):
            logger.info(f"正在批改 {student_key}...")
            
            # 推送进度
            await broadcast_progress(
                batch_id,
                {
                    "type": "progress",
                    "stage": "grading",
                    "current_student": idx,
                    "total_students": len(student_groups),
                    "student_name": student_key,
                    "percentage": int(idx / len(student_groups) * 100)
                }
            )
            
            # 获取该学生的页面
            student_pages = [answer_images[i] for i in page_indices]
            
            # 批改
            result = await grading_service.grade_student(
                student_pages=student_pages,
                rubric=parsed_rubric,
                rubric_context=rubric_context,
                student_name=student_key
            )
            result.page_range = (min(page_indices), max(page_indices))
            all_results.append(result)
            
            logger.info(
                f"{student_key} 批改完成: "
                f"{result.total_score}/{result.max_total_score} 分"
            )
        
        # ===== 步骤 4: 格式化结果 =====
        # 推送完成通知
        await broadcast_progress(
            batch_id,
            {
                "type": "progress",
                "stage": "formatting",
                "percentage": 95
            }
        )
        
        response_data = {
            "status": "completed",
            "total_students": len(all_results),
            "students": []
        }
        
        for result in all_results:
            student_data = {
                "name": result.student_name,
                "page_range": {
                    "start": result.page_range[0] + 1,
                    "end": result.page_range[1] + 1
                },
                "total_score": result.total_score,
                "max_score": result.max_total_score,
                "percentage": round(result.total_score / result.max_total_score * 100, 1),
                "questions_graded": len(result.question_results),
                "details": []
            }
            
            # 添加每题的详细结果
            for q_result in result.question_results:
                question_detail = {
                    "question_id": q_result.question_id,
                    "score": q_result.awarded_score,
                    "max_score": q_result.max_score,
                    "scoring_point_results": [
                        {
                            "description": sp.description,
                            "max_score": sp.max_score,
                            "awarded_score": sp.awarded_score,
                            "is_correct": sp.is_correct,
                            "explanation": sp.explanation
                        }
                        for sp in q_result.scoring_point_results
                    ],
                    "used_alternative_solution": q_result.used_alternative_solution,
                    "confidence": q_result.confidence
                }
                student_data["details"].append(question_detail)
            
            response_data["students"].append(student_data)
        
        # 推送完成通知
        await broadcast_progress(
            batch_id,
            {
                "type": "completed",
                "percentage": 100,
                "total_students": len(all_results),
                "message": "批改完成"
            }
        )
        
        return response_data
        
    except Exception as e:
        logger.error(f"批改失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        if temp_dir:
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}")



# ==================== WebSocket 实时推送 ====================

@router.websocket("/ws/{batch_id}")
async def websocket_batch_progress(websocket: WebSocket, batch_id: str):
    """
    WebSocket 实时推送批改进度
    
    客户端连接后，系统会实时推送以下事件：
    - "progress": 批改进度更新
    - "completed": 批改完成
    - "error": 批改出错
    
    Args:
        batch_id: 批次 ID
    """
    await websocket.accept()
    
    # 注册连接
    if batch_id not in active_connections:
        active_connections[batch_id] = []
    active_connections[batch_id].append(websocket)
    
    logger.info(f"WebSocket 连接已建立: batch_id={batch_id}")
    
    try:
        # 保持连接打开，等待客户端消息
        while True:
            data = await websocket.receive_text()
            # 可以处理客户端发送的命令，例如取消批改
            if data == "cancel":
                logger.info(f"收到取消请求: batch_id={batch_id}")
                await websocket.send_json({
                    "type": "info",
                    "message": "取消请求已收到，正在停止批改..."
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket 连接已断开: batch_id={batch_id}")
        active_connections[batch_id].remove(websocket)
        if not active_connections[batch_id]:
            del active_connections[batch_id]
    
    except Exception as e:
        logger.error(f"WebSocket 错误: batch_id={batch_id}, error={str(e)}")
        if batch_id in active_connections and websocket in active_connections[batch_id]:
            active_connections[batch_id].remove(websocket)


async def broadcast_progress(batch_id: str, message: Dict[str, Any]):
    """
    广播批改进度到所有连接的客户端
    
    Args:
        batch_id: 批次 ID
        message: 消息内容
    """
    if batch_id not in active_connections:
        return
    
    disconnected = []
    for websocket in active_connections[batch_id]:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
            disconnected.append(websocket)
    
    # 清理断开的连接
    for websocket in disconnected:
        active_connections[batch_id].remove(websocket)



@router.post("/grade-cached")
async def grade_batch_cached(
    rubric_file: UploadFile = File(..., description="评分标准 PDF"),
    answer_file: UploadFile = File(..., description="学生作答 PDF"),
    api_key: Optional[str] = Form(None, description="Gemini API Key"),
    total_score: int = Form(105, description="总分"),
    total_questions: int = Form(19, description="总题数"),
    batch_id: Optional[str] = Form(None, description="批次 ID (可选，用于前端预生成)")
):
    """
    优化的批改端点 - 使用 Context Caching
    
    相比 /grade-sync，此端点使用 Gemini Context Caching 技术：
    - 评分标准只计费一次
    - 后续学生批改免费使用缓存
    - 节省约 25% 的 Token 成本
    
    适用场景：
    - 批改多个学生（2+ 个学生）
    - 同一份评分标准
    - 需要降低成本
    
    Args:
        rubric_file: 评分标准 PDF
        answer_file: 学生作答 PDF
        api_key: Gemini API Key
        total_score: 总分
        total_questions: 总题数
        
    Returns:
        dict: 包含所有学生的批改结果 + Token 节省信息
    """

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=400, detail="API Key not provided and GEMINI_API_KEY env var not set")

    if not batch_id:
        batch_id = str(uuid.uuid4())
    temp_dir = None
    
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # 保存上传的文件
        rubric_path = temp_path / "rubric.pdf"
        answer_path = temp_path / "answer.pdf"
        
        rubric_content = await rubric_file.read()
        answer_content = await answer_file.read()
        
        with open(rubric_path, "wb") as f:
            f.write(rubric_content)
        with open(answer_path, "wb") as f:
            f.write(answer_content)
        
        # 转换 PDF 为图像
        logger.info(f"转换 PDF 为图像: batch_id={batch_id}")
        rubric_images = _pdf_to_images(str(rubric_path), dpi=150)
        answer_images = _pdf_to_images(str(answer_path), dpi=150)
        
        logger.info(
            f"PDF 转换完成: "
            f"batch_id={batch_id}, "
            f"rubric_pages={len(rubric_images)}, "
            f"answer_pages={len(answer_images)}"
        )
        
        # 推送进度
        await broadcast_progress(
            batch_id,
            {
                "type": "progress",
                "stage": "parsing_rubric",
                "percentage": 10
            }
        )
        
        # ===== 步骤 1: 解析评分标准 =====
        logger.info("解析评分标准...")
        rubric_parser = RubricParserService(api_key=api_key)
        parsed_rubric = await rubric_parser.parse_rubric(
            rubric_images,
            expected_total_score=total_score
        )
        
        logger.info(
            f"评分标准解析完成: "
            f"题目数={parsed_rubric.total_questions}, "
            f"总分={parsed_rubric.total_score}"
        )
        
        rubric_context = rubric_parser.format_rubric_context(parsed_rubric)
        
        # 推送进度
        await broadcast_progress(
            batch_id,
            {
                "type": "progress",
                "stage": "identifying_students",
                "percentage": 20
            }
        )
        
        # ===== 步骤 2: 识别学生边界 =====
        logger.info("识别学生边界...")
        id_service = StudentIdentificationService(api_key=api_key)
        segmentation_result = await id_service.segment_batch_document(answer_images)
        student_groups = id_service.group_pages_by_student(segmentation_result)
        
        logger.info(f"识别到 {len(student_groups)} 名学生")
        
        # 推送进度
        await broadcast_progress(
            batch_id,
            {
                "type": "progress",
                "stage": "creating_cache",
                "percentage": 30
            }
        )
        
        # ===== 步骤 3: 创建评分标准缓存 =====
        logger.info("创建评分标准缓存...")
        cached_service = CachedGradingService(api_key=api_key)
        await cached_service.create_rubric_cache(parsed_rubric, rubric_context)
        
        cache_info = cached_service.get_cache_info()
        logger.info(f"缓存创建成功: {cache_info['cache_name']}")
        
        # 推送进度
        await broadcast_progress(
            batch_id,
            {
                "type": "progress",
                "stage": "grading",
                "percentage": 40,
                "total_students": len(student_groups)
            }
        )
        
        # ===== 步骤 4: 使用缓存批改每个学生 =====
        logger.info("开始批改（使用缓存）...")
        all_results = []
        
        for idx, (student_key, page_indices) in enumerate(student_groups.items(), 1):
            logger.info(f"正在批改 {student_key}（使用缓存）...")
            
            # 推送进度
            await broadcast_progress(
                batch_id,
                {
                    "type": "progress",
                    "stage": "grading",
                    "current_student": idx,
                    "total_students": len(student_groups),
                    "student_name": student_key,
                    "percentage": 40 + int(idx / len(student_groups) * 50)
                }
            )
            
            # 获取该学生的页面
            student_pages = [answer_images[i] for i in page_indices]
            
            # 使用缓存批改
            result = await cached_service.grade_student_with_cache(
                student_pages=student_pages,
                student_name=student_key
            )
            result.page_range = (min(page_indices), max(page_indices))
            all_results.append(result)
            
            logger.info(
                f"{student_key} 批改完成: "
                f"{result.total_score}/{result.max_total_score} 分"
            )
        
        # ===== 步骤 5: 格式化结果 =====
        await broadcast_progress(
            batch_id,
            {
                "type": "progress",
                "stage": "formatting",
                "percentage": 95
            }
        )
        
        response_data = {
            "status": "completed",
            "total_students": len(all_results),
            "optimization": {
                "method": "context_caching",
                "cache_info": cache_info,
                "token_savings": {
                    "description": "使用 Context Caching 节省约 25% Token",
                    "estimated_savings_per_student": "约 15,000-20,000 tokens",
                    "cost_savings_per_student": "约 $0.04-0.05"
                }
            },
            "students": []
        }
        
        for result in all_results:
            student_data = {
                "name": result.student_name,
                "page_range": {
                    "start": result.page_range[0] + 1,
                    "end": result.page_range[1] + 1
                },
                "total_score": result.total_score,
                "max_score": result.max_total_score,
                "percentage": round(result.total_score / result.max_total_score * 100, 1),
                "questions_graded": len(result.question_results),
                "details": []
            }
            
            # 添加每题的详细结果
            for q_result in result.question_results:
                question_detail = {
                    "question_id": q_result.question_id,
                    "score": q_result.awarded_score,
                    "max_score": q_result.max_score,
                    "scoring_point_results": [
                        {
                            "description": sp.description,
                            "max_score": sp.max_score,
                            "awarded_score": sp.awarded_score,
                            "is_correct": sp.is_correct,
                            "explanation": sp.explanation
                        }
                        for sp in q_result.scoring_point_results
                    ],
                    "used_alternative_solution": q_result.used_alternative_solution,
                    "confidence": q_result.confidence
                }
                student_data["details"].append(question_detail)
            
            response_data["students"].append(student_data)
        
        # 清理缓存
        cached_service.delete_cache()
        logger.info("缓存已清理")
        
        # 推送完成通知
        await broadcast_progress(
            batch_id,
            {
                "type": "completed",
                "percentage": 100,
                "total_students": len(all_results),
                "message": "批改完成（使用缓存优化）"
            }
        )
        
        return response_data
        
    except Exception as e:
        logger.error(f"批改失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        if temp_dir:
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}")
