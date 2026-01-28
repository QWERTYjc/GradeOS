"""
LangGraph 工作流集成测试

验证导出节点和数据格式。

Requirements: 2.1, 11.4
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List

from src.graphs.batch_grading import (
    export_node,
    BatchGradingGraphState,
)


@pytest.mark.asyncio
async def test_export_node_with_merged_questions():
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


@pytest.mark.asyncio
async def test_export_node_json_export_even_when_db_available():
    """测试数据库可用但未持久化时仍导出 JSON 以保证数据安全"""
    import os
    import json
    import tempfile
    from unittest.mock import patch, AsyncMock

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["EXPORT_DIR"] = tmpdir

        student_results = [
            {
                "student_key": "学生C",
                "student_id": "003",
                "start_page": 0,
                "end_page": 1,
                "total_score": 12.0,
                "max_total_score": 20.0,
                "question_details": [
                    {
                        "question_id": "1",
                        "score": 12.0,
                        "max_score": 20.0,
                        "feedback": "需要改进",
                        "student_answer": "答案...",
                        "is_correct": False
                    }
                ],
                "confidence": 0.7,
                "needs_confirmation": False
            }
        ]

        state: BatchGradingGraphState = {
            "batch_id": "test_batch_004",
            "student_results": student_results,
            "cross_page_questions": [],
            "merged_questions": [],
            "timestamps": {}
        }

        # 模拟数据库可用（get_db_pool 返回对象）
        with patch('src.utils.database.get_db_pool', new_callable=AsyncMock) as mock_db:
            mock_db.return_value = object()
            result = await export_node(state)

        export_data = result["export_data"]
        assert "json_file" in export_data

        json_file = export_data["json_file"]
        assert os.path.exists(json_file)

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data["batch_id"] == "test_batch_004"
        assert data["students"][0]["student_name"] == "学生C"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
