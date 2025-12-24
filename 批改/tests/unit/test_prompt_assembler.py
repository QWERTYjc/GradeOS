"""
单元测试：PromptAssembler 服务

测试提示词拼装器的各项功能。
"""

import pytest
from pathlib import Path

from src.services.prompt_assembler import PromptAssembler
from src.models.prompt import PromptSection, AssembledPrompt
from src.models.exemplar import Exemplar
from datetime import datetime


@pytest.fixture
def assembler():
    """创建 PromptAssembler 实例"""
    return PromptAssembler()


@pytest.fixture
def sample_exemplars():
    """创建示例判例"""
    return [
        Exemplar(
            exemplar_id="ex1",
            question_type="objective",
            question_image_hash="hash1",
            student_answer_text="A",
            score=5.0,
            max_score=5.0,
            teacher_feedback="答案正确",
            teacher_id="teacher1",
            confirmed_at=datetime.now(),
            usage_count=10,
            embedding=None
        ),
        Exemplar(
            exemplar_id="ex2",
            question_type="objective",
            question_image_hash="hash2",
            student_answer_text="B",
            score=0.0,
            max_score=5.0,
            teacher_feedback="答案错误，正确答案是 A",
            teacher_id="teacher1",
            confirmed_at=datetime.now(),
            usage_count=5,
            embedding=None
        )
    ]


class TestErrorGuidance:
    """测试错误模式引导功能"""
    
    def test_add_error_guidance_with_patterns(self, assembler):
        """
        测试添加错误模式引导
        
        验证：需求 5.2
        """
        error_patterns = [
            "学生经常混淆 A 和 B 选项",
            "注意单位换算错误",
            "计算过程中的符号错误"
        ]
        
        guidance = assembler.add_error_guidance(error_patterns)
        
        # 验证包含标题
        assert "常见错误提示" in guidance
        
        # 验证包含所有错误模式
        for pattern in error_patterns:
            assert pattern in guidance
        
        # 验证格式正确（有编号）
        assert "1." in guidance
        assert "2." in guidance
        assert "3." in guidance
    
    def test_add_error_guidance_empty_list(self, assembler):
        """测试空错误模式列表"""
        guidance = assembler.add_error_guidance([])
        
        # 空列表应返回空字符串
        assert guidance == ""
    
    def test_add_error_guidance_single_pattern(self, assembler):
        """测试单个错误模式"""
        error_patterns = ["注意单位换算"]
        
        guidance = assembler.add_error_guidance(error_patterns)
        
        assert "常见错误提示" in guidance
        assert "注意单位换算" in guidance
        assert "1." in guidance


class TestDetailedReasoningPrompt:
    """测试详细推理提示功能"""
    
    def test_add_detailed_reasoning_low_confidence(self, assembler):
        """
        测试低置信度时添加详细推理提示
        
        验证：需求 5.3
        """
        # 低置信度（< 0.85）
        prompt = assembler.add_detailed_reasoning_prompt(0.7)
        
        # 验证包含详细推理要求
        assert "详细推理要求" in prompt
        assert "详细记录推理过程" in prompt
        assert "reasoning_trace" in prompt
        assert "不确定因素" in prompt
    
    def test_add_detailed_reasoning_high_confidence(self, assembler):
        """测试高置信度时不添加详细推理提示"""
        # 高置信度（>= 0.85）
        prompt = assembler.add_detailed_reasoning_prompt(0.9)
        
        # 应返回空字符串
        assert prompt == ""
    
    def test_add_detailed_reasoning_threshold(self, assembler):
        """测试置信度阈值边界"""
        # 刚好低于阈值
        prompt_below = assembler.add_detailed_reasoning_prompt(0.84)
        assert len(prompt_below) > 0
        
        # 刚好达到阈值
        prompt_at = assembler.add_detailed_reasoning_prompt(0.85)
        assert prompt_at == ""
        
        # 高于阈值
        prompt_above = assembler.add_detailed_reasoning_prompt(0.86)
        assert prompt_above == ""


class TestExemplarFormatting:
    """测试判例格式化功能"""
    
    def test_format_exemplars_with_data(self, assembler, sample_exemplars):
        """
        测试格式化判例
        
        验证：需求 5.4
        """
        formatted = assembler.format_exemplars(sample_exemplars)
        
        # 验证包含标题
        assert "参考判例" in formatted
        
        # 验证包含所有判例信息
        for exemplar in sample_exemplars:
            assert exemplar.student_answer_text in formatted
            assert exemplar.teacher_feedback in formatted
            assert str(exemplar.score) in formatted
            assert str(exemplar.max_score) in formatted
    
    def test_format_exemplars_empty_list(self, assembler):
        """测试空判例列表"""
        formatted = assembler.format_exemplars([])
        
        # 空列表应返回空字符串
        assert formatted == ""
    
    def test_format_exemplars_numbering(self, assembler, sample_exemplars):
        """测试判例编号"""
        formatted = assembler.format_exemplars(sample_exemplars)
        
        # 验证有编号
        assert "示例 1" in formatted
        assert "示例 2" in formatted


