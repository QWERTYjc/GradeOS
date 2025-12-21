"""
单元测试：提示词截断功能

测试提示词拼装器的截断和优先级处理。
验证：需求 5.4, 5.5
"""

import pytest
from src.services.prompt_assembler import PromptAssembler
from src.models.prompt import PromptSection, AssembledPrompt
from src.models.exemplar import Exemplar
from datetime import datetime


@pytest.fixture
def assembler():
    """创建 PromptAssembler 实例"""
    return PromptAssembler()


@pytest.fixture
def large_exemplars():
    """创建大量判例用于测试截断"""
    exemplars = []
    for i in range(20):
        exemplars.append(
            Exemplar(
                exemplar_id=f"ex{i}",
                question_type="objective",
                question_image_hash=f"hash{i}",
                student_answer_text=f"这是一个很长的学生答案，包含了大量的文字内容，用于测试截断功能。答案编号：{i}",
                score=float(i % 10),
                max_score=10.0,
                teacher_feedback=f"这是一个详细的教师评语，包含了对学生答案的全面分析和建议。评语编号：{i}",
                teacher_id="teacher1",
                confirmed_at=datetime.now(),
                usage_count=i,
                embedding=None
            )
        )
    return exemplars


class TestTruncation:
    """测试截断功能"""
    
    def test_no_truncation_when_under_limit(self, assembler):
        """
        测试在限制内不截断
        
        验证：需求 5.5
        """
        result = assembler.assemble(
            question_type="objective",
            rubric="简短的评分标准",
            max_tokens=10000  # 很大的限制
        )
        
        # 验证没有截断
        assert len(result.truncated_sections) == 0
        
        # 验证 token 数小于限制
        assert result.total_tokens < 10000
    
    def test_truncation_when_over_limit(self, assembler, large_exemplars):
        """
        测试超过限制时截断
        
        验证：需求 5.5
        """
        # 创建一个很长的评分标准
        long_rubric = "评分标准：" + "这是一个很长的评分标准。" * 1000
        
        result = assembler.assemble(
            question_type="objective",
            rubric=long_rubric,
            exemplars=large_exemplars,
            error_patterns=["错误1", "错误2"] * 50,
            max_tokens=1000  # 较小的限制
        )
        
        # 验证发生了截断
        assert len(result.truncated_sections) > 0
        
        # 验证 token 数接近限制
        assert result.total_tokens <= 1000
    
    def test_truncation_priority_order(self, assembler, large_exemplars):
        """
        测试截断优先级顺序
        
        验证：需求 5.5
        属性 12：提示词截断优先级
        
        优先级（从高到低）：
        SYSTEM > RUBRIC > EXEMPLARS > ERROR_GUIDANCE > DETAILED_REASONING > CALIBRATION
        """
        # 创建所有区段都很长的情况
        long_rubric = "评分标准：" + "内容" * 500
        error_patterns = [f"错误模式{i}" for i in range(100)]
        calibration = {
            "deduction_rules": {f"错误{i}": float(i) for i in range(100)},
            "strictness_level": 0.5
        }
        
        result = assembler.assemble(
            question_type="objective",
            rubric=long_rubric,
            exemplars=large_exemplars,
            error_patterns=error_patterns,
            previous_confidence=0.7,  # 触发详细推理
            calibration=calibration,
            max_tokens=500  # 很小的限制
        )
        
        # 验证高优先级区段被保留
        assert PromptSection.SYSTEM in result.sections, "SYSTEM 区段应该被保留"
        assert PromptSection.RUBRIC in result.sections, "RUBRIC 区段应该被保留"
        
        # 验证低优先级区段可能被截断
        # 注意：具体哪些被截断取决于内容大小，但应该遵循优先级
        if result.truncated_sections:
            # 如果有截断，检查优先级
            priority_map = {
                PromptSection.SYSTEM: 0,
                PromptSection.RUBRIC: 1,
                PromptSection.EXEMPLARS: 2,
                PromptSection.ERROR_GUIDANCE: 3,
                PromptSection.DETAILED_REASONING: 4,
                PromptSection.CALIBRATION: 5
            }
            
            # 被截断的区段应该是低优先级的
            for truncated in result.truncated_sections:
                # 被截断的区段优先级应该 >= 某个阈值
                assert priority_map[truncated] >= 2, \
                    f"高优先级区段 {truncated} 不应该被截断"
    
    def test_truncation_preserves_system_and_rubric(self, assembler, large_exemplars):
        """
        测试截断时始终保留 SYSTEM 和 RUBRIC
        
        验证：需求 5.5
        """
        # 极小的限制
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准",
            exemplars=large_exemplars,
            max_tokens=200
        )
        
        # 验证 SYSTEM 和 RUBRIC 始终存在
        assert PromptSection.SYSTEM in result.sections
        assert PromptSection.RUBRIC in result.sections
    
    def test_truncation_marker(self, assembler):
        """测试截断标记"""
        # 创建一个会被截断的长文本
        long_rubric = "评分标准：" + "这是一个很长的评分标准。" * 1000
        
        result = assembler.assemble(
            question_type="objective",
            rubric=long_rubric,
            max_tokens=300
        )
        
        # 如果 RUBRIC 被截断，应该有截断标记
        if PromptSection.RUBRIC in result.truncated_sections:
            rubric_text = result.sections.get(PromptSection.RUBRIC, "")
            assert "[内容已截断...]" in rubric_text


