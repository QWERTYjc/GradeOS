"""规则挖掘器单元测试"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.services.rule_miner import RuleMiner
from src.models.grading_log import GradingLog
from src.models.failure_pattern import PatternType


@pytest.fixture
def rule_miner():
    """创建规则挖掘器实例"""
    return RuleMiner(min_frequency=2, min_confidence=0.7)


@pytest.fixture
def sample_extraction_failures():
    """创建提取失败的样本日志"""
    logs = []
    for i in range(5):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q1",
            extracted_answer="",  # 空答案
            extraction_confidence=0.3,  # 低置信度
            score=0.0,
            max_score=10.0,
            confidence=0.5,
            was_overridden=True,
            override_score=8.0,
            override_reason="答案提取失败"
        )
        logs.append(log)
    return logs


@pytest.fixture
def sample_normalization_failures():
    """创建规范化失败的样本日志"""
    logs = []
    for i in range(3):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q2",
            extracted_answer="100cm",
            extraction_confidence=0.9,
            normalized_answer="100cm",
            normalization_rules_applied=["unit_conversion"],
            match_result=False,
            match_failure_reason="单位不匹配",
            score=0.0,
            max_score=10.0,
            confidence=0.8,
            was_overridden=True,
            override_score=10.0,
            override_reason="单位换算规则缺失"
        )
        logs.append(log)
    return logs


@pytest.fixture
def sample_matching_failures():
    """创建匹配失败的样本日志"""
    logs = []
    for i in range(4):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q3",
            extracted_answer="正确",
            extraction_confidence=0.95,
            normalized_answer="正确",
            match_result=False,
            match_failure_reason="同义词未识别",
            score=0.0,
            max_score=5.0,
            confidence=0.7,
            was_overridden=True,
            override_score=5.0,
            override_reason="应该识别为正确答案"
        )
        logs.append(log)
    return logs


class TestRuleMiner:
    """规则挖掘器测试"""
    
    @pytest.mark.asyncio
    async def test_analyze_empty_logs(self, rule_miner):
        """测试空日志列表"""
        patterns = await rule_miner.analyze_overrides([])
        assert patterns == []
    
    @pytest.mark.asyncio
    async def test_analyze_extraction_failures(
        self,
        rule_miner,
        sample_extraction_failures
    ):
        """测试提取失败模式识别"""
        patterns = await rule_miner.analyze_overrides(sample_extraction_failures)
        
        # 应该识别出至少一个提取失败模式
        extraction_patterns = [
            p for p in patterns
            if p.pattern_type == PatternType.EXTRACTION
        ]
        assert len(extraction_patterns) > 0
        
        # 检查模式属性
        pattern = extraction_patterns[0]
        assert pattern.frequency >= 2
        assert "q1" in pattern.description or "q1" in pattern.affected_question_types
        assert len(pattern.sample_log_ids) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_normalization_failures(
        self,
        rule_miner,
        sample_normalization_failures
    ):
        """测试规范化失败模式识别"""
        patterns = await rule_miner.analyze_overrides(sample_normalization_failures)
        
        # 应该识别出规范化失败模式
        norm_patterns = [
            p for p in patterns
            if p.pattern_type == PatternType.NORMALIZATION
        ]
        assert len(norm_patterns) > 0
        
        # 检查模式属性
        pattern = norm_patterns[0]
        assert pattern.frequency >= 2
        assert "unit_conversion" in pattern.description or "unit_conversion" in pattern.error_signature
    
    @pytest.mark.asyncio
    async def test_analyze_matching_failures(
        self,
        rule_miner,
        sample_matching_failures
    ):
        """测试匹配失败模式识别"""
        patterns = await rule_miner.analyze_overrides(sample_matching_failures)
        
        # 应该识别出匹配失败模式
        match_patterns = [
            p for p in patterns
            if p.pattern_type == PatternType.MATCHING
        ]
        assert len(match_patterns) > 0
        
        # 检查模式属性
        pattern = match_patterns[0]
        assert pattern.frequency >= 2
        assert "同义词" in pattern.description or "同义词" in pattern.match_failure_reason if hasattr(pattern, 'match_failure_reason') else True
    
    @pytest.mark.asyncio
    async def test_pattern_frequency_filtering(self, rule_miner):
        """测试频率过滤"""
        # 创建低频失败（只有1个）
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q_rare",
            extracted_answer="",
            extraction_confidence=0.2,
            score=0.0,
            max_score=10.0,
            confidence=0.5,
            was_overridden=True,
            override_score=8.0,
            override_reason="罕见错误"
        )
        
        patterns = await rule_miner.analyze_overrides([log])
        
        # 低频模式应该被过滤掉（min_frequency=2）
        assert len(patterns) == 0
    
    def test_is_pattern_fixable_extraction(self, rule_miner):
        """测试提取失败模式的可修复性判断"""
        pattern = type('Pattern', (), {
            'pattern_type': PatternType.EXTRACTION,
            'error_signature': 'extraction_failure_q1',
            'frequency': 5,
            'suggested_fix': None
        })()
        
        assert rule_miner.is_pattern_fixable(pattern) is True
    
    def test_is_pattern_fixable_normalization(self, rule_miner):
        """测试规范化失败模式的可修复性判断"""
        pattern = type('Pattern', (), {
            'pattern_type': PatternType.NORMALIZATION,
            'error_signature': 'normalization_unit_conversion',
            'frequency': 3,
            'suggested_fix': None
        })()
        
        assert rule_miner.is_pattern_fixable(pattern) is True
    
    def test_is_pattern_fixable_matching_with_suggestion(self, rule_miner):
        """测试有修复建议的匹配失败模式"""
        pattern = type('Pattern', (), {
            'pattern_type': PatternType.MATCHING,
            'error_signature': None,
            'frequency': 2,
            'suggested_fix': '添加同义词规则'
        })()
        
        assert rule_miner.is_pattern_fixable(pattern) is True
    
    def test_is_pattern_fixable_scoring(self, rule_miner):
        """测试评分失败模式的可修复性判断"""
        # 一般评分失败不可自动修复
        pattern = type('Pattern', (), {
            'pattern_type': PatternType.SCORING,
            'error_signature': None,
            'frequency': 10,
            'suggested_fix': None,
            'description': '评分偏差'
        })()
        
        assert rule_miner.is_pattern_fixable(pattern) is False
        
        # 但固定扣分错误可以修复
        pattern_fixable = type('Pattern', (), {
            'pattern_type': PatternType.SCORING,
            'error_signature': None,
            'frequency': 10,
            'suggested_fix': None,
            'description': '固定扣分规则错误'
        })()
        
        assert rule_miner.is_pattern_fixable(pattern_fixable) is True
    
    @pytest.mark.asyncio
    async def test_mixed_failure_types(
        self,
        rule_miner,
        sample_extraction_failures,
        sample_normalization_failures,
        sample_matching_failures
    ):
        """测试混合失败类型的分析"""
        all_logs = (
            sample_extraction_failures +
            sample_normalization_failures +
            sample_matching_failures
        )
        
        patterns = await rule_miner.analyze_overrides(all_logs)
        
        # 应该识别出多种类型的模式
        pattern_types = {p.pattern_type for p in patterns}
        assert len(pattern_types) >= 2  # 至少两种类型
        
        # 模式应该按频率排序
        if len(patterns) > 1:
            for i in range(len(patterns) - 1):
                assert patterns[i].frequency >= patterns[i + 1].frequency
    
    @pytest.mark.asyncio
    async def test_generate_summary(
        self,
        rule_miner,
        sample_extraction_failures
    ):
        """测试生成汇总报告"""
        patterns = await rule_miner.analyze_overrides(sample_extraction_failures)
        summary = rule_miner.generate_summary(sample_extraction_failures, patterns)
        
        assert summary.total_overrides == len(sample_extraction_failures)
        assert summary.total_patterns == len(patterns)
        assert summary.fixable_patterns <= summary.total_patterns
        assert len(summary.patterns) == len(patterns)
        assert summary.analysis_time is not None
