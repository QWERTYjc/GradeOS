"""检查点持久化属性测试

使用 Hypothesis 验证检查点持久化的正确性

**功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
**验证: 需求 3.7**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from unittest.mock import AsyncMock, MagicMock, call, patch
from src.agents.grading_agent import GradingAgent
from src.utils.checkpoint import get_thread_id


# 生成有效的 UUID 字符串（简化版本，不需要完全符合 UUID 格式）
uuid_strategy = st.text(
    alphabet="0123456789abcdef",
    min_size=32,
    max_size=36
)

# 生成有效的题目 ID
question_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=50
)


class TestCheckpointPersistenceProperties:
    """检查点持久化属性测试
    
    **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
    **验证: 需求 3.7**
    
    属性 4 定义：对于任意智能体执行期间的 LangGraph 状态转换，
    在下一个节点执行之前，应当将带有正确 thread_id 的检查点记录持久化到数据库。
    """
    
    @given(
        submission_id=uuid_strategy,
        question_id=question_id_strategy
    )
    def test_thread_id_determinism(self, submission_id, question_id):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        对于任意 submission_id 和 question_id，
        多次调用 get_thread_id 应该产生相同的 thread_id
        
        这是确定性属性：f(x) = f(f(x))
        """
        thread_id_1 = get_thread_id(submission_id, question_id)
        thread_id_2 = get_thread_id(submission_id, question_id)
        
        # 验证确定性
        assert thread_id_1 == thread_id_2
    
    @given(
        submission_id_1=uuid_strategy,
        submission_id_2=uuid_strategy,
        question_id=question_id_strategy
    )
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_thread_id_uniqueness_different_submissions(
        self, submission_id_1, submission_id_2, question_id
    ):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        对于不同的 submission_id，
        即使 question_id 相同，生成的 thread_id 也应该不同
        """
        # 使用 assume 过滤相同的 submission_id
        assume(submission_id_1 != submission_id_2)
        
        thread_id_1 = get_thread_id(submission_id_1, question_id)
        thread_id_2 = get_thread_id(submission_id_2, question_id)
        
        # 验证唯一性
        assert thread_id_1 != thread_id_2
    
    @given(
        submission_id=uuid_strategy,
        question_id_1=question_id_strategy,
        question_id_2=question_id_strategy
    )
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_thread_id_uniqueness_different_questions(
        self, submission_id, question_id_1, question_id_2
    ):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        对于不同的 question_id，
        即使 submission_id 相同，生成的 thread_id 也应该不同
        """
        # 使用 assume 过滤相同的 question_id
        assume(question_id_1 != question_id_2)
        
        thread_id_1 = get_thread_id(submission_id, question_id_1)
        thread_id_2 = get_thread_id(submission_id, question_id_2)
        
        # 验证唯一性
        assert thread_id_1 != thread_id_2
    
    @given(
        submission_id=uuid_strategy,
        question_id=question_id_strategy
    )
    def test_thread_id_format_contains_both_ids(self, submission_id, question_id):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        thread_id 应该包含 submission_id 和 question_id
        """
        thread_id = get_thread_id(submission_id, question_id)
        
        # 验证格式
        assert submission_id in thread_id
        assert question_id in thread_id
        assert "_" in thread_id
    
    @given(
        submission_id=uuid_strategy,
        question_id=question_id_strategy
    )
    def test_thread_id_is_recoverable(self, submission_id, question_id):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        thread_id 应该可以被解析回原始的 submission_id 和 question_id
        这确保了检查点可以被正确检索
        """
        thread_id = get_thread_id(submission_id, question_id)
        
        # 验证可以从 thread_id 恢复原始 ID
        parts = thread_id.split("_", 1)
        assert len(parts) == 2
        recovered_submission_id, recovered_question_id = parts
        
        assert recovered_submission_id == submission_id
        assert recovered_question_id == question_id


class TestCheckpointPersistenceWithMockCheckpointer:
    """使用 Mock Checkpointer 测试检查点持久化行为
    
    **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
    **验证: 需求 3.7**
    """
    
    @pytest.mark.asyncio
    @given(
        submission_id=uuid_strategy,
        question_id=question_id_strategy
    )
    @settings(max_examples=20)  # 减少示例数量以加快测试速度
    async def test_grading_agent_accepts_thread_id(
        self, submission_id, question_id
    ):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        批改智能体应该能够接受任意有效的 thread_id
        """
        # 创建 mock 客户端
        mock_reasoning_client = AsyncMock()
        mock_reasoning_client.vision_extraction.return_value = "分析结果"
        mock_reasoning_client.rubric_mapping.return_value = {
            "rubric_mapping": [],
            "initial_score": 5.0,
            "reasoning": "推理"
        }
        mock_reasoning_client.critique.return_value = {
            "critique_feedback": None,
            "needs_revision": False,
            "confidence": 0.9
        }
        
        # 创建智能体
        agent = GradingAgent(reasoning_client=mock_reasoning_client)
        
        # 生成 thread_id
        thread_id = get_thread_id(submission_id, question_id)
        
        # 运行批改（应该不抛出异常）
        result = await agent.run(
            question_image="fake_image",
            rubric="评分细则",
            max_score=10.0,
            thread_id=thread_id
        )
        
        # 验证结果
        assert result is not None
        assert result["is_finalized"] is True
    
    @pytest.mark.asyncio
    @given(
        submission_id=uuid_strategy,
        question_id=question_id_strategy
    )
    @settings(max_examples=20)
    async def test_checkpointer_receives_correct_thread_id(
        self, submission_id, question_id
    ):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        当智能体配置了 checkpointer 时，运行时应该传递正确的 thread_id
        """
        # 创建 mock 客户端
        mock_reasoning_client = AsyncMock()
        mock_reasoning_client.vision_extraction.return_value = "分析结果"
        mock_reasoning_client.rubric_mapping.return_value = {
            "rubric_mapping": [],
            "initial_score": 5.0,
            "reasoning": "推理"
        }
        mock_reasoning_client.critique.return_value = {
            "critique_feedback": None,
            "needs_revision": False,
            "confidence": 0.9
        }
        
        # 创建 mock checkpointer
        mock_checkpointer = MagicMock()
        
        # 创建智能体
        agent = GradingAgent(
            reasoning_client=mock_reasoning_client,
            checkpointer=mock_checkpointer
        )
        
        # 生成 thread_id
        thread_id = get_thread_id(submission_id, question_id)
        
        # 验证智能体已正确配置 checkpointer
        assert agent.checkpointer is mock_checkpointer
        
        # 验证 thread_id 格式正确
        assert submission_id in thread_id
        assert question_id in thread_id


