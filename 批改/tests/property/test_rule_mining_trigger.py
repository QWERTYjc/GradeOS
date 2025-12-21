"""规则挖掘触发条件属性测试

验证：需求 9.1 - 当累积足够的老师改判样本时，规则挖掘应被触发
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime, timedelta
from uuid import uuid4

from src.services.rule_miner import RuleMiner
from src.models.grading_log import GradingLog
from src.models.failure_pattern import PatternType


# 生成策略
@st.composite
def grading_log_strategy(draw):
    """生成批改日志的策略"""
    # 随机选择失败类型
    failure_type = draw(st.sampled_from([
        "extraction",
        "normalization", 
        "matching",
        "scoring"
    ]))
    
    # 基础字段
    log = GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id=draw(st.sampled_from(["q1", "q2", "q3", "q4", "q5"])),
        score=draw(st.floats(min_value=0, max_value=10)),
        max_score=10.0,
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        was_overridden=True,
        override_score=draw(st.floats(min_value=0, max_value=10)),
        override_reason=draw(st.text(min_size=5, max_size=50)),
        created_at=datetime.utcnow()
    )
    
    # 根据失败类型设置特定字段
    if failure_type == "extraction":
        log.extracted_answer = ""
        log.extraction_confidence = draw(st.floats(min_value=0.0, max_value=0.5))
    elif failure_type == "normalization":
        log.extracted_answer = draw(st.text(min_size=1, max_size=20))
        log.extraction_confidence = draw(st.floats(min_value=0.7, max_value=1.0))
        log.normalized_answer = log.extracted_answer
        log.normalization_rules_applied = [
            draw(st.sampled_from([
                "unit_conversion",
                "remove_spaces",
                "lowercase",
                "synonym_replace"
            ]))
        ]
        log.match_result = False
        log.match_failure_reason = "规范化后仍不匹配"
    elif failure_type == "matching":
        log.extracted_answer = draw(st.text(min_size=1, max_size=20))
        log.extraction_confidence = draw(st.floats(min_value=0.7, max_value=1.0))
        log.normalized_answer = log.extracted_answer
        log.match_result = False
        log.match_failure_reason = draw(st.sampled_from([
            "同义词未识别",
            "格式不匹配",
            "答案不完整"
        ]))
    else:  # scoring
        log.extracted_answer = draw(st.text(min_size=1, max_size=20))
        log.extraction_confidence = draw(st.floats(min_value=0.7, max_value=1.0))
        log.normalized_answer = log.extracted_answer
        log.match_result = True
    
    return log


class TestRuleMiningTrigger:
    """规则挖掘触发条件属性测试
    
    **Feature: self-evolving-grading, Property 21: 规则挖掘触发条件**
    **Validates: Requirements 9.1**
    """
    
    @given(
        n_overrides=st.integers(min_value=100, max_value=500)
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_rule_mining_triggered_with_sufficient_samples(
        self,
        n_overrides: int
    ):
        """
        属性：当累积足够的改判样本（>= 100）时，规则挖掘应被触发并返回结果
        
        **Feature: self-evolving-grading, Property 21: 规则挖掘触发条件**
        **Validates: Requirements 9.1**
        """
        # 生成指定数量的改判样本
        override_logs = []
        for _ in range(n_overrides):
            log = GradingLog(
                log_id=str(uuid4()),
                submission_id=str(uuid4()),
                question_id="q1",
                extracted_answer="",
                extraction_confidence=0.3,
                score=0.0,
                max_score=10.0,
                confidence=0.5,
                was_overridden=True,
                override_score=8.0,
                override_reason="提取失败",
                created_at=datetime.utcnow()
            )
            override_logs.append(log)
        
        # 创建规则挖掘器
        rule_miner = RuleMiner(min_frequency=3)
        
        # 执行规则挖掘
        patterns = await rule_miner.analyze_overrides(override_logs)
        
        # 验证：应该触发规则挖掘并返回结果
        # 由于所有样本都是相同的失败模式，应该至少识别出一个模式
        assert patterns is not None, "规则挖掘应该返回结果"
        assert len(patterns) > 0, f"有 {n_overrides} 个改判样本，应该识别出至少一个失败模式"
    
    @given(
        n_overrides=st.integers(min_value=0, max_value=99)
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_rule_mining_with_insufficient_samples(
        self,
        n_overrides: int
    ):
        """
        属性：当改判样本不足（< 100）时，规则挖掘仍应正常执行
        
        注意：需求 9.1 说的是"累积足够的样本"，但没有说样本不足时不能执行。
        这个测试验证系统在样本不足时的行为是否合理。
        
        **Feature: self-evolving-grading, Property 21: 规则挖掘触发条件**
        **Validates: Requirements 9.1**
        """
        # 生成少量改判样本
        override_logs = []
        for _ in range(n_overrides):
            log = GradingLog(
                log_id=str(uuid4()),
                submission_id=str(uuid4()),
                question_id="q1",
                extracted_answer="",
                extraction_confidence=0.3,
                score=0.0,
                max_score=10.0,
                confidence=0.5,
                was_overridden=True,
                override_score=8.0,
                override_reason="提取失败",
                created_at=datetime.utcnow()
            )
            override_logs.append(log)
        
        # 创建规则挖掘器
        rule_miner = RuleMiner(min_frequency=3)
        
        # 执行规则挖掘
        patterns = await rule_miner.analyze_overrides(override_logs)
        
        # 验证：应该正常执行，但可能没有识别出模式（因为样本不足）
        assert patterns is not None, "规则挖掘应该返回结果（即使是空列表）"
        # 如果样本数少于 min_frequency，可能识别不出模式
        if n_overrides < 3:
            assert len(patterns) == 0, "样本数少于 min_frequency 时不应识别出模式"
    
    @given(
        logs=st.lists(
            grading_log_strategy(),
            min_size=100,
            max_size=200
        )
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.large_base_example,
            HealthCheck.data_too_large
        ]
    )
    @pytest.mark.asyncio
    async def test_pattern_identification_with_diverse_failures(
        self,
        logs
    ):
        """
        属性：对于任意的改判样本集合（>= 100），规则挖掘应该能够识别出失败模式
        
        **Feature: self-evolving-grading, Property 21: 规则挖掘触发条件**
        **Validates: Requirements 9.1**
        """
        # 创建规则挖掘器
        rule_miner = RuleMiner(min_frequency=3)
        
        # 执行规则挖掘
        patterns = await rule_miner.analyze_overrides(logs)
        
        # 验证：应该返回结果
        assert patterns is not None
        
        # 验证：所有识别出的模式都应该满足最小频率要求
        for pattern in patterns:
            assert pattern.frequency >= rule_miner.min_frequency, \
                f"模式频率 {pattern.frequency} 应该 >= {rule_miner.min_frequency}"
        
        # 验证：模式应该按频率降序排列
        if len(patterns) > 1:
            for i in range(len(patterns) - 1):
                assert patterns[i].frequency >= patterns[i + 1].frequency, \
                    "模式应该按频率降序排列"
    
    @given(
        n_overrides=st.integers(min_value=100, max_value=300),
        min_frequency=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_frequency_threshold_filtering(
        self,
        n_overrides: int,
        min_frequency: int
    ):
        """
        属性：规则挖掘应该过滤掉频率低于阈值的模式
        
        **Feature: self-evolving-grading, Property 21: 规则挖掘触发条件**
        **Validates: Requirements 9.1**
        """
        # 创建多种失败模式，但频率不同
        override_logs = []
        
        # 高频模式（应该被识别）
        for _ in range(min_frequency + 5):
            log = GradingLog(
                log_id=str(uuid4()),
                submission_id=str(uuid4()),
                question_id="q_high_freq",
                extracted_answer="",
                extraction_confidence=0.3,
                score=0.0,
                max_score=10.0,
                confidence=0.5,
                was_overridden=True,
                override_score=8.0,
                override_reason="高频失败",
                created_at=datetime.utcnow()
            )
            override_logs.append(log)
        
        # 低频模式（应该被过滤）
        for _ in range(min_frequency - 1):
            log = GradingLog(
                log_id=str(uuid4()),
                submission_id=str(uuid4()),
                question_id="q_low_freq",
                extracted_answer="",
                extraction_confidence=0.3,
                score=0.0,
                max_score=10.0,
                confidence=0.5,
                was_overridden=True,
                override_score=8.0,
                override_reason="低频失败",
                created_at=datetime.utcnow()
            )
            override_logs.append(log)
        
        # 填充到指定数量
        while len(override_logs) < n_overrides:
            log = GradingLog(
                log_id=str(uuid4()),
                submission_id=str(uuid4()),
                question_id="q_high_freq",
                extracted_answer="",
                extraction_confidence=0.3,
                score=0.0,
                max_score=10.0,
                confidence=0.5,
                was_overridden=True,
                override_score=8.0,
                override_reason="高频失败",
                created_at=datetime.utcnow()
            )
            override_logs.append(log)
        
        # 创建规则挖掘器
        rule_miner = RuleMiner(min_frequency=min_frequency)
        
        # 执行规则挖掘
        patterns = await rule_miner.analyze_overrides(override_logs)
        
        # 验证：所有识别出的模式频率都应该 >= min_frequency
        for pattern in patterns:
            assert pattern.frequency >= min_frequency, \
                f"模式频率 {pattern.frequency} 应该 >= {min_frequency}"
        
        # 验证：应该识别出高频模式
        high_freq_patterns = [
            p for p in patterns
            if "q_high_freq" in (p.affected_question_types or []) or
               "q_high_freq" in p.description
        ]
        assert len(high_freq_patterns) > 0, "应该识别出高频模式"
        
        # 验证：不应该识别出低频模式
        low_freq_patterns = [
            p for p in patterns
            if "q_low_freq" in (p.affected_question_types or []) or
               "q_low_freq" in p.description
        ]
        assert len(low_freq_patterns) == 0, "不应该识别出低频模式"
    
    @given(
        n_overrides=st.integers(min_value=100, max_value=300)
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_pattern_type_classification(
        self,
        n_overrides: int
    ):
        """
        属性：规则挖掘应该正确分类不同类型的失败模式
        
        **Feature: self-evolving-grading, Property 21: 规则挖掘触发条件**
        **Validates: Requirements 9.1**
        """
        # 创建不同类型的失败样本
        override_logs = []
        
        # 每种类型至少 min_frequency 个
        min_freq = 5
        
        # 提取失败
        for _ in range(min_freq):
            log = GradingLog(
                log_id=str(uuid4()),
                submission_id=str(uuid4()),
                question_id="q1",
                extracted_answer="",
                extraction_confidence=0.2,
                score=0.0,
                max_score=10.0,
                confidence=0.5,
                was_overridden=True,
                override_score=8.0,
                override_reason="提取失败"
            )
            override_logs.append(log)
        
        # 规范化失败
        for _ in range(min_freq):
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
                override_reason="规范化失败"
            )
            override_logs.append(log)
        
        # 匹配失败
        for _ in range(min_freq):
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
                override_reason="匹配失败"
            )
            override_logs.append(log)
        
        # 填充到指定数量
        while len(override_logs) < n_overrides:
            log = GradingLog(
                log_id=str(uuid4()),
                submission_id=str(uuid4()),
                question_id="q1",
                extracted_answer="",
                extraction_confidence=0.2,
                score=0.0,
                max_score=10.0,
                confidence=0.5,
                was_overridden=True,
                override_score=8.0,
                override_reason="提取失败"
            )
            override_logs.append(log)
        
        # 创建规则挖掘器
        rule_miner = RuleMiner(min_frequency=3)
        
        # 执行规则挖掘
        patterns = await rule_miner.analyze_overrides(override_logs)
        
        # 验证：应该识别出多种类型的模式
        pattern_types = {p.pattern_type for p in patterns}
        assert len(pattern_types) >= 2, \
            f"应该识别出至少2种类型的模式，实际识别出 {len(pattern_types)} 种"
        
        # 验证：每个模式都应该有有效的类型
        for pattern in patterns:
            assert pattern.pattern_type in [
                PatternType.EXTRACTION,
                PatternType.NORMALIZATION,
                PatternType.MATCHING,
                PatternType.SCORING
            ], f"模式类型 {pattern.pattern_type} 无效"