class TestAssembleIntegration:
    """测试完整拼装的集成场景"""
    
    def test_assemble_all_sections(self, assembler, large_exemplars):
        """
        测试包含所有区段的拼装
        
        验证：需求 5.4
        """
        calibration = {
            "deduction_rules": {"计算错误": 2.0},
            "strictness_level": 0.5
        }
        
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准：正确得分，错误不得分",
            exemplars=large_exemplars[:3],  # 只用 3 个判例
            error_patterns=["常见错误1", "常见错误2"],
            previous_confidence=0.7,
            calibration=calibration,
            max_tokens=5000
        )
        
        # 验证所有区段都存在
        assert PromptSection.SYSTEM in result.sections
        assert PromptSection.RUBRIC in result.sections
        assert PromptSection.EXEMPLARS in result.sections
        assert PromptSection.ERROR_GUIDANCE in result.sections
        assert PromptSection.DETAILED_REASONING in result.sections
        assert PromptSection.CALIBRATION in result.sections
        
        # 验证可以获取完整提示词
        full_prompt = result.get_full_prompt()
        assert len(full_prompt) > 0
        
        # 验证各区段内容都在完整提示词中
        for section_text in result.sections.values():
            if section_text:
                # 至少部分内容应该在完整提示词中
                assert any(part in full_prompt for part in section_text.split()[:5])
    
    def test_assemble_minimal(self, assembler):
        """测试最小配置的拼装"""
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准"
        )
        
        # 验证至少有基本区段
        assert PromptSection.SYSTEM in result.sections
        assert PromptSection.RUBRIC in result.sections
        
        # 验证可以获取完整提示词
        full_prompt = result.get_full_prompt()
        assert len(full_prompt) > 0
    
    def test_get_full_prompt_order(self, assembler):
        """测试完整提示词的区段顺序"""
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准",
            error_patterns=["错误1"],
            previous_confidence=0.7
        )
        
        full_prompt = result.get_full_prompt()
        
        # 验证顺序：SYSTEM 应该在最前面
        system_text = result.sections[PromptSection.SYSTEM]
        system_start = full_prompt.find(system_text[:50])  # 查找前 50 个字符
        
        # RUBRIC 应该在 SYSTEM 之后
        rubric_text = result.sections[PromptSection.RUBRIC]
        rubric_start = full_prompt.find(rubric_text[:20])
        
        assert system_start < rubric_start, "SYSTEM 应该在 RUBRIC 之前"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
