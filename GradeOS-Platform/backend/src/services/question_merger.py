"""
题目合并器 (Question Merger)

负责识别和合并跨越多个页面的同一道题目，解决一道题分两页导致
小题当大题算、分数计算错误的问题。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.3
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from src.models.grading_models import (
    QuestionResult,
    PageGradingResult,
    CrossPageQuestion,
    ScoringPointResult,
)

logger = logging.getLogger(__name__)


@dataclass
class MergeConfig:
    """合并配置"""
    confidence_threshold: float = 0.8  # 置信度阈值
    enable_sub_question_detection: bool = True  # 启用子题检测
    max_page_gap: int = 1  # 最大页面间隔（用于判断是否连续）


class QuestionMerger:
    """
    题目合并器
    
    负责检测和合并跨页题目，确保：
    - 同一题目的答案跨越多页时正确合并 (Req 2.1)
    - 连续页面相同题号识别为跨页题目 (Req 2.2)
    - 未完成题目的延续正确处理 (Req 2.3)
    - 满分只计算一次 (Req 2.4)
    - 低置信度时标记需人工确认 (Req 2.5)
    - 子题正确识别和分别评分 (Req 2.6)
    """
    
    def __init__(self, config: Optional[MergeConfig] = None):
        """
        初始化题目合并器
        
        Args:
            config: 合并配置，为 None 时使用默认配置
        """
        self.config = config or MergeConfig()
    
    def detect_cross_page_questions(
        self,
        page_results: List[PageGradingResult]
    ) -> List[CrossPageQuestion]:
        """
        检测跨页题目 (Requirements 2.1, 2.2, 2.3)
        
        Args:
            page_results: 各页面的批改结果（应按页码排序）
            
        Returns:
            List[CrossPageQuestion]: 检测到的跨页题目列表
        """
        if len(page_results) < 2:
            return []
        
        # 按页码排序
        sorted_results = sorted(page_results, key=lambda x: x.page_index)
        
        cross_page_questions: List[CrossPageQuestion] = []
        processed_questions: Set[str] = set()
        
        for i in range(len(sorted_results) - 1):
            curr_page = sorted_results[i]
            next_page = sorted_results[i + 1]
            
            # 检查页面是否连续
            if next_page.page_index - curr_page.page_index > self.config.max_page_gap:
                continue
            
            # 获取当前页和下一页的题目编号
            curr_questions = {
                self._normalize_question_id(qr.question_id): qr 
                for qr in curr_page.question_results
            }
            next_questions = {
                self._normalize_question_id(qr.question_id): qr 
                for qr in next_page.question_results
            }
            
            # 检测相同题号 (Requirement 2.2)
            common_ids = set(curr_questions.keys()) & set(next_questions.keys())
            
            for qid in common_ids:
                if qid in processed_questions:
                    continue
                
                # 计算置信度
                confidence = self._calculate_merge_confidence(
                    curr_questions[qid],
                    next_questions[qid],
                    curr_page.page_index,
                    next_page.page_index
                )
                
                cross_page = CrossPageQuestion(
                    question_id=qid,
                    page_indices=[curr_page.page_index, next_page.page_index],
                    confidence=confidence,
                    merge_reason="连续页面出现相同题号"
                )
                
                # 检查是否还有更多页面包含该题目
                self._extend_cross_page_range(
                    cross_page, 
                    sorted_results[i+2:], 
                    qid
                )
                
                cross_page_questions.append(cross_page)
                processed_questions.add(qid)
            
            # 检测未完成题目延续 (Requirement 2.3)
            continuation = self._detect_continuation(curr_page, next_page)
            if continuation and continuation.question_id not in processed_questions:
                cross_page_questions.append(continuation)
                processed_questions.add(continuation.question_id)
        
        logger.info(f"检测到 {len(cross_page_questions)} 个跨页题目")
        return cross_page_questions

    def merge_cross_page_results(
        self,
        page_results: List[PageGradingResult],
        cross_page_questions: List[CrossPageQuestion]
    ) -> List[QuestionResult]:
        """
        合并跨页题目的评分结果 (Requirements 2.4, 4.3)
        
        确保满分只计算一次，不重复计算。
        
        Args:
            page_results: 各页面的批改结果
            cross_page_questions: 跨页题目信息列表
            
        Returns:
            List[QuestionResult]: 合并后的题目结果列表
        """
        # 建立页码到结果的映射
        page_map: Dict[int, PageGradingResult] = {
            pr.page_index: pr for pr in page_results
        }
        
        # 建立跨页题目ID集合
        cross_page_ids = {cpq.question_id for cpq in cross_page_questions}
        
        merged_results: List[QuestionResult] = []
        processed_questions: Set[str] = set()
        
        # 首先处理跨页题目
        for cpq in cross_page_questions:
            qid = cpq.question_id
            if qid in processed_questions:
                continue
            
            # 收集该题目在所有页面的结果
            question_results_to_merge: List[QuestionResult] = []
            for page_idx in cpq.page_indices:
                if page_idx in page_map:
                    for qr in page_map[page_idx].question_results:
                        if self._normalize_question_id(qr.question_id) == qid:
                            question_results_to_merge.append(qr)
            
            if question_results_to_merge:
                merged = self._merge_question_results(
                    question_results_to_merge,
                    cpq
                )
                merged_results.append(merged)
                processed_questions.add(qid)
        
        # 然后处理非跨页题目
        for page_result in sorted(page_results, key=lambda x: x.page_index):
            for qr in page_result.question_results:
                qid = self._normalize_question_id(qr.question_id)
                if qid not in processed_questions and qid not in cross_page_ids:
                    # 更新页面索引
                    qr.page_indices = [page_result.page_index]
                    merged_results.append(qr)
                    processed_questions.add(qid)
        
        # 按题号排序
        merged_results.sort(key=lambda x: self._question_sort_key(x.question_id))
        
        logger.info(f"合并完成，共 {len(merged_results)} 道题目")
        return merged_results
    
    def _merge_question_results(
        self,
        results: List[QuestionResult],
        cross_page_info: CrossPageQuestion
    ) -> QuestionResult:
        """
        合并同一题目的多个评分结果 (Requirement 2.4)
        
        确保满分只计算一次。
        
        Args:
            results: 待合并的评分结果列表
            cross_page_info: 跨页信息
            
        Returns:
            QuestionResult: 合并后的评分结果
        """
        if not results:
            raise ValueError("没有可合并的结果")
        
        if len(results) == 1:
            result = results[0]
            result.is_cross_page = True
            result.page_indices = cross_page_info.page_indices
            return result
        
        # 取满分最大值（应该相同，但以防万一）
        max_score = max(r.max_score for r in results)
        
        # 合并得分点结果，去重
        merged_scoring_points = self._merge_scoring_point_results(results)
        
        # 计算总得分（基于合并后的得分点）
        total_score = sum(spr.awarded for spr in merged_scoring_points)
        # 确保不超过满分
        total_score = min(total_score, max_score)
        
        # 计算平均置信度
        avg_confidence = sum(r.confidence for r in results) / len(results)
        
        # 合并反馈
        feedbacks = [r.feedback for r in results if r.feedback]
        merged_feedback = " | ".join(feedbacks) if feedbacks else ""
        
        # 合并学生答案
        answers = [r.student_answer for r in results if r.student_answer]
        merged_answer = "\n---\n".join(answers) if answers else ""
        
        # 创建合并结果
        merged = QuestionResult(
            question_id=results[0].question_id,
            score=total_score,
            max_score=max_score,  # 满分只计算一次 (Req 2.4)
            confidence=avg_confidence,
            feedback=merged_feedback,
            scoring_point_results=merged_scoring_points,
            page_indices=cross_page_info.page_indices,
            is_cross_page=True,
            merge_source=[f"page_{r.page_indices[0] if r.page_indices else 'unknown'}" 
                         for r in results],
            student_answer=merged_answer
        )
        
        # 如果置信度低于阈值，标记需要人工确认 (Req 2.5)
        if cross_page_info.confidence < self.config.confidence_threshold:
            merged.feedback = f"[需人工确认] {merged.feedback}"
        
        return merged

    def _merge_scoring_point_results(
        self,
        results: List[QuestionResult]
    ) -> List[ScoringPointResult]:
        """
        合并得分点结果，去除重复
        
        Args:
            results: 题目结果列表
            
        Returns:
            List[ScoringPointResult]: 合并后的得分点结果
        """
        # 使用得分点描述作为键进行去重
        seen_descriptions: Dict[str, ScoringPointResult] = {}
        
        for result in results:
            for spr in result.scoring_point_results:
                desc = spr.scoring_point.description
                if desc not in seen_descriptions:
                    seen_descriptions[desc] = spr
                else:
                    # 如果已存在，取得分较高的
                    existing = seen_descriptions[desc]
                    if spr.awarded > existing.awarded:
                        seen_descriptions[desc] = spr
        
        return list(seen_descriptions.values())
    
    def identify_sub_questions(
        self,
        question_results: List[QuestionResult]
    ) -> Dict[str, List[QuestionResult]]:
        """
        识别子题关系 (Requirement 2.6)
        
        将子题（如 7a, 7b）归类到父题目下。
        
        Args:
            question_results: 题目结果列表
            
        Returns:
            Dict[str, List[QuestionResult]]: 父题号 -> 子题列表
        """
        if not self.config.enable_sub_question_detection:
            return {}
        
        parent_map: Dict[str, List[QuestionResult]] = {}
        
        for qr in question_results:
            parent_id = self._get_parent_question_id(qr.question_id)
            if parent_id:
                if parent_id not in parent_map:
                    parent_map[parent_id] = []
                parent_map[parent_id].append(qr)
        
        return parent_map
    
    def aggregate_sub_question_scores(
        self,
        parent_id: str,
        sub_questions: List[QuestionResult]
    ) -> Tuple[float, float]:
        """
        聚合子题分数 (Requirement 2.6)
        
        Args:
            parent_id: 父题号
            sub_questions: 子题结果列表
            
        Returns:
            Tuple[float, float]: (总得分, 总满分)
        """
        total_score = sum(sq.score for sq in sub_questions)
        total_max = sum(sq.max_score for sq in sub_questions)
        return (total_score, total_max)
    
    # ==================== 私有辅助方法 ====================
    
    def _normalize_question_id(self, question_id: str) -> str:
        """标准化题目编号"""
        normalized = question_id.strip().lower()
        # 移除常见前缀
        normalized = re.sub(r'^(第|题目|question|q)\s*', '', normalized)
        # 移除常见后缀
        normalized = re.sub(r'\s*(题|分)$', '', normalized)
        return normalized
    
    def _get_parent_question_id(self, question_id: str) -> Optional[str]:
        """
        获取父题目编号
        
        例如: "7a" -> "7", "15b" -> "15", "3.1" -> "3"
        """
        normalized = self._normalize_question_id(question_id)
        
        # 匹配 7a, 15b 等格式
        match = re.match(r'^(\d+)[a-zA-Z]$', normalized)
        if match:
            return match.group(1)
        
        # 匹配 3.1, 5.2 等格式
        match = re.match(r'^(\d+)\.\d+$', normalized)
        if match:
            return match.group(1)
        
        return None
    
    def _is_same_question(self, q1: str, q2: str) -> bool:
        """判断两个题号是否为同一题目"""
        return self._normalize_question_id(q1) == self._normalize_question_id(q2)
    
    def _calculate_merge_confidence(
        self,
        result1: QuestionResult,
        result2: QuestionResult,
        page1: int,
        page2: int
    ) -> float:
        """
        计算合并置信度
        
        考虑因素：
        - 页面是否连续
        - 满分是否一致
        - 题目编号是否完全匹配
        """
        confidence = 1.0
        
        # 页面不连续降低置信度
        if abs(page2 - page1) > 1:
            confidence *= 0.7
        
        # 满分不一致降低置信度
        if result1.max_score != result2.max_score:
            confidence *= 0.8
        
        # 题号不完全匹配（如 "7" vs "7a"）降低置信度
        if result1.question_id.lower() != result2.question_id.lower():
            confidence *= 0.9
        
        return confidence
    
    def _detect_continuation(
        self,
        curr_page: PageGradingResult,
        next_page: PageGradingResult
    ) -> Optional[CrossPageQuestion]:
        """
        检测未完成题目的延续 (Requirement 2.3)
        
        当前页最后一道题未完成，下一页以相同题号开始
        """
        if not curr_page.question_results or not next_page.question_results:
            return None
        
        last_question = curr_page.question_results[-1]
        first_question = next_page.question_results[0]
        
        # 检查是否为同一题目
        if not self._is_same_question(
            last_question.question_id, 
            first_question.question_id
        ):
            return None
        
        # 检查是否可能是延续（例如，当前页得分较低可能表示未完成）
        # 这里使用简单的启发式：如果当前页得分低于满分的一半，可能是未完成
        is_likely_continuation = (
            last_question.score < last_question.max_score * 0.5 or
            "未完成" in last_question.feedback or
            "继续" in first_question.feedback
        )
        
        if is_likely_continuation:
            return CrossPageQuestion(
                question_id=self._normalize_question_id(last_question.question_id),
                page_indices=[curr_page.page_index, next_page.page_index],
                confidence=0.7,  # 延续检测置信度较低
                merge_reason="检测到未完成题目延续"
            )
        
        return None
    
    def _extend_cross_page_range(
        self,
        cross_page: CrossPageQuestion,
        remaining_pages: List[PageGradingResult],
        question_id: str
    ) -> None:
        """
        扩展跨页题目的页面范围
        
        检查后续页面是否还包含该题目
        """
        for page_result in remaining_pages:
            for qr in page_result.question_results:
                if self._normalize_question_id(qr.question_id) == question_id:
                    if page_result.page_index not in cross_page.page_indices:
                        cross_page.page_indices.append(page_result.page_index)
                    break
    
    def _question_sort_key(self, question_id: str) -> Tuple:
        """
        生成题目排序键
        
        支持数字和字母混合排序，如: 1, 2, 3a, 3b, 10, 11
        """
        normalized = self._normalize_question_id(question_id)
        
        # 提取数字和字母部分
        match = re.match(r'^(\d+)([a-zA-Z]?)(.*)$', normalized)
        if match:
            num = int(match.group(1))
            letter = match.group(2).lower() if match.group(2) else ''
            rest = match.group(3)
            return (num, letter, rest)
        
        return (float('inf'), normalized, '')


# 导出
__all__ = [
    "QuestionMerger",
    "MergeConfig",
]
