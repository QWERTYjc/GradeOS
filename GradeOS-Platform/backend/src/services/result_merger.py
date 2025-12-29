"""
结果合并器 (Result Merger)

负责合并分批并行处理的批改结果，确保最终输出完整、准确的学生成绩。

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

from src.models.grading_models import (
    QuestionResult,
    PageGradingResult,
    StudentResult,
    CrossPageQuestion,
    BatchGradingResult,
)
from src.services.question_merger import QuestionMerger, MergeConfig

logger = logging.getLogger(__name__)


@dataclass
class MergeValidationResult:
    """合并验证结果"""
    is_valid: bool
    actual_total: float
    expected_total: float
    discrepancy: float
    message: str


@dataclass
class ConflictInfo:
    """评分冲突信息"""
    question_id: str
    scoring_point: str
    scores: List[float]
    confidences: List[float]
    resolved_score: float
    resolution_reason: str


class ResultMerger:
    """
    结果合并器
    
    负责：
    - 按页码顺序合并所有批改结果 (Req 4.1)
    - 合并同一题目的多次评分 (Req 4.2)
    - 汇总跨页题目得分点，不重复计算满分 (Req 4.3)
    - 检测和处理评分冲突 (Req 4.4)
    - 验证总分等于各题得分之和 (Req 4.5)
    - 标记需人工审核的结果 (Req 4.6)
    """
    
    def __init__(
        self,
        question_merger: Optional[QuestionMerger] = None,
        score_tolerance: float = 0.01
    ):
        """
        初始化结果合并器
        
        Args:
            question_merger: 题目合并器实例
            score_tolerance: 分数验证容差
        """
        self.question_merger = question_merger or QuestionMerger()
        self.score_tolerance = score_tolerance
        self.conflicts: List[ConflictInfo] = []
    
    def merge_batch_results(
        self,
        batch_results: List[List[PageGradingResult]]
    ) -> List[PageGradingResult]:
        """
        合并多个批次的结果 (Requirement 4.1)
        
        1. 按页码排序
        2. 去重
        3. 返回有序结果
        
        Args:
            batch_results: 多个批次的页面结果列表
            
        Returns:
            List[PageGradingResult]: 合并后的有序页面结果
        """
        # 展平所有批次结果
        all_pages: List[PageGradingResult] = []
        for batch in batch_results:
            all_pages.extend(batch)
        
        # 按页码去重（保留置信度更高的）
        page_map: Dict[int, PageGradingResult] = {}
        for page in all_pages:
            page_idx = page.page_index
            if page_idx not in page_map:
                page_map[page_idx] = page
            else:
                # 如果已存在，比较并保留更好的结果
                existing = page_map[page_idx]
                if self._is_better_result(page, existing):
                    page_map[page_idx] = page
        
        # 按页码排序
        sorted_pages = sorted(page_map.values(), key=lambda x: x.page_index)
        
        logger.info(f"合并 {len(batch_results)} 个批次，共 {len(sorted_pages)} 页")
        return sorted_pages

    def merge_cross_page_questions(
        self,
        page_results: List[PageGradingResult]
    ) -> Tuple[List[QuestionResult], List[CrossPageQuestion]]:
        """
        处理跨页题目合并 (Requirements 4.2, 4.3)
        
        1. 检测跨页题目
        2. 合并跨页评分
        3. 确保满分不重复计算
        
        Args:
            page_results: 页面批改结果列表
            
        Returns:
            Tuple[List[QuestionResult], List[CrossPageQuestion]]: 
                (合并后的题目结果, 跨页题目信息)
        """
        # 检测跨页题目
        cross_page_questions = self.question_merger.detect_cross_page_questions(
            page_results
        )
        
        # 合并跨页结果
        merged_results = self.question_merger.merge_cross_page_results(
            page_results, cross_page_questions
        )
        
        logger.info(
            f"跨页合并完成: {len(cross_page_questions)} 个跨页题目, "
            f"共 {len(merged_results)} 道题目"
        )
        
        return merged_results, cross_page_questions
    
    def detect_and_resolve_conflicts(
        self,
        question_results: List[QuestionResult]
    ) -> List[QuestionResult]:
        """
        检测和处理评分冲突 (Requirement 4.4)
        
        当同一得分点有不同分数时，选择置信度更高的结果。
        
        Args:
            question_results: 题目结果列表
            
        Returns:
            List[QuestionResult]: 处理冲突后的结果
        """
        self.conflicts.clear()
        
        # 按题目ID分组
        question_map: Dict[str, List[QuestionResult]] = {}
        for qr in question_results:
            qid = qr.question_id.lower()
            if qid not in question_map:
                question_map[qid] = []
            question_map[qid].append(qr)
        
        resolved_results: List[QuestionResult] = []
        
        for qid, results in question_map.items():
            if len(results) == 1:
                resolved_results.append(results[0])
            else:
                # 检测冲突并解决
                resolved = self._resolve_question_conflict(qid, results)
                resolved_results.append(resolved)
        
        if self.conflicts:
            logger.warning(f"检测到 {len(self.conflicts)} 个评分冲突")
        
        return resolved_results
    
    def _resolve_question_conflict(
        self,
        question_id: str,
        results: List[QuestionResult]
    ) -> QuestionResult:
        """
        解决单个题目的评分冲突
        
        策略：选择置信度最高的结果
        """
        # 按置信度排序
        sorted_results = sorted(results, key=lambda x: x.confidence, reverse=True)
        best_result = sorted_results[0]
        
        # 检查是否存在分数差异
        scores = [r.score for r in results]
        if len(set(scores)) > 1:
            conflict = ConflictInfo(
                question_id=question_id,
                scoring_point="总分",
                scores=scores,
                confidences=[r.confidence for r in results],
                resolved_score=best_result.score,
                resolution_reason=f"选择置信度最高的结果 ({best_result.confidence:.2f})"
            )
            self.conflicts.append(conflict)
        
        return best_result
    
    def validate_total_score(
        self,
        question_results: List[QuestionResult],
        expected_total: float
    ) -> MergeValidationResult:
        """
        验证总分 (Requirement 4.5)
        
        验证总分等于各题得分之和。
        
        Args:
            question_results: 题目结果列表
            expected_total: 预期总分（满分）
            
        Returns:
            MergeValidationResult: 验证结果
        """
        actual_total = sum(r.score for r in question_results)
        actual_max = sum(r.max_score for r in question_results)
        
        # 检查满分是否匹配
        max_score_valid = abs(actual_max - expected_total) < self.score_tolerance
        
        discrepancy = abs(actual_total - sum(r.score for r in question_results))
        
        if not max_score_valid:
            return MergeValidationResult(
                is_valid=False,
                actual_total=actual_total,
                expected_total=expected_total,
                discrepancy=abs(actual_max - expected_total),
                message=f"满分不匹配: 实际 {actual_max}, 预期 {expected_total}"
            )
        
        return MergeValidationResult(
            is_valid=True,
            actual_total=actual_total,
            expected_total=expected_total,
            discrepancy=discrepancy,
            message="验证通过"
        )

    def create_student_result(
        self,
        student_key: str,
        question_results: List[QuestionResult],
        start_page: int,
        end_page: int,
        expected_total: float,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None
    ) -> StudentResult:
        """
        创建学生结果 (Requirement 4.6)
        
        如果总分验证失败，标记需要人工审核。
        
        Args:
            student_key: 学生标识
            question_results: 题目结果列表
            start_page: 起始页
            end_page: 结束页
            expected_total: 预期满分
            student_id: 学号（可选）
            student_name: 姓名（可选）
            
        Returns:
            StudentResult: 学生批改结果
        """
        # 计算总分
        total_score = sum(r.score for r in question_results)
        max_total_score = sum(r.max_score for r in question_results)
        
        # 计算平均置信度
        if question_results:
            avg_confidence = sum(r.confidence for r in question_results) / len(question_results)
        else:
            avg_confidence = 0.0
        
        # 验证总分
        validation = self.validate_total_score(question_results, expected_total)
        
        # 确定是否需要人工确认 (Requirement 4.6)
        needs_confirmation = (
            not validation.is_valid or
            avg_confidence < 0.7 or
            any(r.is_cross_page and r.confidence < 0.8 for r in question_results) or
            len(self.conflicts) > 0
        )
        
        return StudentResult(
            student_key=student_key,
            student_id=student_id,
            student_name=student_name,
            start_page=start_page,
            end_page=end_page,
            total_score=total_score,
            max_total_score=max_total_score,
            question_results=question_results,
            confidence=avg_confidence,
            needs_confirmation=needs_confirmation
        )
    
    def merge_all(
        self,
        batch_results: List[List[PageGradingResult]],
        expected_total: float
    ) -> Tuple[List[QuestionResult], List[CrossPageQuestion], MergeValidationResult]:
        """
        执行完整的合并流程
        
        1. 合并批次结果
        2. 处理跨页题目
        3. 解决评分冲突
        4. 验证总分
        
        Args:
            batch_results: 多个批次的页面结果
            expected_total: 预期满分
            
        Returns:
            Tuple: (合并后的题目结果, 跨页题目信息, 验证结果)
        """
        # 1. 合并批次结果
        merged_pages = self.merge_batch_results(batch_results)
        
        # 2. 处理跨页题目
        question_results, cross_page_questions = self.merge_cross_page_questions(
            merged_pages
        )
        
        # 3. 解决评分冲突
        resolved_results = self.detect_and_resolve_conflicts(question_results)
        
        # 4. 验证总分
        validation = self.validate_total_score(resolved_results, expected_total)
        
        return resolved_results, cross_page_questions, validation
    
    def get_conflicts(self) -> List[ConflictInfo]:
        """获取检测到的评分冲突"""
        return self.conflicts.copy()
    
    # ==================== 私有辅助方法 ====================
    
    def _is_better_result(
        self,
        new_result: PageGradingResult,
        existing_result: PageGradingResult
    ) -> bool:
        """
        判断新结果是否比现有结果更好
        
        比较标准：
        1. 非空白页优于空白页
        2. 题目数量更多
        3. 平均置信度更高
        """
        # 非空白页优于空白页
        if existing_result.is_blank_page and not new_result.is_blank_page:
            return True
        if new_result.is_blank_page and not existing_result.is_blank_page:
            return False
        
        # 题目数量更多
        if len(new_result.question_results) > len(existing_result.question_results):
            return True
        if len(new_result.question_results) < len(existing_result.question_results):
            return False
        
        # 平均置信度更高
        new_confidence = self._calculate_avg_confidence(new_result)
        existing_confidence = self._calculate_avg_confidence(existing_result)
        
        return new_confidence > existing_confidence
    
    def _calculate_avg_confidence(self, page_result: PageGradingResult) -> float:
        """计算页面结果的平均置信度"""
        if not page_result.question_results:
            return 0.0
        return sum(
            qr.confidence for qr in page_result.question_results
        ) / len(page_result.question_results)


# 导出
__all__ = [
    "ResultMerger",
    "MergeValidationResult",
    "ConflictInfo",
]
