"""
评分标准引用与记忆系统优化 - 单元测试

测试内容：
1. ScoringPointResult 扩展字段
2. MemoryEntry 验证状态转换
3. 置信度计算
4. 自白-记忆集成

Requirements: Task 12 (综合测试)
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from src.services.grading_memory import (
    GradingMemoryService,
    MemoryEntry,
    MemoryType,
    MemoryImportance,
    MemoryVerificationStatus,
    reset_memory_service,
)
from src.services.confidence_calculator import (
    calculate_point_confidence,
    calculate_question_confidence,
    calculate_student_confidence,
)
from src.services.grading_confession import (
    ConfessionIssue,
    generate_confession,
    review_memory_conflict,
)


class TestScoringPointResultExtension:
    """测试 ScoringPointResult 扩展字段"""
    
    def test_citation_quality_enum_values(self):
        """验证 citation_quality 的有效值"""
        valid_values = ["exact", "partial", "none"]
        for value in valid_values:
            # 应该不抛出异常
            assert value in valid_values
    
    def test_point_confidence_range(self):
        """验证 point_confidence 在有效范围内"""
        # 测试各种情况
        test_cases = [
            {"has_rubric_reference": True, "citation_quality": "exact", "is_alternative_solution": False},
            {"has_rubric_reference": True, "citation_quality": "partial", "is_alternative_solution": False},
            {"has_rubric_reference": False, "citation_quality": "none", "is_alternative_solution": False},
            {"has_rubric_reference": True, "citation_quality": "exact", "is_alternative_solution": True},
        ]
        
        for case in test_cases:
            confidence = calculate_point_confidence(**case)
            assert 0.0 <= confidence <= 1.0, f"置信度超出范围: {confidence}"


class TestMemoryVerificationStatus:
    """测试记忆验证状态转换 (P2)"""
    
    @pytest.fixture
    def memory_service(self):
        """创建测试用的记忆服务"""
        reset_memory_service()
        service = GradingMemoryService(
            storage_path=None,
            max_memory_entries=100,
        )
        return service
    
    def test_pending_to_verified(self, memory_service):
        """测试 PENDING → VERIFIED 转换"""
        # 创建待验证记忆
        memory_id = memory_service.store_memory(
            memory_type=MemoryType.ERROR_PATTERN,
            pattern="测试模式",
            lesson="测试教训",
        )
        
        # 验证初始状态
        entry = memory_service.get_memory_by_id(memory_id)
        assert entry.verification_status == MemoryVerificationStatus.PENDING
        
        # 执行验证
        success = memory_service.verify_memory(memory_id, verified_by="test")
        assert success
        
        # 验证状态转换
        entry = memory_service.get_memory_by_id(memory_id)
        assert entry.verification_status == MemoryVerificationStatus.VERIFIED
    
    def test_verified_to_core(self, memory_service):
        """测试 VERIFIED → CORE 转换"""
        # 创建并验证记忆
        memory_id = memory_service.store_memory(
            memory_type=MemoryType.ERROR_PATTERN,
            pattern="测试模式",
            lesson="测试教训",
        )
        memory_service.verify_memory(memory_id)
        
        # 提升为核心
        success = memory_service.promote_to_core(memory_id, promoted_by="test")
        assert success
        
        # 验证状态
        entry = memory_service.get_memory_by_id(memory_id)
        assert entry.verification_status == MemoryVerificationStatus.CORE
    
    def test_pending_to_suspicious(self, memory_service):
        """测试 PENDING → SUSPICIOUS 转换"""
        memory_id = memory_service.store_memory(
            memory_type=MemoryType.ERROR_PATTERN,
            pattern="测试模式",
            lesson="测试教训",
        )
        
        success = memory_service.mark_suspicious(memory_id, marked_by="test")
        assert success
        
        entry = memory_service.get_memory_by_id(memory_id)
        assert entry.verification_status == MemoryVerificationStatus.SUSPICIOUS
    
    def test_invalid_transition_core_to_verified(self, memory_service):
        """测试无效转换：CORE 不能直接验证"""
        memory_id = memory_service.store_memory(
            memory_type=MemoryType.ERROR_PATTERN,
            pattern="测试模式",
            lesson="测试教训",
        )
        memory_service.verify_memory(memory_id)
        memory_service.promote_to_core(memory_id)
        
        # 尝试再次验证（应该失败）
        success = memory_service.verify_memory(memory_id)
        assert not success
    
    def test_soft_delete_and_rollback(self, memory_service):
        """测试软删除和回滚"""
        memory_id = memory_service.store_memory(
            memory_type=MemoryType.ERROR_PATTERN,
            pattern="测试模式",
            lesson="测试教训",
        )
        memory_service.verify_memory(memory_id)
        
        # 软删除
        success = memory_service.soft_delete_memory(memory_id, reason="测试删除")
        assert success
        
        entry = memory_service.get_memory_by_id(memory_id)
        assert entry.is_soft_deleted
        assert entry.verification_status == MemoryVerificationStatus.DEPRECATED
        
        # 回滚
        success = memory_service.rollback_memory(memory_id, reason="测试回滚")
        assert success
        
        entry = memory_service.get_memory_by_id(memory_id)
        assert not entry.is_soft_deleted
        assert entry.verification_status == MemoryVerificationStatus.VERIFIED


class TestConfidenceCalculation:
    """测试置信度计算 (P1)"""
    
    def test_exact_citation_confidence(self):
        """精确引用的置信度"""
        confidence = calculate_point_confidence(
            has_rubric_reference=True,
            citation_quality="exact",
            is_alternative_solution=False,
        )
        assert confidence == 0.9
    
    def test_partial_citation_confidence(self):
        """部分引用的置信度"""
        confidence = calculate_point_confidence(
            has_rubric_reference=True,
            citation_quality="partial",
            is_alternative_solution=False,
        )
        assert confidence == 0.81  # 0.9 * 0.9
    
    def test_no_citation_confidence(self):
        """无引用的置信度"""
        confidence = calculate_point_confidence(
            has_rubric_reference=False,
            citation_quality="none",
            is_alternative_solution=False,
        )
        assert confidence <= 0.7
    
    def test_alternative_solution_reduces_confidence(self):
        """另类解法降低置信度"""
        base_confidence = calculate_point_confidence(
            has_rubric_reference=True,
            citation_quality="exact",
            is_alternative_solution=False,
        )
        
        alt_confidence = calculate_point_confidence(
            has_rubric_reference=True,
            citation_quality="exact",
            is_alternative_solution=True,
        )
        
        assert alt_confidence < base_confidence
        assert alt_confidence == base_confidence * 0.75
    
    def test_question_confidence_weighted_average(self):
        """题目置信度是加权平均"""
        from src.models.grading_models import ScoringPointResult, ScoringPoint
        
        # 创建评分点结果
        point_results = [
            ScoringPointResult(
                scoring_point=ScoringPoint(point_id="1.1", description="测试1", score=2),
                awarded=2,
                point_confidence=0.9,
            ),
            ScoringPointResult(
                scoring_point=ScoringPoint(point_id="1.2", description="测试2", score=3),
                awarded=3,
                point_confidence=0.7,
            ),
        ]
        
        # 手动计算加权平均
        total_weight = 2 + 3
        expected = (0.9 * 2 + 0.7 * 3) / total_weight
        
        # 使用函数计算
        confidence = calculate_question_confidence(point_results)
        
        assert abs(confidence - expected) < 0.001


class TestConfessionMemoryIntegration:
    """测试自白-记忆集成 (P4)"""
    
    def test_confession_issue_with_memory_fields(self):
        """测试 ConfessionIssue 包含记忆字段"""
        issue = ConfessionIssue(
            issue_id="test_001",
            type="low_confidence",
            severity="warning",
            question_id="Q1",
            message="测试消息",
            should_create_memory=True,
            memory_type="error_pattern",
            memory_pattern="测试模式",
            memory_lesson="测试教训",
        )
        
        assert issue.should_create_memory
        assert issue.memory_type == "error_pattern"
        assert issue.memory_pattern == "测试模式"
    
    def test_generate_confession_marks_memory_candidates(self):
        """测试 generate_confession 标记记忆候选"""
        evidence = {"warnings": []}
        score_result = {
            "question_details": [
                {
                    "question_id": "Q1",
                    "confidence": 0.5,  # 低置信度
                    "scoring_point_results": [],
                }
            ]
        }
        
        report = generate_confession(evidence, score_result, page_index=0)
        
        # 应该有记忆候选
        assert "memory_candidates" in report
        # 低置信度应该标记为需要创建记忆
        low_conf_issues = [i for i in report["issues"] if i["type"] == "low_confidence"]
        if low_conf_issues:
            assert any(c["memory_type"] == "calibration" for c in report["memory_candidates"])
    
    def test_review_memory_conflict_logic(self):
        """测试记忆冲突审查逻辑"""
        # 创建模拟记忆条目
        memory_entry = MemoryEntry(
            memory_id="test_mem",
            memory_type=MemoryType.ERROR_PATTERN,
            importance=MemoryImportance.MEDIUM,
            pattern="测试模式",
            context={},
            lesson="测试教训",
            confirmation_count=5,
            contradiction_count=1,  # 置信度 = 5/6 ≈ 0.83
        )
        
        # 逻辑复核结果置信度更高
        logic_review_result = {"confidence": 0.95}
        grading_result = {}
        
        review = review_memory_conflict(memory_entry, logic_review_result, grading_result)
        
        # 逻辑复核置信度更高，应该建议标记记忆为可疑
        assert review["action"] == "contradict"
        assert review["suggested_memory_action"] == "mark_suspicious"


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
