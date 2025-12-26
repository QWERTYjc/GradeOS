"""
属性测试：提示词模板选择正确性

**Feature: self-evolving-grading, Property 11: 提示词模板选择正确性**
**Validates: Requirements 5.1**

测试对于任意题目类型，加载的基础模板应与该题型匹配。
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase
from pathlib import Path

from src.services.prompt_assembler import PromptAssembler
from src.models.prompt import PromptSection


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)
settings.load_profile("ci")


# 已知的题型列表
KNOWN_QUESTION_TYPES = ["objective", "stepwise", "essay"]


@given(question_type=st.sampled_from(KNOWN_QUESTION_TYPES))
@settings(max_examples=100)
def test_template_selection_correctness(question_type: str):
    """
    **Feature: self-evolving-grading, Property 11: 提示词模板选择正确性**
    **Validates: Requirements 5.1**
    
    属性：对于任意题目类型，加载的基础模板应与该题型匹配。
    
    验证：
    1. 模板文件存在
    2. 模板内容非空
    3. 模板内容包含题型相关的关键词
    """
    # 创建 PromptAssembler 实例
    assembler = PromptAssembler()
    
    # 加载模板
    template = assembler.load_base_template(question_type)
    
    # 验证 1：模板内容非空
    assert template, f"题型 {question_type} 的模板内容为空"
    assert len(template) > 0, f"题型 {question_type} 的模板长度为 0"
    
    # 验证 2：模板包含题型相关的关键词
    # 根据题型检查特定关键词
    if question_type == "objective":
        # 客观题应包含"答案识别"、"匹配"等关键词
        assert any(keyword in template for keyword in ["答案识别", "匹配", "客观题"]), \
            f"客观题模板缺少关键词"
    
    elif question_type == "stepwise":
        # 解答题应包含"步骤"、"逻辑"等关键词
        assert any(keyword in template for keyword in ["步骤", "逻辑", "解答题", "计算"]), \
            f"解答题模板缺少关键词"
    
    elif question_type == "essay":
        # 论述题应包含"论述"、"要点"等关键词
        assert any(keyword in template for keyword in ["论述", "要点", "内容", "逻辑"]), \
            f"论述题模板缺少关键词"
    
    # 验证 3：模板包含输出格式说明
    assert "JSON" in template or "json" in template, \
        f"题型 {question_type} 的模板缺少 JSON 格式说明"


def test_template_caching():
    """
    测试模板缓存功能
    
    验证：
    1. 第一次加载从文件读取
    2. 第二次加载从缓存读取
    3. 缓存内容与文件内容一致
    """
    assembler = PromptAssembler()
    
    # 第一次加载
    template1 = assembler.load_base_template("objective")
    
    # 第二次加载（应从缓存）
    template2 = assembler.load_base_template("objective")
    
    # 验证内容一致
    assert template1 == template2, "缓存的模板内容与原始内容不一致"
    
    # 验证缓存中存在
    assert "objective" in assembler._template_cache, "模板未被缓存"


def test_template_not_found():
    """
    测试不存在的模板
    
    验证：
    1. 加载不存在的模板应抛出 FileNotFoundError
    """
    assembler = PromptAssembler()
    
    with pytest.raises(FileNotFoundError):
        assembler.load_base_template("nonexistent_type")


@given(
    question_type=st.sampled_from(KNOWN_QUESTION_TYPES),
    load_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=50)
def test_template_idempotence(question_type: str, load_count: int):
    """
    测试模板加载的幂等性
    
    属性：多次加载同一模板应返回相同内容
    """
    assembler = PromptAssembler()
    
    # 多次加载
    templates = [assembler.load_base_template(question_type) for _ in range(load_count)]
    
    # 验证所有加载的内容相同
    assert all(t == templates[0] for t in templates), \
        f"多次加载题型 {question_type} 的模板返回了不同内容"


def test_all_known_templates_exist():
    """
    测试所有已知题型的模板都存在
    
    验证：
    1. 所有已知题型都有对应的模板文件
    2. 所有模板文件都可以成功加载
    """
    assembler = PromptAssembler()
    
    for question_type in KNOWN_QUESTION_TYPES:
        # 应该能成功加载
        template = assembler.load_base_template(question_type)
        
        # 验证模板非空
        assert template, f"题型 {question_type} 的模板为空"
        assert len(template) > 100, f"题型 {question_type} 的模板过短（< 100 字符）"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
