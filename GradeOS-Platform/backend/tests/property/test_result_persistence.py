"""结果持久化完整性属性测试

使用 Hypothesis 验证批改结果持久化的完整性

**功能: ai-grading-agent, 属性 13: 结果持久化完整性**
**验证: 需求 7.1, 7.2, 7.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Optional
import json


def create_grading_result(
    score: float,
    max_score: float,
    confidence_score: float,
    visual_annotations: List[Dict[str, Any]],
    agent_trace: Dict[str, Any]
) -> Dict[str, Any]:
    """创建批改结果记录"""
    return {
        "score": score,
        "max_score": max_score,
        "confidence_score": confidence_score,
        "visual_annotations": visual_annotations,
        "agent_trace": agent_trace
    }


def validate_grading_result_persistence(result: Dict[str, Any]) -> bool:
    """验证批改结果持久化的完整性
    
    根据属性 13 和需求 7.1, 7.2, 7.3，持久化记录应当包含：
    - 有效的 score 和 max_score 值
    - 介于 0.0 和 1.0 之间的 confidence_score
    - 作为有效 JSONB 的 visual_annotations，包含边界框坐标
    - 作为有效 JSONB 的 agent_trace，包含 vision_analysis、reasoning_trace 和 critique 字段
    """
    # 检查 score 有效性
    score = result.get("score")
    if score is None or not isinstance(score, (int, float)):
        return False
    if score < 0:
        return False
    
    # 检查 max_score 有效性
    max_score = result.get("max_score")
    if max_score is None or not isinstance(max_score, (int, float)):
        return False
    if max_score < 0:
        return False
    
    # 检查 score 不超过 max_score
    if score > max_score:
        return False
    
    # 检查 confidence_score 在 [0.0, 1.0] 范围内
    confidence = result.get("confidence_score")
    if confidence is None or not isinstance(confidence, (int, float)):
        return False
    if confidence < 0.0 or confidence > 1.0:
        return False
    
    # 检查 visual_annotations 是有效的 JSONB（列表）
    annotations = result.get("visual_annotations")
    if annotations is None or not isinstance(annotations, list):
        return False
    
    # 验证每个标注包含边界框坐标
    for annotation in annotations:
        if not isinstance(annotation, dict):
            return False
        bbox = annotation.get("bounding_box")
        if bbox is None:
            return False
        # 边界框应包含 ymin, xmin, ymax, xmax
        required_keys = ["ymin", "xmin", "ymax", "xmax"]
        if not all(key in bbox for key in required_keys):
            return False
        # 所有坐标应为非负数
        if not all(isinstance(bbox[key], (int, float)) and bbox[key] >= 0 for key in required_keys):
            return False
    
    # 检查 agent_trace 是有效的 JSONB（字典）
    trace = result.get("agent_trace")
    if trace is None or not isinstance(trace, dict):
        return False
    
    # agent_trace 应包含 vision_analysis、reasoning_trace 和 critique 字段
    if "vision_analysis" not in trace:
        return False
    if "reasoning_trace" not in trace:
        return False
    if "critique" not in trace:
        return False
    
    return True


def is_valid_jsonb(data: Any) -> bool:
    """检查数据是否可以序列化为有效的 JSONB"""
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False


# ===== Hypothesis 策略定义 =====

# 有效的分数策略
valid_score = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# 有效的置信度策略 [0.0, 1.0]
valid_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# 有效的边界框坐标策略
valid_bbox_coord = st.integers(min_value=0, max_value=10000)

# 有效的边界框策略
valid_bounding_box = st.fixed_dictionaries({
    "ymin": valid_bbox_coord,
    "xmin": valid_bbox_coord,
    "ymax": valid_bbox_coord,
    "xmax": valid_bbox_coord
})

# 有效的视觉标注策略
valid_annotation = st.fixed_dictionaries({
    "type": st.sampled_from(["error", "correct", "partial", "highlight"]),
    "bounding_box": valid_bounding_box,
    "message": st.text(min_size=0, max_size=200)
})

# 有效的视觉标注列表策略
valid_visual_annotations = st.lists(valid_annotation, min_size=0, max_size=10)

# 非空文本策略
non_empty_text = st.text(min_size=1, max_size=500).filter(lambda s: s.strip())

# 有效的推理步骤列表策略
valid_reasoning_trace = st.lists(non_empty_text, min_size=0, max_size=10)

# 有效的 agent_trace 策略
valid_agent_trace = st.fixed_dictionaries({
    "vision_analysis": st.text(min_size=0, max_size=1000),
    "reasoning_trace": valid_reasoning_trace,
    "critique": st.one_of(st.none(), st.text(min_size=0, max_size=500))
})


class TestResultPersistenceCompleteness:
    """结果持久化完整性属性测试
    
    **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
    **验证: 需求 7.1, 7.2, 7.3**
    """
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_valid_grading_result_passes_validation(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1, 7.2, 7.3**
        
        对于任意有效的批改结果，验证函数应当返回 True
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        assert validate_grading_result_persistence(result), (
            f"有效的批改结果应当通过验证: score={score}, max_score={max_score}, "
            f"confidence={confidence_score}"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_score_and_max_score_are_valid(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1**
        
        对于任意批改结果，score 和 max_score 应当是有效的非负数值
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        # 验证 score 有效
        assert result["score"] >= 0, f"score 应当非负，实际值为 {result['score']}"
        assert isinstance(result["score"], (int, float)), "score 应当是数值类型"
        
        # 验证 max_score 有效
        assert result["max_score"] >= 0, f"max_score 应当非负，实际值为 {result['max_score']}"
        assert isinstance(result["max_score"], (int, float)), "max_score 应当是数值类型"
        
        # 验证 score <= max_score
        assert result["score"] <= result["max_score"], (
            f"score ({result['score']}) 不应超过 max_score ({result['max_score']})"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_confidence_score_in_valid_range(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1**
        
        对于任意批改结果，confidence_score 应当介于 0.0 和 1.0 之间
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        assert 0.0 <= result["confidence_score"] <= 1.0, (
            f"confidence_score 应当在 [0.0, 1.0] 范围内，实际值为 {result['confidence_score']}"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_visual_annotations_is_valid_jsonb(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.2**
        
        对于任意批改结果，visual_annotations 应当是有效的 JSONB
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        # 验证可以序列化为 JSON
        assert is_valid_jsonb(result["visual_annotations"]), (
            "visual_annotations 应当可以序列化为有效的 JSONB"
        )
        
        # 验证是列表类型
        assert isinstance(result["visual_annotations"], list), (
            "visual_annotations 应当是列表类型"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_visual_annotations_contain_bounding_boxes(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.2**
        
        对于任意批改结果，visual_annotations 中的每个标注应当包含边界框坐标
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        for i, annotation in enumerate(result["visual_annotations"]):
            # 验证包含 bounding_box
            assert "bounding_box" in annotation, (
                f"标注 {i} 应当包含 bounding_box 字段"
            )
            
            bbox = annotation["bounding_box"]
            
            # 验证边界框包含所有必需坐标
            required_keys = ["ymin", "xmin", "ymax", "xmax"]
            for key in required_keys:
                assert key in bbox, f"边界框应当包含 {key} 字段"
                assert isinstance(bbox[key], (int, float)), f"{key} 应当是数值类型"
                assert bbox[key] >= 0, f"{key} 应当非负，实际值为 {bbox[key]}"
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_agent_trace_is_valid_jsonb(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.3**
        
        对于任意批改结果，agent_trace 应当是有效的 JSONB
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        # 验证可以序列化为 JSON
        assert is_valid_jsonb(result["agent_trace"]), (
            "agent_trace 应当可以序列化为有效的 JSONB"
        )
        
        # 验证是字典类型
        assert isinstance(result["agent_trace"], dict), (
            "agent_trace 应当是字典类型"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_agent_trace_contains_required_fields(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.3**
        
        对于任意批改结果，agent_trace 应当包含 vision_analysis、reasoning_trace 和 critique 字段
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        trace = result["agent_trace"]
        
        # 验证包含 vision_analysis
        assert "vision_analysis" in trace, (
            "agent_trace 应当包含 vision_analysis 字段"
        )
        
        # 验证包含 reasoning_trace
        assert "reasoning_trace" in trace, (
            "agent_trace 应当包含 reasoning_trace 字段"
        )
        
        # 验证包含 critique
        assert "critique" in trace, (
            "agent_trace 应当包含 critique 字段"
        )


class TestResultPersistenceInvalidInputs:
    """结果持久化无效输入测试
    
    验证无效输入被正确拒绝
    """
    
    @given(
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=50)
    def test_negative_score_fails_validation(
        self,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1**
        
        负的 score 应当导致验证失败
        """
        result = create_grading_result(
            score=-1.0,  # 负数
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        assert not validate_grading_result_persistence(result), (
            "负的 score 应当导致验证失败"
        )
    
    @given(
        score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=50)
    def test_negative_max_score_fails_validation(
        self,
        score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1**
        
        负的 max_score 应当导致验证失败
        """
        result = create_grading_result(
            score=score,
            max_score=-1.0,  # 负数
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        assert not validate_grading_result_persistence(result), (
            "负的 max_score 应当导致验证失败"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=50)
    def test_confidence_out_of_range_fails_validation(
        self,
        score: float,
        max_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1**
        
        超出 [0.0, 1.0] 范围的 confidence_score 应当导致验证失败
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        # 测试大于 1.0 的情况
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=1.5,  # 超出范围
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        assert not validate_grading_result_persistence(result), (
            "confidence_score > 1.0 应当导致验证失败"
        )
        
        # 测试小于 0.0 的情况
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=-0.5,  # 超出范围
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        assert not validate_grading_result_persistence(result), (
            "confidence_score < 0.0 应当导致验证失败"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=50)
    def test_missing_bounding_box_fails_validation(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.2**
        
        visual_annotations 中缺少 bounding_box 应当导致验证失败
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        # 创建缺少 bounding_box 的标注
        invalid_annotations = [{"type": "error", "message": "错误"}]  # 缺少 bounding_box
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=invalid_annotations,
            agent_trace=agent_trace
        )
        
        assert not validate_grading_result_persistence(result), (
            "缺少 bounding_box 的标注应当导致验证失败"
        )
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations
    )
    @settings(max_examples=50)
    def test_missing_agent_trace_fields_fails_validation(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.3**
        
        agent_trace 缺少必需字段应当导致验证失败
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        # 测试缺少 vision_analysis
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace={"reasoning_trace": [], "critique": None}  # 缺少 vision_analysis
        )
        
        assert not validate_grading_result_persistence(result), (
            "缺少 vision_analysis 应当导致验证失败"
        )
        
        # 测试缺少 reasoning_trace
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace={"vision_analysis": "分析", "critique": None}  # 缺少 reasoning_trace
        )
        
        assert not validate_grading_result_persistence(result), (
            "缺少 reasoning_trace 应当导致验证失败"
        )
        
        # 测试缺少 critique
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace={"vision_analysis": "分析", "reasoning_trace": []}  # 缺少 critique
        )
        
        assert not validate_grading_result_persistence(result), (
            "缺少 critique 应当导致验证失败"
        )
    
    @given(
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=50)
    def test_score_exceeds_max_score_fails_validation(
        self,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1**
        
        score 超过 max_score 应当导致验证失败
        """
        # 确保 score > max_score
        score = max_score + 10.0
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        assert not validate_grading_result_persistence(result), (
            f"score ({score}) 超过 max_score ({max_score}) 应当导致验证失败"
        )


class TestResultPersistenceRoundTrip:
    """结果持久化往返测试
    
    验证数据在序列化和反序列化后保持一致
    """
    
    @given(
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        visual_annotations=valid_visual_annotations,
        agent_trace=valid_agent_trace
    )
    @settings(max_examples=100)
    def test_json_round_trip_preserves_data(
        self,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any]
    ):
        """
        **功能: ai-grading-agent, 属性 13: 结果持久化完整性**
        **验证: 需求 7.1, 7.2, 7.3**
        
        对于任意批改结果，JSON 序列化和反序列化应当保持数据一致
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        result = create_grading_result(
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            visual_annotations=visual_annotations,
            agent_trace=agent_trace
        )
        
        # 序列化
        json_str = json.dumps(result)
        
        # 反序列化
        restored = json.loads(json_str)
        
        # 验证数据一致性
        assert restored["score"] == result["score"], "score 应当在往返后保持一致"
        assert restored["max_score"] == result["max_score"], "max_score 应当在往返后保持一致"
        assert restored["confidence_score"] == result["confidence_score"], (
            "confidence_score 应当在往返后保持一致"
        )
        assert restored["visual_annotations"] == result["visual_annotations"], (
            "visual_annotations 应当在往返后保持一致"
        )
        assert restored["agent_trace"] == result["agent_trace"], (
            "agent_trace 应当在往返后保持一致"
        )
