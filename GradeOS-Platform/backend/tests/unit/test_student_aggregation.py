"""
单元测试：学生结果聚合功能

测试学生边界检测器的结果聚合功能，包括跨页题目处理
"""

import pytest
from src.services.student_boundary_detector import (
    StudentBoundaryDetector,
    StudentBoundary,
)
from src.services.student_identification import StudentInfo


@pytest.mark.asyncio
async def test_aggregate_student_results_basic():
    """
    测试基本的学生结果聚合功能
    """
    detector = StudentBoundaryDetector()
    
    # 创建学生边界
    boundaries = [
        StudentBoundary(
            student_key="001",
            start_page=0,
            end_page=2,
            confidence=0.9,
            needs_confirmation=False,
            student_info=StudentInfo(
                name="Student A",
                student_id="001",
                confidence=0.9
            )
        )
    ]
    
    # 创建批改结果
    grading_results = [
        {
            "page_index": 0,
            "question_results": [
                {
                    "question_id": "1",
                    "score": 8.0,
                    "max_score": 10.0,
                    "confidence": 0.9,
                    "feedback": "Good work"
                }
            ]
        },
        {
            "page_index": 1,
            "question_results": [
                {
                    "question_id": "2",
                    "score": 7.0,
                    "max_score": 10.0,
                    "confidence": 0.85,
                    "feedback": "Nice"
                }
            ]
        },
        {
            "page_index": 2,
            "question_results": [
                {
                    "question_id": "3",
                    "score": 9.0,
                    "max_score": 10.0,
                    "confidence": 0.95,
                    "feedback": "Excellent"
                }
            ]
        }
    ]
    
    # 执行聚合
    student_results = detector.aggregate_student_results(boundaries, grading_results)
    
    # 验证
    assert len(student_results) == 1
    
    result = student_results[0]
    assert result["student_key"] == "001"
    assert result["student_id"] == "001"
    assert result["student_name"] == "Student A"
    assert result["start_page"] == 0
    assert result["end_page"] == 2
    assert result["page_count"] == 3
    
    # 验证题目聚合
    assert len(result["question_results"]) == 3
    
    # 验证总分
    assert result["total_score"] == 24.0  # 8 + 7 + 9
    assert result["max_total_score"] == 30.0  # 10 + 10 + 10


@pytest.mark.asyncio
async def test_aggregate_with_cross_page_questions():
    """
    测试跨页题目的聚合，确保满分不重复计算
    """
    detector = StudentBoundaryDetector()
    
    boundaries = [
        StudentBoundary(
            student_key="002",
            start_page=0,
            end_page=1,
            confidence=0.85,
            needs_confirmation=False,
            student_info=StudentInfo(
                name="Student B",
                student_id="002",
                confidence=0.85
            )
        )
    ]
    
    # 创建跨页题目的批改结果
    grading_results = [
        {
            "page_index": 0,
            "question_results": [
                {
                    "question_id": "1",
                    "score": 5.0,
                    "max_score": 10.0,
                    "confidence": 0.8,
                    "feedback": "Part 1",
                    "is_cross_page": True,
                    "page_indices": [0]
                }
            ]
        },
        {
            "page_index": 1,
            "question_results": [
                {
                    "question_id": "1",  # 同一题目
                    "score": 3.0,
                    "max_score": 10.0,  # 满分应该只计算一次
                    "confidence": 0.85,
                    "feedback": "Part 2",
                    "is_cross_page": True,
                    "page_indices": [1]
                }
            ]
        }
    ]
    
    # 执行聚合
    student_results = detector.aggregate_student_results(boundaries, grading_results)
    
    # 验证
    assert len(student_results) == 1
    
    result = student_results[0]
    questions = result["question_results"]
    
    # 验证只有一道题目（跨页题目已合并）
    assert len(questions) == 1
    
    question = questions[0]
    assert question["question_id"] == "1"
    
    # 验证满分只计算一次
    assert question["max_score"] == 10.0  # 不是 20.0
    
    # 验证得分取较大值
    assert question["score"] == 5.0  # max(5.0, 3.0)
    
    # 验证跨页标记
    assert question["is_cross_page"] is True
    
    # 验证页面索引合并
    assert set(question["page_indices"]) == {0, 1}