class TestTokenEstimation:
    """测试 Token 估算功能"""
    
    def test_estimate_tokens_chinese(self, assembler):
        """测试中文文本的 token 估算"""
        text = "这是一段中文文本，用于测试 token 估算功能。"
        tokens = assembler._estimate_tokens(text)
        
        # 验证估算合理（中文约 4 字符 = 1 token）
        expected_tokens = len(text) // 4
        assert tokens == expected_tokens
    
    def test_estimate_tokens_empty(self, assembler):
        """测试空文本"""
        tokens = assembler._estimate_tokens("")
        assert tokens == 0


class TestCalibrationFormatting:
    """测试校准配置格式化"""
    
    def test_format_calibration_with_rules(self, assembler):
        """测试格式化校准配置"""
        calibration = {
            "deduction_rules": {
                "计算错误": 2.0,
                "单位错误": 1.0
            },
            "tolerance_rules": [
                {"rule_type": "numeric", "description": "数值容差 ±0.1"},
                {"rule_type": "unit", "description": "单位自动换算"}
            ],
            "strictness_level": 0.5
        }
        
        formatted = assembler._format_calibration(calibration)
        
        # 验证包含各部分
        assert "个性化校准配置" in formatted
        assert "扣分规则" in formatted
        assert "容差设置" in formatted
        assert "评分严格程度" in formatted
        
        # 验证具体内容
        assert "计算错误" in formatted
        assert "2.0" in formatted
        assert "数值容差" in formatted
    
    def test_format_calibration_empty(self, assembler):
        """测试空校准配置"""
        formatted = assembler._format_calibration({})
        assert formatted == ""
    
    def test_format_calibration_strictness_levels(self, assembler):
        """测试不同严格程度的描述"""
        # 宽松
        formatted_loose = assembler._format_calibration({"strictness_level": 0.2})
        assert "宽松" in formatted_loose
        
        # 适中
        formatted_medium = assembler._format_calibration({"strictness_level": 0.5})
        assert "适中" in formatted_medium
        
        # 严格
        formatted_strict = assembler._format_calibration({"strictness_level": 0.8})
        assert "严格" in formatted_strict


class TestAssemble:
    """测试完整拼装功能"""
    
    def test_assemble_basic(self, assembler):
        """测试基本拼装"""
        result = assembler.assemble(
            question_type="objective",
            rubric="选择题评分标准：正确得 5 分，错误得 0 分"
        )
        
        # 验证返回类型
        assert isinstance(result, AssembledPrompt)
        
        # 验证包含必需区段
        assert PromptSection.SYSTEM in result.sections
        assert PromptSection.RUBRIC in result.sections
        
        # 验证 token 数合理
        assert result.total_tokens > 0
        
        # 验证没有截断
        assert len(result.truncated_sections) == 0
    
    def test_assemble_with_exemplars(self, assembler, sample_exemplars):
        """测试包含判例的拼装"""
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准",
            exemplars=sample_exemplars
        )
        
        # 验证包含判例区段
        assert PromptSection.EXEMPLARS in result.sections
        
        # 验证判例内容
        exemplar_text = result.sections[PromptSection.EXEMPLARS]
        assert "参考判例" in exemplar_text
    
    def test_assemble_with_error_patterns(self, assembler):
        """测试包含错误模式的拼装"""
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准",
            error_patterns=["常见错误1", "常见错误2"]
        )
        
        # 验证包含错误引导区段
        assert PromptSection.ERROR_GUIDANCE in result.sections
    
    def test_assemble_with_low_confidence(self, assembler):
        """测试低置信度时的拼装"""
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准",
            previous_confidence=0.7
        )
        
        # 验证包含详细推理区段
        assert PromptSection.DETAILED_REASONING in result.sections
    
    def test_assemble_with_calibration(self, assembler):
        """测试包含校准配置的拼装"""
        calibration = {
            "deduction_rules": {"错误": 1.0},
            "strictness_level": 0.5
        }
        
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准",
            calibration=calibration
        )
        
        # 验证包含校准区段
        assert PromptSection.CALIBRATION in result.sections
    
    def test_assemble_full_prompt(self, assembler):
        """测试获取完整提示词"""
        result = assembler.assemble(
            question_type="objective",
            rubric="评分标准"
        )
        
        # 拼接所有区段内容
        full_prompt = "\n\n".join(result.sections.values())
        
        # 验证是字符串
        assert isinstance(full_prompt, str)
        
        # 验证包含各区段内容
        assert len(full_prompt) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
