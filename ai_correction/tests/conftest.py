#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pytest配置文件
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_llm_client():
    """模拟LLM客户端"""
    class MockLLMClient:
        def chat(self, messages, **kwargs):
            return {"content": "测试响应"}
    
    return MockLLMClient()


@pytest.fixture
def sample_state():
    """示例状态对象"""
    return {
        'task_id': 'test_001',
        'user_id': 'test_user',
        'mode': 'professional',
        'questions': [],
        'evaluations': [],
        'errors': []
    }


@pytest.fixture
def sample_rubric():
    """示例评分标准"""
    return {
        'questions': [
            {
                'qid': 'Q1',
                'max_score': 10,
                'rubric_items': [
                    {
                        'id': 'Q1_R1',
                        'description': '正确应用公式',
                        'score_if_fulfilled': 5,
                        'conditions': ['使用余弦定理'],
                        'keywords': ['余弦定理', 'cosA']
                    }
                ]
            }
        ]
    }