@pytest.mark.asyncio
async def test_aggregate_multiple_students():
    """
    测试多个学生的结果聚合
    """
    detector = StudentBoundaryDetector()
    
    boundaries = [
        StudentBoundary(
            student_key="001",
            start_page=0,
            end_page=1,
            confidence=0.9,
            needs_confirmation=False,
            student_info=StudentInfo(name="Student A", student_id="001", confidence=0.9)
        ),
        StudentBoundary(
            student_key="002",
            start_page=2,
            end_page=3,
            confidence=0.85,
            needs_confirmation=False,
            student_info=StudentInfo(name="Student B", student_id="002", confidence=0.85)
        )
    ]
    
    grading_results = [
        {"page_index": 0, "question_results": [{"question_id": "1", "score": 8.0, "max_score": 10.0}]},
        {"page_index": 1, "question_results": [{"question_id": "2", "score": 7.0, "max_score": 10.0}]},
        {"page_index": 2, "question_results": [{"question_id": "1", "score": 9.0, "max_score": 10.0}]},
        {"page_index": 3, "question_results": [{"question_id": "2", "score": 6.0, "max_score": 10.0}]},
    ]
    
    # 执行聚合
    student_results = detector.aggregate_student_results(boundaries, grading_results)
    
    # 验证
    assert len(student_results) == 2
    
    # 验证第一个学生
    student_a = student_results[0]
    assert student_a["student_key"] == "001"
    assert len(student_a["question_results"]) == 2
    assert student_a["total_score"] == 15.0  # 8 + 7
    
    # 验证第二个学生
    student_b = student_results[1]
    assert student_b["student_key"] == "002"
    assert len(student_b["question_results"]) == 2
    assert student_b["total_score"] == 15.0  # 9 + 6


@pytest.mark.asyncio
async def test_extract_questions_from_different_formats():
    """
    测试从不同格式的页面数据中提取题目
    """
    detector = StudentBoundaryDetector()
    
    # 格式1：question_results 字段
    page1 = {
        "question_results": [
            {"question_id": "1", "score": 8.0}
        ]
    }
    questions1 = detector._extract_questions_from_page(page1)
    assert len(questions1) == 1
    assert questions1[0]["question_id"] == "1"
    
    # 格式2：questions 字段
    page2 = {
        "questions": [
            {"question_id": "2", "score": 7.0}
        ]
    }
    questions2 = detector._extract_questions_from_page(page2)
    assert len(questions2) == 1
    assert questions2[0]["question_id"] == "2"
    
    # 格式3：页面本身就是题目
    page3 = {
        "question_id": "3",
        "score": 9.0
    }
    questions3 = detector._extract_questions_from_page(page3)
    assert len(questions3) == 1
    assert questions3[0]["question_id"] == "3"
    
    # 格式4：metadata 中的 questions
    page4 = {
        "metadata": {
            "questions": [
                {"question_id": "4", "score": 6.0}
            ]
        }
    }
    questions4 = detector._extract_questions_from_page(page4)
    assert len(questions4) == 1
    assert questions4[0]["question_id"] == "4"


@pytest.mark.asyncio
async def test_merge_cross_page_with_scoring_points():
    """
    测试带有得分点的跨页题目合并
    """
    detector = StudentBoundaryDetector()
    
    existing = {
        "question_id": "1",
        "score": 5.0,
        "max_score": 10.0,
        "scoring_point_results": [
            {"description": "Point A", "awarded": 3.0},
            {"description": "Point B", "awarded": 2.0}
        ],
        "page_indices": [0]
    }
    
    new = {
        "question_id": "1",
        "score": 4.0,
        "max_score": 10.0,
        "scoring_point_results": [
            {"description": "Point C", "awarded": 4.0}
        ],
        "page_indices": [1]
    }
    
    merged = detector._merge_cross_page_question(existing, new)
    
    # 验证满分只计算一次
    assert merged["max_score"] == 10.0
    
    # 验证得分点合并
    assert len(merged["scoring_point_results"]) == 3
    
    # 验证总得分重新计算
    assert merged["score"] == 9.0  # 3 + 2 + 4
    
    # 验证页面索引合并
    assert set(merged["page_indices"]) == {0, 1}
    
    # 验证跨页标记
    assert merged["is_cross_page"] is True
