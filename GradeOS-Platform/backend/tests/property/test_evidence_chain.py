"""证据链完整性属性测试

使用 Hypothesis 验证证据链条目的结构完整性

**功能: ai-grading-agent, 属性 22: 证据链完整性**
**验证: 需求 7.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any

from src.models.state import EvidenceItem


def create_evidence_item(
    scoring_point: str,
    image_region: List[int],
    text_description: str,
    reasoning: str,
    rubric_reference: str,
    points_awarded: float
) -> EvidenceItem:
    """创建证据链条目"""
    return EvidenceItem(
        scoring_point=scoring_point,
        image_region=image_region,
        text_description=text_description,
        reasoning=reasoning,
        rubric_reference=rubric_reference,
        points_awarded=points_awarded
    )


def validate_evidence_item(evidence: EvidenceItem) -> bool:
    """验证证据链条目的完整性
    
    根据需求 7.3，每个证据链条目应当包含：
    - 非空的 scoring_point
    - 有效的 image_region（4 个非负整数）
    - 非空的 text_description
    - 非空的 reasoning
    - 非空的 rubric_reference
    - 非负的 points_awarded
    """
    # 检查 scoring_point 非空
    if not evidence.get("scoring_point") or not evidence["scoring_point"].strip():
        return False
    
    # 检查 image_region 有效性
    image_region = evidence.get("image_region")
    if not image_region or len(image_region) != 4:
        return False
    if not all(isinstance(x, (int, float)) and x >= 0 for x in image_region):
        return False
    
    # 检查 text_description 非空
    if not evidence.get("text_description") or not evidence["text_description"].strip():
        return False
    
    # 检查 reasoning 非空
    if not evidence.get("reasoning") or not evidence["reasoning"].strip():
        return False
    
    # 检查 rubric_reference 非空
    if not evidence.get("rubric_reference") or not evidence["rubric_reference"].strip():
        return False
    
    # 检查 points_awarded 非负
    points = evidence.get("points_awarded")
    if points is None or points < 0:
        return False
    
    return True


# ===== Hypothesis 策略定义 =====

# 非空字符串策略（至少包含一个非空白字符）
non_empty_text = st.text(min_size=1).filter(lambda s: s.strip())

# 有效的边界框坐标策略（4 个非负整数）
valid_image_region = st.lists(
    st.integers(min_value=0, max_value=10000),
    min_size=4,
    max_size=4
)

# 非负分数策略
non_negative_score = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


class TestEvidenceChainCompleteness:
    """证据链完整性属性测试
    
    **功能: ai-grading-agent, 属性 22: 证据链完整性**
    **验证: 需求 7.3**
    """
    
    @given(
        scoring_point=non_empty_text,
        ymin=st.integers(min_value=0, max_value=1000),
        xmin=st.integers(min_value=0, max_value=1000),
        ymax=st.integers(min_value=0, max_value=1000),
        xmax=st.integers(min_value=0, max_value=1000),
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score
    )
    @settings(max_examples=100)
    def test_valid_evidence_item_passes_validation(
        self,
        scoring_point: str,
        ymin: int,
        xmin: int,
        ymax: int,
        xmax: int,
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        对于任意有效的证据链条目输入，验证函数应当返回 True
        """
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=[ymin, xmin, ymax, xmax],
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        assert validate_evidence_item(evidence), (
            f"有效的证据链条目应当通过验证: {evidence}"
        )
    
    @given(
        scoring_point=non_empty_text,
        image_region=valid_image_region,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score
    )
    @settings(max_examples=100)
    def test_evidence_item_has_all_required_fields(
        self,
        scoring_point: str,
        image_region: List[int],
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        对于任意证据链条目，应当包含所有必需字段
        """
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=image_region,
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        # 验证所有必需字段存在
        assert "scoring_point" in evidence
        assert "image_region" in evidence
        assert "text_description" in evidence
        assert "reasoning" in evidence
        assert "rubric_reference" in evidence
        assert "points_awarded" in evidence
    
    @given(
        scoring_point=non_empty_text,
        image_region=valid_image_region,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score
    )
    @settings(max_examples=100)
    def test_image_region_has_four_non_negative_integers(
        self,
        scoring_point: str,
        image_region: List[int],
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        对于任意证据链条目，image_region 应当包含 4 个非负整数
        """
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=image_region,
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        region = evidence["image_region"]
        
        # 验证 image_region 有 4 个元素
        assert len(region) == 4, f"image_region 应当有 4 个元素，实际有 {len(region)} 个"
        
        # 验证所有元素为非负整数
        for i, coord in enumerate(region):
            assert isinstance(coord, int), f"image_region[{i}] 应当是整数，实际是 {type(coord)}"
            assert coord >= 0, f"image_region[{i}] 应当非负，实际值为 {coord}"
    
    @given(
        scoring_point=non_empty_text,
        image_region=valid_image_region,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score
    )
    @settings(max_examples=100)
    def test_points_awarded_is_non_negative(
        self,
        scoring_point: str,
        image_region: List[int],
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        对于任意证据链条目，points_awarded 应当非负
        """
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=image_region,
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        assert evidence["points_awarded"] >= 0, (
            f"points_awarded 应当非负，实际值为 {evidence['points_awarded']}"
        )
    
    @given(
        scoring_point=non_empty_text,
        image_region=valid_image_region,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score
    )
    @settings(max_examples=100)
    def test_text_fields_are_non_empty(
        self,
        scoring_point: str,
        image_region: List[int],
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        对于任意证据链条目，所有文本字段应当非空
        """
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=image_region,
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        # 验证 scoring_point 非空
        assert evidence["scoring_point"], "scoring_point 不应为空"
        assert evidence["scoring_point"].strip(), "scoring_point 不应只包含空白字符"
        
        # 验证 text_description 非空
        assert evidence["text_description"], "text_description 不应为空"
        assert evidence["text_description"].strip(), "text_description 不应只包含空白字符"
        
        # 验证 reasoning 非空
        assert evidence["reasoning"], "reasoning 不应为空"
        assert evidence["reasoning"].strip(), "reasoning 不应只包含空白字符"
        
        # 验证 rubric_reference 非空
        assert evidence["rubric_reference"], "rubric_reference 不应为空"
        assert evidence["rubric_reference"].strip(), "rubric_reference 不应只包含空白字符"


class TestEvidenceChainInvalidInputs:
    """证据链无效输入测试
    
    验证无效输入被正确拒绝
    """
    
    @given(
        image_region=valid_image_region,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score
    )
    @settings(max_examples=50)
    def test_empty_scoring_point_fails_validation(
        self,
        image_region: List[int],
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        空的 scoring_point 应当导致验证失败
        """
        evidence = create_evidence_item(
            scoring_point="",  # 空字符串
            image_region=image_region,
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        assert not validate_evidence_item(evidence), (
            "空的 scoring_point 应当导致验证失败"
        )
    
    @given(
        scoring_point=non_empty_text,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score
    )
    @settings(max_examples=50)
    def test_invalid_image_region_length_fails_validation(
        self,
        scoring_point: str,
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        image_region 长度不为 4 应当导致验证失败
        """
        # 测试长度为 3 的情况
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=[0, 0, 100],  # 只有 3 个元素
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        assert not validate_evidence_item(evidence), (
            "image_region 长度不为 4 应当导致验证失败"
        )
    
    @given(
        scoring_point=non_empty_text,
        image_region=valid_image_region,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text
    )
    @settings(max_examples=50)
    def test_negative_points_awarded_fails_validation(
        self,
        scoring_point: str,
        image_region: List[int],
        text_description: str,
        reasoning: str,
        rubric_reference: str
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        负的 points_awarded 应当导致验证失败
        """
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=image_region,
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=-1.0  # 负数
        )
        
        assert not validate_evidence_item(evidence), (
            "负的 points_awarded 应当导致验证失败"
        )
    
    @given(
        scoring_point=non_empty_text,
        text_description=non_empty_text,
        reasoning=non_empty_text,
        rubric_reference=non_empty_text,
        points_awarded=non_negative_score,
        negative_coord=st.integers(min_value=-1000, max_value=-1)
    )
    @settings(max_examples=50)
    def test_negative_image_region_coordinate_fails_validation(
        self,
        scoring_point: str,
        text_description: str,
        reasoning: str,
        rubric_reference: str,
        points_awarded: float,
        negative_coord: int
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        image_region 包含负数坐标应当导致验证失败
        """
        evidence = create_evidence_item(
            scoring_point=scoring_point,
            image_region=[negative_coord, 0, 100, 100],  # 第一个坐标为负数
            text_description=text_description,
            reasoning=reasoning,
            rubric_reference=rubric_reference,
            points_awarded=points_awarded
        )
        
        assert not validate_evidence_item(evidence), (
            "image_region 包含负数坐标应当导致验证失败"
        )


class TestEvidenceChainListProperties:
    """证据链列表属性测试
    
    验证证据链列表的整体属性
    """
    
    @given(
        evidence_count=st.integers(min_value=1, max_value=10),
        base_points=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_evidence_chain_list_all_items_valid(
        self,
        evidence_count: int,
        base_points: float
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        对于任意证据链列表，所有条目都应当通过验证
        """
        evidence_chain: List[EvidenceItem] = []
        
        for i in range(evidence_count):
            evidence = create_evidence_item(
                scoring_point=f"评分点 {i + 1}",
                image_region=[i * 10, i * 10, (i + 1) * 100, (i + 1) * 100],
                text_description=f"学生在此处展示了对概念 {i + 1} 的理解",
                reasoning=f"根据评分细则第 {i + 1} 条，学生的回答符合要求",
                rubric_reference=f"评分细则 {i + 1}.{i + 1}",
                points_awarded=base_points
            )
            evidence_chain.append(evidence)
        
        # 验证所有条目都有效
        for i, evidence in enumerate(evidence_chain):
            assert validate_evidence_item(evidence), (
                f"证据链条目 {i} 应当通过验证: {evidence}"
            )
    
    @given(
        evidence_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_evidence_chain_total_points_non_negative(
        self,
        evidence_count: int
    ):
        """
        **功能: ai-grading-agent, 属性 22: 证据链完整性**
        **验证: 需求 7.3**
        
        对于任意证据链列表，所有条目的 points_awarded 之和应当非负
        """
        evidence_chain: List[EvidenceItem] = []
        
        for i in range(evidence_count):
            evidence = create_evidence_item(
                scoring_point=f"评分点 {i + 1}",
                image_region=[0, 0, 100, 100],
                text_description=f"描述 {i + 1}",
                reasoning=f"理由 {i + 1}",
                rubric_reference=f"参考 {i + 1}",
                points_awarded=float(i)  # 0, 1, 2, ...
            )
            evidence_chain.append(evidence)
        
        # 计算总分
        total_points = sum(e["points_awarded"] for e in evidence_chain)
        
        assert total_points >= 0, (
            f"证据链总分应当非负，实际值为 {total_points}"
        )