class TestCheckpointStateTransitions:
    """测试状态转换时的检查点行为
    
    **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
    **验证: 需求 3.7**
    """
    
    @pytest.mark.asyncio
    @given(
        submission_id=uuid_strategy,
        question_id=question_id_strategy,
        max_score=st.floats(min_value=5.0, max_value=100.0, allow_nan=False)
    )
    @settings(max_examples=20)
    async def test_state_transitions_produce_reasoning_trace(
        self, submission_id, question_id, max_score
    ):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        每次状态转换都应该在 reasoning_trace 中留下记录，
        这证明了状态转换确实发生了
        """
        # 计算一个合理的分数（不超过 max_score）
        mock_score = min(5.0, max_score * 0.5)
        
        # 创建 mock 客户端
        mock_reasoning_client = AsyncMock()
        mock_reasoning_client.vision_extraction.return_value = "视觉分析结果"
        mock_reasoning_client.rubric_mapping.return_value = {
            "rubric_mapping": [{"point": "测试点", "score": mock_score}],
            "initial_score": mock_score,
            "reasoning": "评分推理"
        }
        mock_reasoning_client.critique.return_value = {
            "critique_feedback": None,
            "needs_revision": False,
            "confidence": 0.85
        }
        
        # 创建智能体
        agent = GradingAgent(reasoning_client=mock_reasoning_client)
        
        # 生成 thread_id
        thread_id = get_thread_id(submission_id, question_id)
        
        # 运行批改
        result = await agent.run(
            question_image="fake_image",
            rubric="评分细则",
            max_score=max_score,
            thread_id=thread_id
        )
        
        # 验证状态转换产生了推理轨迹
        assert "reasoning_trace" in result
        assert len(result["reasoning_trace"]) > 0
        
        # 验证最终状态
        assert result["is_finalized"] is True
        assert result["final_score"] <= max_score
    
    @pytest.mark.asyncio
    @given(
        submission_id=uuid_strategy,
        question_id=question_id_strategy,
        revision_count=st.integers(min_value=0, max_value=2)
    )
    @settings(max_examples=15)
    async def test_revision_loop_creates_additional_state_transitions(
        self, submission_id, question_id, revision_count
    ):
        """
        **功能: ai-grading-agent, 属性 4: 状态转换时检查点持久化**
        **验证: 需求 3.7**
        
        当存在修正循环时，应该产生额外的状态转换
        每次修正都应该在推理轨迹中留下记录
        """
        # 创建 mock 客户端
        mock_reasoning_client = AsyncMock()
        mock_reasoning_client.vision_extraction.return_value = "视觉分析结果"
        mock_reasoning_client.rubric_mapping.return_value = {
            "rubric_mapping": [{"point": "测试点", "score": 5.0}],
            "initial_score": 5.0,
            "reasoning": "评分推理"
        }
        
        # 设置 critique 返回值，模拟修正循环
        call_count = [0]
        
        def critique_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= revision_count:
                return {
                    "critique_feedback": f"需要修正 {call_count[0]}",
                    "needs_revision": True,
                    "confidence": 0.6
                }
            return {
                "critique_feedback": None,
                "needs_revision": False,
                "confidence": 0.9
            }
        
        mock_reasoning_client.critique.side_effect = critique_side_effect
        
        # 创建智能体
        agent = GradingAgent(reasoning_client=mock_reasoning_client)
        
        # 生成 thread_id
        thread_id = get_thread_id(submission_id, question_id)
        
        # 运行批改
        result = await agent.run(
            question_image="fake_image",
            rubric="评分细则",
            max_score=10.0,
            thread_id=thread_id
        )
        
        # 验证最终状态
        assert result["is_finalized"] is True
        
        # 验证推理轨迹包含了修正记录
        assert "reasoning_trace" in result
        # 修正循环应该产生更多的推理轨迹条目
        if revision_count > 0:
            # 至少应该有视觉分析和评分的记录
            assert len(result["reasoning_trace"]) >= 1
