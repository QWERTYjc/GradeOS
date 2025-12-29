"""
LangGraph 工作流集成测试

验证跨页题目合并节点和 ResultMerger 集成是否正常工作。

Requirements: 2.1, 4.2, 4.3, 11.4
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List

from src.graphs.batch_grading import (
    cross_page_merge_node,
    export_node,
    BatchGradingGraphState,
)


@pytest.fixture
def sample_grading_results() -> List[Dict[str, Any]]:
    """创建示例批改结果"""
    return [
        {
            "page_index": 0,
            "status": "completed",
            "score": 5.0,
            "max_score": 10.0,
            "confidence": 0.9,
            "question_details": [
                {
                    "question_id": "1",
                    "score": 5.0,
                    "max_score": 10.0,
                    "feedback": "部分正确",
                    "student_answer": "答案内容...",
                    "is_correct": False,
                    "scoring_point_results": []
                }
            ],
            "is_blank_page": False
        },
        {
            "page_index": 1,
            "status": "completed",
            "score": 5.0,
            "max_score": 10.0,
            "confidence": 0.85,
            "question_details": [
                {
                    "question_id": "1",  # 同一题目，跨页
                    "score": 5.0,
                    "max_score": 10.0,
                    "feedback": "继续答题",
                    "student_answer": "答案继续...",
                    "is_correct": False,
                    "scoring_point_results": []
                }
            ],
            "is_blank_page": False
        },
        {
            "page_index": 2,
            "status": "completed",
            "score": 8.0,
            "max_score": 10.0,
            "confidence": 0.95,
            "question_details": [
                {
                    "question_id": "2",
                    "score": 8.0,
                    "max_score": 10.0,
                    "feedback": "很好",
                    "student_answer": "答案2...",
                    "is_correct": True,
                    "scoring_point_results": []
                }
            ],
            "is_blank_page": False
        }
    ]


@pytest.mark.asyncio
async def test_cross_page_merge_node(sample_grading_results):
    """测试跨页题目合并节点"""
    # 准备状态
    state: BatchGradingGraphState = {
        "batch_id": "test_batch_001",
        "grading_results": sample_grading_results,
        "timestamps": {}
    }
    
    # 执行跨页合并
    result = await cross_page_merge_node(state)
    
    # 验证结果
    assert "merged_questions" in result
    assert "cross_page_questions" in result
    assert result["current_stage"] == "cross_page_merge_completed"
    assert result["percentage"] == 75.0
    
    # 验证合并后的题目数量（应该少于原始数量，因为跨页题目被合并了）
    merged_questions = result["merged_questions"]
    assert len(merged_questions) <= len(sample_grading_results)
    
    # 验证跨页题目信息
    cross_page_questions = result["cross_page_questions"]
    if cross_page_questions:
        # 应该检测到题目1是跨页的
        cross_page_ids = [cpq["question_id"] for cpq in cross_page_questions]
        assert "1" in cross_page_ids or any("1" in qid for qid in cross_page_ids)


@pytest.mark.asyncio
async def test_export_node_with_merged_questions(sample_grading_results):
    """测试导出节点支持合并后的题目"""
    # 准备状态（包含合并后的题目）
    merged_questions = [
        {
            "question_id": "1",
            "score": 10.0,
            "max_score": 10.0,
            "confidence": 0.875,
            "feedback": "部分正确 | 继续答题",
            "student_answer": "答案内容...\n---\n答案继续...",
            "is_cross_page": True,
            "page_indices": [0, 1],
            "merge_source": ["page_0", "page_1"],
            "scoring_point_results": []
        },
        {
            "question_id": "2",
            "score": 8.0,
            "max_score": 10.0,
            "confidence": 0.95,
            "feedback": "很好",
            "student_answer": "答案2...",
            "is_cross_page": False,
            "page_indices": [2],
            "merge_source": None,
            "scoring_point_results": []
        }
    ]
    
    cross_page_questions = [
        {
            "question_id": "1",
            "page_indices": [0, 1],
            "confidence": 0.875,
            "merge_reason": "连续页面出现相同题号"
        }
    ]
    
    student_results = [
        {
            "student_key": "学生A",
            "student_id": "001",
            "start_page": 0,
            "end_page": 2,
            "total_score": 18.0,
            "max_total_score": 20.0,
            "question_details": merged_questions,
            "confidence": 0.9,
            "needs_confirmation": False
        }
    ]
    
    state: BatchGradingGraphState = {
        "batch_id": "test_batch_002",
        "student_results": student_results,
        "cross_page_questions": cross_page_questions,
        "merged_questions": merged_questions,
        "timestamps": {}
    }
    
    # 执行导出
    result = await export_node(state)
    
    # 验证结果
    assert "export_data" in result
    assert result["current_stage"] == "completed"
    assert result["percentage"] == 100.0
    
    export_data = result["export_data"]
    assert export_data["batch_id"] == "test_batch_002"
    assert len(export_data["students"]) == 1
    
    # 验证学生数据
    student = export_data["students"][0]
    assert student["student_name"] == "学生A"
    assert student["score"] == 18.0
    assert student["max_score"] == 20.0
    assert student["percentage"] == 90.0
    
    # 验证题目结果包含跨页信息
    question_results = student["question_results"]
    assert len(question_results) == 2
    
    # 找到跨页题目
    cross_page_q = next((q for q in question_results if q["is_cross_page"]), None)
    assert cross_page_q is not None
    assert cross_page_q["question_id"] == "1"
    assert len(cross_page_q["page_indices"]) == 2
    
    # 验证跨页题目信息被导出
    assert "cross_page_questions" in export_data
    assert len(export_data["cross_page_questions"]) == 1


@pytest.mark.asyncio
async def test_export_node_json_export():
    """测试无数据库模式下的 JSON 导出"""
    import os
    import json
    import tempfile
    from unittest.mock import patch, AsyncMock
    
    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 设置导出目录
        os.environ["EXPORT_DIR"] = tmpdir
        
        # 准备状态
        student_results = [
            {
                "student_key": "学生B",
                "student_id": "002",
                "start_page": 0,
                "end_page": 1,
                "total_score": 15.0,
                "max_total_score": 20.0,
                "question_details": [
                    {
                        "question_id": "1",
                        "score": 15.0,
                        "max_score": 20.0,
                        "feedback": "不错",
                        "student_answer": "答案...",
                        "is_correct": True
                    }
                ],
                "confidence": 0.9,
                "needs_confirmation": False
            }
        ]
        
        state: BatchGradingGraphState = {
            "batch_id": "test_batch_003",
            "student_results": student_results,
            "cross_page_questions": [],
            "merged_questions": [],
            "timestamps": {}
        }
        
        # Mock 数据库连接失败，强制使用 JSON 导出
        with patch('src.utils.database.get_db_pool', new_callable=AsyncMock) as mock_db:
            mock_db.return_value = None  # 模拟无数据库
            
            # 执行导出
            result = await export_node(state)
        
        # 验证 JSON 文件被创建
        export_data = result["export_data"]
        assert "json_file" in export_data
        
        json_file = export_data["json_file"]
        assert os.path.exists(json_file)
        
        # 验证 JSON 内容
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["batch_id"] == "test_batch_003"
        assert len(data["students"]) == 1
        assert data["students"][0]["student_name"] == "学生B"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
