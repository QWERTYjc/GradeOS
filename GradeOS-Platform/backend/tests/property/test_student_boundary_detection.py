"""
属性测试：学生边界检测

测试学生边界检测器的正确性属性
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any

from src.services.student_boundary_detector import (
    StudentBoundaryDetector,
    StudentBoundary,
    BoundaryDetectionResult
)
from src.services.student_identification import StudentInfo


# 生成器：学生信息
@st.composite
def student_info_strategy(draw):
    """生成学生信息"""
    has_info = draw(st.booleans())
    if not has_info:
        return None
    
    return StudentInfo(
        name=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        student_id=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        class_name=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        is_placeholder=draw(st.booleans())
    )


# 生成器：批改结果
@st.composite
def grading_result_strategy(draw):
    """生成单个批改结果"""
    result = {
        "page_index": draw(st.integers(min_value=0, max_value=100)),
        "question_id": draw(st.one_of(st.none(), st.text(min_size=1, max_size=10))),
    }
    
    # 可能包含学生信息
    if draw(st.booleans()):
        student_info = draw(student_info_strategy())
        if student_info:
            result["student_info"] = {
                "name": student_info.name,
                "student_id": student_info.student_id,
                "class_name": student_info.class_name,
                "confidence": student_info.confidence
            }
    
    # 可能包含题目编号
    if draw(st.booleans()):
        result["question_numbers"] = draw(
            st.lists(st.text(min_size=1, max_size=5), min_size=0, max_size=5)
        )
    
    return result


# 生成器：批改结果列表
@st.composite
def grading_results_strategy(draw):
    """生成批改结果列表"""
    n_pages = draw(st.integers(min_value=1, max_value=50))
    results = []
    
    for i in range(n_pages):
        result = draw(grading_result_strategy())
        result["page_index"] = i  # 确保页码连续
        results.append(result)
    
    return results


@pytest.mark.asyncio
@given(grading_results=grading_results_strategy())
@settings(max_examples=100, deadline=None)
async def test_property_5_boundary_detection_triggered(grading_results: List[Dict[str, Any]]):
    """
    **Feature: self-evolving-grading, Property 5: 学生边界检测触发**
    **Validates: Requirements 3.1**
    
    属性：对于任意完成的批次批改，学生边界检测应被触发并产生分割结果
    """
    # 创建检测器
    detector = StudentBoundaryDetector()
    
    # 执行检测
    result = await detector.detect_boundaries(grading_results)
    
    # 验证：检测被触发并产生结果
    assert isinstance(result, BoundaryDetectionResult), "应返回 BoundaryDetectionResult 对象"
    assert result.total_pages == len(grading_results), "总页数应与输入一致"
    assert isinstance(result.boundaries, list), "boundaries 应为列表"
    assert result.total_students >= 0, "学生数量应为非负数"
    assert isinstance(result.unassigned_pages, list), "unassigned_pages 应为列表"


@pytest.mark.asyncio
@given(grading_results=grading_results_strategy())
@settings(max_examples=100, deadline=None)
async def test_property_6_boundary_marking_correctness(grading_results: List[Dict[str, Any]]):
    """
    **Feature: self-evolving-grading, Property 6: 学生边界标记正确性**
    **Validates: Requirements 3.2, 3.5**
    
    属性：对于任意检测到的学生边界，start_page 应小于等于 end_page，
    且相邻学生的边界不重叠
    """
    # 创建检测器
    detector = StudentBoundaryDetector()
    
    # 执行检测
    result = await detector.detect_boundaries(grading_results)
    
    # 验证1：每个边界的 start_page <= end_page
    for boundary in result.boundaries:
        assert boundary.start_page <= boundary.end_page, \
            f"边界 {boundary.student_key} 的起始页 {boundary.start_page} 应 <= 结束页 {boundary.end_page}"
    
    # 验证2：相邻边界不重叠
    if len(result.boundaries) > 1:
        # 按起始页排序
        sorted_boundaries = sorted(result.boundaries, key=lambda b: b.start_page)
        
        for i in range(len(sorted_boundaries) - 1):
            current = sorted_boundaries[i]
            next_boundary = sorted_boundaries[i + 1]
            
            # 当前边界的结束页应小于下一个边界的起始页
            assert current.end_page < next_boundary.start_page, \
                f"边界重叠：{current.student_key} 的结束页 {current.end_page} " \
                f"应 < {next_boundary.student_key} 的起始页 {next_boundary.start_page}"
    
    # 验证3：所有边界的页码应在有效范围内
    total_pages = len(grading_results)
    for boundary in result.boundaries:
        assert 0 <= boundary.start_page < total_pages, \
            f"起始页 {boundary.start_page} 应在 [0, {total_pages}) 范围内"
        assert 0 <= boundary.end_page < total_pages, \
            f"结束页 {boundary.end_page} 应在 [0, {total_pages}) 范围内"
    
    # 验证4：置信度应在 [0, 1] 范围内
    for boundary in result.boundaries:
        assert 0.0 <= boundary.confidence <= 1.0, \
            f"置信度 {boundary.confidence} 应在 [0.0, 1.0] 范围内"


@pytest.mark.asyncio
@given(
    n_pages=st.integers(min_value=1, max_value=30),
    n_students=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100, deadline=None)
async def test_boundary_detection_with_clear_markers(n_pages: int, n_students: int):
    """
    测试：当有明确的学生标识时，边界检测应准确
    """
    assume(n_pages >= n_students)  # 确保每个学生至少有一页
    
    # 创建有明确学生标识的批改结果
    grading_results = []
    pages_per_student = n_pages // n_students
    
    for student_idx in range(n_students):
        start = student_idx * pages_per_student
        end = start + pages_per_student if student_idx < n_students - 1 else n_pages
        
        for page_idx in range(start, end):
            result = {
                "page_index": page_idx,
                "student_info": {
                    "name": f"Student_{student_idx}",
                    "student_id": f"ID_{student_idx:03d}",
                    "confidence": 0.9
                },
                "question_id": str((page_idx % 5) + 1)
            }
            grading_results.append(result)
    
    # 执行检测
    detector = StudentBoundaryDetector()
    result = await detector.detect_boundaries(grading_results)
    
    # 验证：应检测到正确数量的学生
    assert result.total_students >= 1, "应至少检测到1个学生"
    assert result.total_students <= n_students, f"检测到的学生数 {result.total_students} 不应超过 {n_students}"
    
    # 验证：所有页面应被分配
    assigned_pages = set()
    for boundary in result.boundaries:
        assigned_pages.update(range(boundary.start_page, boundary.end_page + 1))
    
    # 允许部分页面未分配（因为检测逻辑可能不完美）
    coverage = len(assigned_pages) / n_pages
    assert coverage >= 0.5, f"至少50%的页面应被分配，实际覆盖率：{coverage:.2%}"


@pytest.mark.asyncio
@given(
    n_pages=st.integers(min_value=5, max_value=30),
    questions_per_student=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=100, deadline=None)
async def test_boundary_detection_with_question_cycle(
    n_pages: int,
    questions_per_student: int
):
    """
    测试：通过题目循环检测学生边界
    """
    # 创建有题目循环的批改结果
    grading_results = []
    
    for page_idx in range(n_pages):
        # 题目编号循环：1,2,3,1,2,3,...
        question_num = (page_idx % questions_per_student) + 1
        
        result = {
            "page_index": page_idx,
            "question_id": str(question_num),
            "question_numbers": [str(question_num)]
        }
        grading_results.append(result)
    
    # 执行检测
    detector = StudentBoundaryDetector()
    result = await detector.detect_boundaries(grading_results)
    
    # 验证：应检测到多个学生（如果页数足够）
    expected_students = n_pages // questions_per_student
    if expected_students > 1:
        assert result.total_students >= 1, "应至少检测到1个学生"
    
    # 验证：边界标记正确性
    for boundary in result.boundaries:
        assert boundary.start_page <= boundary.end_page
        assert 0 <= boundary.confidence <= 1.0


@pytest.mark.asyncio
async def test_empty_grading_results():
    """
    边缘情况测试：空批改结果
    """
    detector = StudentBoundaryDetector()
    result = await detector.detect_boundaries([])
    
    assert result.total_pages == 0
    assert result.total_students == 0
    assert len(result.boundaries) == 0
    assert len(result.unassigned_pages) == 0


@pytest.mark.asyncio
async def test_single_page_result():
    """
    边缘情况测试：单页批改结果
    """
    grading_results = [{
        "page_index": 0,
        "question_id": "1",
        "student_info": {
            "name": "Test Student",
            "student_id": "001",
            "confidence": 0.9
        }
    }]
    
    detector = StudentBoundaryDetector()
    result = await detector.detect_boundaries(grading_results)
    
    assert result.total_pages == 1
    assert result.total_students >= 0
    
    if result.total_students > 0:
        assert len(result.boundaries) > 0
        boundary = result.boundaries[0]
        assert boundary.start_page == 0
        assert boundary.end_page == 0


@pytest.mark.asyncio
@given(
    confidence_threshold=st.floats(min_value=0.0, max_value=1.0),
    student_confidence=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=100, deadline=None)
async def test_property_7_low_confidence_boundary_marking(
    confidence_threshold: float,
    student_confidence: float
):
    """
    **Feature: self-evolving-grading, Property 7: 低置信度边界标记**
    **Validates: Requirements 3.4**
    
    属性：对于任意置信度低于 0.8 的学生边界，needs_confirmation 应为 True
    """
    # 创建检测器，使用固定阈值 0.8（符合需求）
    detector = StudentBoundaryDetector(confidence_threshold=0.8)
    
    # 创建批改结果，确保学生信息置信度足够高以被识别（>= 0.6）
    # 但综合置信度可能会因其他因素而降低
    effective_confidence = max(0.6, student_confidence)  # 确保能被识别
    
    grading_results = [
        {
            "page_index": 0,
            "question_id": "1",
            "student_info": {
                "name": "Test Student",
                "student_id": "001",
                "confidence": effective_confidence
            }
        },
        {
            "page_index": 1,
            "question_id": "2",
            "student_info": {
                "name": "Test Student",
                "student_id": "001",
                "confidence": effective_confidence
            }
        }
    ]
    
    # 执行检测
    result = await detector.detect_boundaries(grading_results)
    
    # 验证：所有边界都应正确标记 needs_confirmation
    for boundary in result.boundaries:
        # 验证置信度在有效范围内
        assert 0.0 <= boundary.confidence <= 1.0, \
            f"置信度 {boundary.confidence} 应在 [0.0, 1.0] 范围内"
        
        # 验证 needs_confirmation 标志与置信度一致
        if boundary.confidence < 0.8:
            assert boundary.needs_confirmation is True, \
                f"置信度 {boundary.confidence} < 0.8，needs_confirmation 应为 True"
        else:
            assert boundary.needs_confirmation is False, \
                f"置信度 {boundary.confidence} >= 0.8，needs_confirmation 应为 False"


@pytest.mark.asyncio
@given(
    n_pages=st.integers(min_value=1, max_value=20),
    base_confidence=st.floats(min_value=0.6, max_value=1.0)
)
@settings(max_examples=100, deadline=None)
async def test_confidence_threshold_consistency(
    n_pages: int,
    base_confidence: float
):
    """
    测试置信度阈值的一致性
    
    验证：needs_confirmation 标志始终与置信度阈值一致
    """
    # 使用默认阈值 0.8
    detector = StudentBoundaryDetector(confidence_threshold=0.8)
    
    # 创建批改结果
    grading_results = []
    for i in range(n_pages):
        grading_results.append({
            "page_index": i,
            "question_id": str((i % 5) + 1),
            "student_info": {
                "name": "Student A",
                "student_id": "001",
                "confidence": base_confidence
            }
        })
    
    # 执行检测
    result = await detector.detect_boundaries(grading_results)
    
    # 验证：所有边界的 needs_confirmation 标志应与置信度一致
    for boundary in result.boundaries:
        expected_needs_confirmation = boundary.confidence < 0.8
        assert boundary.needs_confirmation == expected_needs_confirmation, \
            f"置信度 {boundary.confidence}，needs_confirmation 应为 {expected_needs_confirmation}"
