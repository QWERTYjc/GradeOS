"""批改智能体单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.grading_agent import GradingAgent
from src.models.state import GradingState


@pytest.fixture
def mock_reasoning_client():
    """模拟 Gemini 推理客户端"""
    client = AsyncMock()
    
    # 模拟视觉提取
    client.vision_extraction.return_value = "学生写了公式 F=ma，并进行了计算"
    
    # 模拟评分映射
    client.rubric_mapping.return_value = {
        "rubric_mapping": [
            {
                "rubric_point": "正确写出公式",
                "evidence": "学生写了 F=ma",
                "score_awarded": 5.0,
                "max_score": 5.0
            },
            {
                "rubric_point": "计算正确",
                "evidence": "计算过程有误",
                "score_awarded": 2.0,
                "max_score": 5.0
            }
        ],
        "initial_score": 7.0,
        "reasoning": "公式正确但计算有误"
    }
    
    # 模拟反思
    client.critique.return_value = {
        "critique_feedback": None,
        "needs_revision": False,
        "confidence": 0.85
    }
    
    return client


@pytest.mark.asyncio
async def test_grading_agent_basic_flow(mock_reasoning_client):
    """测试批改智能体基本流程"""
    # 创建智能体（不使用检查点）
    agent = GradingAgent(reasoning_client=mock_reasoning_client)
    
    # 运行批改
    result = await agent.run(
        question_image="fake_base64_image",
        rubric="1. 正确写出公式 (5分)\n2. 计算正确 (5分)",
        max_score=10.0,
        standard_answer="F=ma, F=10N"
    )
    
    # 验证结果
    assert result["is_finalized"] is True
    assert result["final_score"] == 7.0
    assert result["confidence"] == 0.85
    assert "vision_analysis" in result
    assert len(result["rubric_mapping"]) == 2
    assert len(result["reasoning_trace"]) > 0


@pytest.mark.asyncio
async def test_grading_agent_revision_loop(mock_reasoning_client):
    """测试批改智能体修正循环"""
    # 修改 mock 以触发修正
    mock_reasoning_client.critique.side_effect = [
        {
            "critique_feedback": "评分过于严格",
            "needs_revision": True,
            "confidence": 0.6
        },
        {
            "critique_feedback": None,
            "needs_revision": False,
            "confidence": 0.9
        }
    ]
    
    # 创建智能体
    agent = GradingAgent(reasoning_client=mock_reasoning_client)
    
    # 运行批改
    result = await agent.run(
        question_image="fake_base64_image",
        rubric="评分细则",
        max_score=10.0
    )
    
    # 验证修正循环
    assert result["revision_count"] == 1
    assert result["is_finalized"] is True
    # 应该调用了两次 critique
    assert mock_reasoning_client.critique.call_count == 2


@pytest.mark.asyncio
async def test_grading_agent_max_revisions(mock_reasoning_client):
    """测试批改智能体最大修正次数限制"""
    # 修改 mock 以持续触发修正
    mock_reasoning_client.critique.return_value = {
        "critique_feedback": "需要修正",
        "needs_revision": True,
        "confidence": 0.5
    }
    
    # 创建智能体
    agent = GradingAgent(reasoning_client=mock_reasoning_client)
    
    # 运行批改
    result = await agent.run(
        question_image="fake_base64_image",
        rubric="评分细则",
        max_score=10.0
    )
    
    # 验证最大修正次数
    assert result["revision_count"] == 3
    assert result["is_finalized"] is True
    # 应该调用了 3 次 critique（初始 + 3 次修正）
    assert mock_reasoning_client.critique.call_count == 3


def test_should_revise_logic():
    """测试条件边逻辑"""
    from src.agents.grading_agent import GradingAgent
    
    agent = GradingAgent(reasoning_client=AsyncMock())
    
    # 测试：有反馈且修正次数 < 3 -> revise
    state1: GradingState = {
        "critique_feedback": "需要修正",
        "revision_count": 0
    }
    assert agent._should_revise(state1) == "revise"
    
    # 测试：有反馈但修正次数 >= 3 -> finalize
    state2: GradingState = {
        "critique_feedback": "需要修正",
        "revision_count": 3
    }
    assert agent._should_revise(state2) == "finalize"
    
    # 测试：无反馈 -> finalize
    state3: GradingState = {
        "critique_feedback": None,
        "revision_count": 0
    }
    assert agent._should_revise(state3) == "finalize"
    
    # 测试：有错误 -> finalize
    state4: GradingState = {
        "error": "某个错误",
        "critique_feedback": "需要修正",
        "revision_count": 0
    }
    assert agent._should_revise(state4) == "finalize"
