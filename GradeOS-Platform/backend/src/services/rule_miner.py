"""规则挖掘器服务

从老师改判样本中分析高频失败模式，为规则升级提供依据。
验证：需求 9.1, 9.2
"""

import logging
from typing import List, Dict, Any, Optional, Set
from collections import Counter, defaultdict
from datetime import datetime

from src.models.grading_log import GradingLog
from src.models.failure_pattern import (
    FailurePattern,
    FailurePatternSummary,
    PatternType
)


logger = logging.getLogger(__name__)


class RuleMiner:
    """规则挖掘器
    
    功能：
    1. 分析改判样本，识别高频失败模式（analyze_overrides）
    2. 判断模式是否可通过规则修复（is_pattern_fixable）
    
    验证：需求 9.1, 9.2
    """
    
    def __init__(
        self,
        min_frequency: int = 3,
        min_confidence: float = 0.7
    ):
        """初始化规则挖掘器
        
        Args:
            min_frequency: 最小频率阈值（低于此值的模式不会被识别）
            min_confidence: 最小置信度阈值
        """
        self.min_frequency = min_frequency
        self.min_confidence = min_confidence
    
    async def analyze_overrides(
        self,
        override_logs: List[GradingLog]
    ) -> List[FailurePattern]:
        """分析改判样本，识别高频失败模式
        
        通过分析改判日志，识别出系统批改中的常见错误模式。
        验证：需求 9.1
        
        Args:
            override_logs: 改判日志列表
            
        Returns:
            识别出的失败模式列表
        """
        if not override_logs:
            logger.info("没有改判样本，跳过规则挖掘")
            return []
        
        logger.info(f"开始分析 {len(override_logs)} 条改判样本")
        
        # 按失败阶段分组
        extraction_failures = []
        normalization_failures = []
        matching_failures = []
        scoring_failures = []
        
        for log in override_logs:
            # 判断失败发生在哪个阶段
            if self._is_extraction_failure(log):
                extraction_failures.append(log)
            elif self._is_normalization_failure(log):
                normalization_failures.append(log)
            elif self._is_matching_failure(log):
                matching_failures.append(log)
            else:
                # 默认归类为评分失败
                scoring_failures.append(log)
        
        # 识别各阶段的失败模式
        patterns = []
        
        # 提取阶段失败模式
        patterns.extend(
            self._identify_extraction_patterns(extraction_failures)
        )
        
        # 规范化阶段失败模式
        patterns.extend(
            self._identify_normalization_patterns(normalization_failures)
        )
        
        # 匹配阶段失败模式
        patterns.extend(
            self._identify_matching_patterns(matching_failures)
        )
        
        # 评分阶段失败模式
        patterns.extend(
            self._identify_scoring_patterns(scoring_failures)
        )
        
        # 过滤低频模式
        patterns = [
            p for p in patterns
            if p.frequency >= self.min_frequency
        ]
        
        # 按频率排序
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        
        logger.info(f"识别出 {len(patterns)} 个失败模式")
        return patterns
    
    def is_pattern_fixable(self, pattern: FailurePattern) -> bool:
        """判断模式是否可通过规则修复
        
        分析失败模式的特征，判断是否可以通过添加规则来修复。
        验证：需求 9.2
        
        Args:
            pattern: 失败模式
            
        Returns:
            是否可修复
        """
        # 提取和规范化阶段的失败通常可以通过规则修复
        if pattern.pattern_type in [PatternType.EXTRACTION, PatternType.NORMALIZATION]:
            # 检查是否有明确的错误特征
            if pattern.error_signature:
                return True
            # 检查频率是否足够高（说明是系统性问题）
            if pattern.frequency >= 5:
                return True
        
        # 匹配阶段的失败可能可以修复
        if pattern.pattern_type == PatternType.MATCHING:
            # 如果有建议的修复方案，则认为可修复
            if pattern.suggested_fix:
                return True
            # 高频匹配失败通常可以通过添加同义词规则修复
            if pattern.frequency >= 10:
                return True
        
        # 评分阶段的失败通常需要人工介入，不适合自动修复
        if pattern.pattern_type == PatternType.SCORING:
            # 除非有非常明确的规则（如固定扣分错误）
            if "固定扣分" in pattern.description or "扣分规则" in pattern.description:
                return True
            return False
        
        return False
    
    def _is_extraction_failure(self, log: GradingLog) -> bool:
        """判断是否为提取阶段失败"""
        # 提取置信度低
        if log.extraction_confidence is not None and log.extraction_confidence < 0.6:
            return True
        # 提取的答案为空或None
        if not log.extracted_answer or log.extracted_answer.strip() == "":
            return True
        return False
    
    def _is_normalization_failure(self, log: GradingLog) -> bool:
        """判断是否为规范化阶段失败"""
        # 有规范化规则应用，但匹配失败
        if (log.normalization_rules_applied and
            len(log.normalization_rules_applied) > 0 and
            log.match_result is False):
            return True
        # 规范化前后差异很大，但仍然匹配失败
        if (log.extracted_answer and log.normalized_answer and
            log.extracted_answer != log.normalized_answer and
            log.match_result is False):
            return True
        return False
    
    def _is_matching_failure(self, log: GradingLog) -> bool:
        """判断是否为匹配阶段失败"""
        # 明确标记为匹配失败
        if log.match_result is False and log.match_failure_reason:
            return True
        return False
    
    def _identify_extraction_patterns(
        self,
        logs: List[GradingLog]
    ) -> List[FailurePattern]:
        """识别提取阶段的失败模式"""
        if not logs:
            return []
        
        patterns = []
        
        # 按题目类型分组
        by_question = defaultdict(list)
        for log in logs:
            by_question[log.question_id].append(log)
        
        # 识别每个题目的提取失败模式
        for question_id, question_logs in by_question.items():
            if len(question_logs) >= self.min_frequency:
                pattern = FailurePattern(
                    pattern_type=PatternType.EXTRACTION,
                    description=f"题目 {question_id} 答案提取失败（低置信度或空答案）",
                    frequency=len(question_logs),
                    sample_log_ids=[log.log_id for log in question_logs[:5]],
                    confidence=0.8,
                    is_fixable=True,
                    error_signature=f"extraction_failure_{question_id}",
                    affected_question_types=[question_id],
                    suggested_fix="优化提取提示词，增加答案区域识别规则"
                )
                patterns.append(pattern)
        
        return patterns
    
    def _identify_normalization_patterns(
        self,
        logs: List[GradingLog]
    ) -> List[FailurePattern]:
        """识别规范化阶段的失败模式"""
        if not logs:
            return []
        
        patterns = []
        
        # 统计规范化规则失败情况
        rule_failures = Counter()
        rule_samples = defaultdict(list)
        
        for log in logs:
            if log.normalization_rules_applied:
                for rule in log.normalization_rules_applied:
                    rule_failures[rule] += 1
                    rule_samples[rule].append(log.log_id)
        
        # 为每个高频失败的规则创建模式
        for rule, count in rule_failures.items():
            if count >= self.min_frequency:
                pattern = FailurePattern(
                    pattern_type=PatternType.NORMALIZATION,
                    description=f"规范化规则 '{rule}' 应用后仍然匹配失败",
                    frequency=count,
                    sample_log_ids=rule_samples[rule][:5],
                    confidence=0.85,
                    is_fixable=True,
                    error_signature=f"normalization_{rule}",
                    suggested_fix=f"检查规则 '{rule}' 的实现，可能需要添加更多变体"
                )
                patterns.append(pattern)
        
        return patterns
    
    def _identify_matching_patterns(
        self,
        logs: List[GradingLog]
    ) -> List[FailurePattern]:
        """识别匹配阶段的失败模式"""
        if not logs:
            return []
        
        patterns = []
        
        # 统计匹配失败原因
        failure_reasons = Counter()
        reason_samples = defaultdict(list)
        
        for log in logs:
            if log.match_failure_reason:
                failure_reasons[log.match_failure_reason] += 1
                reason_samples[log.match_failure_reason].append(log.log_id)
        
        # 为每个高频失败原因创建模式
        for reason, count in failure_reasons.items():
            if count >= self.min_frequency:
                pattern = FailurePattern(
                    pattern_type=PatternType.MATCHING,
                    description=f"匹配失败：{reason}",
                    frequency=count,
                    sample_log_ids=reason_samples[reason][:5],
                    confidence=0.9,
                    is_fixable=True,
                    error_signature=f"matching_{hash(reason) % 10000}",
                    suggested_fix="添加同义词规则或放宽匹配条件"
                )
                patterns.append(pattern)
        
        return patterns
    
    def _identify_scoring_patterns(
        self,
        logs: List[GradingLog]
    ) -> List[FailurePattern]:
        """识别评分阶段的失败模式"""
        if not logs:
            return []
        
        patterns = []
        
        # 统计评分偏差
        score_diffs = []
        for log in logs:
            if (log.score is not None and
                log.override_score is not None):
                diff = abs(log.score - log.override_score)
                score_diffs.append((diff, log))
        
        # 如果有大量评分偏差，创建模式
        if len(score_diffs) >= self.min_frequency:
            # 按偏差大小排序
            score_diffs.sort(key=lambda x: x[0], reverse=True)
            
            # 取前5个作为样本
            sample_logs = [log for _, log in score_diffs[:5]]
            
            pattern = FailurePattern(
                pattern_type=PatternType.SCORING,
                description=f"评分偏差：系统评分与教师评分存在差异",
                frequency=len(score_diffs),
                sample_log_ids=[log.log_id for log in sample_logs],
                confidence=0.7,
                is_fixable=False,  # 评分偏差通常需要人工调整
                error_signature="scoring_deviation",
                suggested_fix="需要人工审核评分标准，可能需要调整校准配置"
            )
            patterns.append(pattern)
        
        return patterns
    
    def generate_summary(
        self,
        override_logs: List[GradingLog],
        patterns: List[FailurePattern]
    ) -> FailurePatternSummary:
        """生成失败模式汇总报告
        
        Args:
            override_logs: 改判日志列表
            patterns: 识别出的失败模式列表
            
        Returns:
            失败模式汇总
        """
        fixable_count = sum(1 for p in patterns if p.is_fixable)
        
        return FailurePatternSummary(
            total_overrides=len(override_logs),
            total_patterns=len(patterns),
            fixable_patterns=fixable_count,
            patterns=patterns,
            analysis_time=datetime.utcnow()
        )


# 全局单例
_rule_miner: Optional[RuleMiner] = None


def get_rule_miner() -> RuleMiner:
    """获取规则挖掘器单例"""
    global _rule_miner
    if _rule_miner is None:
        _rule_miner = RuleMiner()
    return _rule_miner
