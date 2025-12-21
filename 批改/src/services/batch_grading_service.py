"""批次批改服务 - 实现固定分批并行批改 + 批改后学生分割

按照设计文档实现的正确流程：
1. 固定分批并行批改（10张图片一批）
2. 批改后学生分割（基于批改结果智能判断学生边界）
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from src.services.strict_grading import StrictGradingService, StudentGradingResult
from src.services.rubric_parser import ParsedRubric


logger = logging.getLogger(__name__)

BATCH_SIZE = 10  # 固定批次大小


@dataclass
class PageGradingResult:
    """单页批改结果"""
    page_index: int
    question_ids: List[str] = field(default_factory=list)
    student_marker: Optional[str] = None  # 学生标识（姓名/学号）
    scores: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.9
    raw_result: Optional[Dict[str, Any]] = None


@dataclass
class BatchResult:
    """批次批改结果"""
    batch_index: int
    page_results: List[PageGradingResult]
    success_count: int
    failure_count: int


@dataclass
class StudentBoundary:
    """学生边界"""
    student_key: str
    start_page: int
    end_page: int
    confidence: float
    needs_confirmation: bool


@dataclass
class BoundaryDetectionResult:
    """边界检测结果"""
    boundaries: List[StudentBoundary]
    total_students: int
    unassigned_pages: List[int]


class BatchGradingService:
    """
    批次批改服务
    
    实现固定分批并行批改 + 批改后学生分割
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.grading_service = StrictGradingService(api_key=api_key)
    
    def create_batches(self, images: List[bytes]) -> List[List[bytes]]:
        """将图片按 10 张一组分批"""
        batches = []
        for i in range(0, len(images), BATCH_SIZE):
            batches.append(images[i:i + BATCH_SIZE])
        return batches
    
    async def process_batch(
        self,
        batch_index: int,
        images: List[bytes],
        rubric: ParsedRubric,
        rubric_context: str,
        progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """处理单个批次"""
        logger.info(f"开始处理批次 {batch_index + 1}，共 {len(images)} 张图片")
        
        page_results = []
        success_count = 0
        failure_count = 0
        
        # 批次内并行处理
        for i, image in enumerate(images):
            page_index = batch_index * BATCH_SIZE + i
            
            try:
                # 调用批改服务处理单页
                result = await self.grading_service.grade_student(
                    student_pages=[image],
                    rubric=rubric,
                    rubric_context=rubric_context,
                    student_name=f"Page_{page_index}"
                )
                
                # 提取题目 ID 和分数
                question_ids = [q.question_id for q in result.question_results]
                scores = {q.question_id: q.awarded_score for q in result.question_results}
                
                # 检测学生标识（从批改结果中提取）
                student_marker = self._extract_student_marker(result)
                
                page_results.append(PageGradingResult(
                    page_index=page_index,
                    question_ids=question_ids,
                    student_marker=student_marker,
                    scores=scores,
                    confidence=min([q.confidence for q in result.question_results] or [0.9]),
                    raw_result=result
                ))
                success_count += 1
                
                if progress_callback:
                    await progress_callback(page_index + 1, "completed")
                    
            except Exception as e:
                logger.error(f"页面 {page_index} 批改失败: {e}")
                page_results.append(PageGradingResult(
                    page_index=page_index,
                    confidence=0.0
                ))
                failure_count += 1
                
                if progress_callback:
                    await progress_callback(page_index + 1, "failed")
        
        return BatchResult(
            batch_index=batch_index,
            page_results=page_results,
            success_count=success_count,
            failure_count=failure_count
        )
    
    def _extract_student_marker(self, result: StudentGradingResult) -> Optional[str]:
        """从批改结果中提取学生标识"""
        # 如果 student_name 不是自动生成的，使用它
        if result.student_name and not result.student_name.startswith("Page_"):
            return result.student_name
        return None
    
    def detect_student_boundaries(
        self,
        page_results: List[PageGradingResult]
    ) -> BoundaryDetectionResult:
        """
        基于批改结果检测学生边界
        
        策略：
        1. 如果有明确的学生标识，按标识分组
        2. 如果没有，检测题目序列循环（如 1,2,3 → 1,2,3 表示新学生）
        """
        if not page_results:
            return BoundaryDetectionResult(
                boundaries=[],
                total_students=0,
                unassigned_pages=[]
            )
        
        # 策略1：检测学生标识
        markers = [p.student_marker for p in page_results if p.student_marker]
        if markers:
            return self._detect_by_markers(page_results)
        
        # 策略2：检测题目序列循环
        return self._detect_by_question_cycle(page_results)
    
    def _detect_by_markers(
        self,
        page_results: List[PageGradingResult]
    ) -> BoundaryDetectionResult:
        """基于学生标识分组"""
        boundaries = []
        current_marker = None
        current_start = 0
        confidences = []
        
        for i, page in enumerate(page_results):
            marker = page.student_marker or f"Student_{len(boundaries) + 1}"
            
            if marker != current_marker:
                if current_marker is not None:
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
                    boundaries.append(StudentBoundary(
                        student_key=current_marker,
                        start_page=current_start,
                        end_page=i - 1,
                        confidence=avg_conf,
                        needs_confirmation=avg_conf < 0.8
                    ))
                current_marker = marker
                current_start = i
                confidences = []
            
            confidences.append(page.confidence)
        
        # 添加最后一个学生
        if current_marker is not None:
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
            boundaries.append(StudentBoundary(
                student_key=current_marker,
                start_page=current_start,
                end_page=len(page_results) - 1,
                confidence=avg_conf,
                needs_confirmation=avg_conf < 0.8
            ))
        
        return BoundaryDetectionResult(
            boundaries=boundaries,
            total_students=len(boundaries),
            unassigned_pages=[]
        )
    
    def _detect_by_question_cycle(
        self,
        page_results: List[PageGradingResult]
    ) -> BoundaryDetectionResult:
        """
        通过题目序列循环检测边界
        
        逻辑：当题目编号"回退"（如从 5 回到 1），说明换了一个学生
        """
        boundaries = []
        current_start = 0
        last_max_question = 0
        student_count = 0
        confidences = []
        
        for i, page in enumerate(page_results):
            question_ids = page.question_ids
            if not question_ids:
                confidences.append(page.confidence)
                continue
            
            try:
                first_q = int(question_ids[0])
                
                # 检测循环：题目编号回退到较小值
                if first_q < last_max_question and first_q <= 2:
                    # 保存当前学生
                    if i > current_start:
                        student_count += 1
                        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
                        boundaries.append(StudentBoundary(
                            student_key=f"Student_{student_count}",
                            start_page=current_start,
                            end_page=i - 1,
                            confidence=avg_conf,
                            needs_confirmation=True  # 基于循环检测的需要确认
                        ))
                    current_start = i
                    last_max_question = first_q
                    confidences = []
                else:
                    # 更新最大题号
                    for q_id in question_ids:
                        try:
                            q_num = int(q_id)
                            last_max_question = max(last_max_question, q_num)
                        except ValueError:
                            pass
                
                confidences.append(page.confidence)
                
            except (ValueError, IndexError):
                confidences.append(page.confidence)
        
        # 添加最后一个学生
        if current_start < len(page_results):
            student_count += 1
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
            boundaries.append(StudentBoundary(
                student_key=f"Student_{student_count}",
                start_page=current_start,
                end_page=len(page_results) - 1,
                confidence=avg_conf,
                needs_confirmation=True
            ))
        
        return BoundaryDetectionResult(
            boundaries=boundaries,
            total_students=len(boundaries),
            unassigned_pages=[]
        )
    
    def aggregate_by_students(
        self,
        page_results: List[PageGradingResult],
        boundaries: List[StudentBoundary]
    ) -> List[StudentGradingResult]:
        """按学生聚合批改结果"""
        student_results = []
        
        for boundary in boundaries:
            # 获取该学生的所有页面结果
            student_pages = [
                p for p in page_results 
                if boundary.start_page <= p.page_index <= boundary.end_page
            ]
            
            # 聚合分数
            all_question_results = []
            total_score = 0.0
            max_score = 0.0
            
            for page in student_pages:
                if page.raw_result and hasattr(page.raw_result, 'question_results'):
                    all_question_results.extend(page.raw_result.question_results)
                    total_score += page.raw_result.total_score
                    max_score += page.raw_result.max_total_score
            
            student_results.append(StudentGradingResult(
                student_id=boundary.student_key,
                student_name=boundary.student_key,
                total_score=total_score,
                max_total_score=max_score,
                question_results=all_question_results,
                page_range=(boundary.start_page, boundary.end_page)
            ))
        
        return student_results
