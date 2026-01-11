"""双阶段批改 Worker

按照 implementation_plan.md 实现：
1. 视觉模型：内容提取 + 简单批改
2. 文本模型：深度批改
3. 生成批改自白

Requirements: Phase 4
"""

import logging
import base64
from typing import Dict, Any, List, Optional, Callable, Awaitable

from src.services.gemini_reasoning import GeminiReasoningClient
from src.services.grading_self_report import generate_self_report
from src.services.student_summary import generate_student_summary


logger = logging.getLogger(__name__)


class GradingWorker:
    """双阶段批改 Worker
    
    工作流程：
    1. 视觉模型：extract_answer_evidence（内容提取）
    2. 文本模型：score_from_evidence（深度批改）
    3. 生成批改自白（辅助人工核查）
    """
    
    def __init__(
        self,
        api_key: str,
        model_name: Optional[str] = None,
        parsed_rubric: Optional[Dict[str, Any]] = None,
    ):
        self.reasoning_client = GeminiReasoningClient(
            api_key=api_key,
            model_name=model_name,
        )
        self.parsed_rubric = parsed_rubric or {}
    
    async def grade_page(
        self,
        image: bytes,
        page_index: int,
        page_context: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        批改单页（双阶段流程）
        
        Args:
            image: 页面图像
            page_index: 页面索引
            page_context: 索引上下文
            stream_callback: 流式回调
            
        Returns:
            批改结果，包含 score, max_score, question_details, self_report 等
        """
        logger.info(f"[GradingWorker] 开始批改页面 {page_index}")
        
        # Stage 1: 视觉模型 - 内容提取
        evidence = await self.reasoning_client.extract_answer_evidence(
            image=image,
            parsed_rubric=self.parsed_rubric,
            page_context=page_context,
            stream_callback=stream_callback,
        )
        
        # 检查是否为空白页/封面页
        if evidence.get("is_blank_page") or evidence.get("is_cover_page"):
            return {
                "page_index": page_index,
                "status": "completed",
                "score": 0.0,
                "max_score": 0.0,
                "is_blank_page": True,
                "question_details": [],
                "self_report": None,
            }
        
        # Stage 2: 文本模型 - 深度批改
        score_result = await self.reasoning_client.score_from_evidence(
            evidence=evidence,
            parsed_rubric=self.parsed_rubric,
            page_context=page_context,
            mode="fast",
            stream_callback=stream_callback,
        )
        
        # 低置信度时使用 strict 模式重批
        confidence = score_result.get("confidence", 0.0)
        did_second_pass = False
        
        if confidence < 0.65:
            logger.info(f"[GradingWorker] 页面 {page_index} 置信度低 ({confidence:.2f})，启用严格模式")
            score_result = await self.reasoning_client.score_from_evidence(
                evidence=evidence,
                parsed_rubric=self.parsed_rubric,
                page_context=page_context,
                mode="strict",
                stream_callback=stream_callback,
            )
            did_second_pass = True
        
        # Stage 3: 生成批改自白
        self_report = generate_self_report(
            evidence=evidence,
            score_result=score_result,
            page_index=page_index,
        )
        
        result = {
            "page_index": page_index,
            "status": "completed",
            "score": score_result.get("score", 0.0),
            "max_score": score_result.get("max_score", 0.0),
            "confidence": score_result.get("confidence", 0.0),
            "question_numbers": score_result.get("question_numbers", []),
            "question_details": score_result.get("question_details", []),
            "student_info": evidence.get("student_info") or score_result.get("student_info"),
            "page_summary": score_result.get("page_summary") or evidence.get("page_summary", ""),
            "is_blank_page": False,
            "did_second_pass": did_second_pass,
            "self_report": self_report,
        }
        
        logger.info(
            f"[GradingWorker] 页面 {page_index} 完成: "
            f"score={result['score']}/{result['max_score']}, "
            f"confidence={result['confidence']:.2f}"
        )
        
        return result
    
    async def grade_batch(
        self,
        images: List[bytes],
        page_indices: List[int],
        page_contexts: Optional[Dict[int, Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        批量批改多页
        
        Args:
            images: 图像列表
            page_indices: 页面索引列表
            page_contexts: 页面上下文字典
            progress_callback: 进度回调 (current, total, message)
            
        Returns:
            批改结果列表
        """
        results = []
        total = len(images)
        
        for i, (image, page_idx) in enumerate(zip(images, page_indices)):
            if progress_callback:
                await progress_callback(i + 1, total, f"批改页面 {page_idx}...")
            
            page_context = page_contexts.get(page_idx) if page_contexts else None
            result = await self.grade_page(image, page_idx, page_context)
            results.append(result)
        
        return results


async def create_grading_worker(
    api_key: str,
    parsed_rubric: Dict[str, Any],
    model_name: Optional[str] = None,
) -> GradingWorker:
    """工厂函数：创建批改 Worker"""
    return GradingWorker(
        api_key=api_key,
        model_name=model_name,
        parsed_rubric=parsed_rubric,
    )
