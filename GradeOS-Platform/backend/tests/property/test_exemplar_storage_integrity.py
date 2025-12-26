"""判例存储完整性的属性测试

**功能: self-evolving-grading, 属性 8: 判例存储完整性**
**验证: 需求 4.1, 4.2**

属性定义：
对于任意老师确认的批改结果，存储的判例应包含：
question_type、student_answer_text、score、max_score、teacher_feedback、confirmed_at。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.services.exemplar_memory import ExemplarMemory


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def grading_result_strategy(draw):
    """生成随机的批改结果字典"""
    question_type = draw(st.sampled_from(['objective', 'stepwise', 'essay']))
    question_image_hash = draw(st.text(min_size=10, max_size=64, alphabet=st.characters(whitelist_categories=('L', 'N'))))
    student_answer_text = draw(st.text(min_size=1, max_size=500))
    score = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    max_score = draw(st.floats(min_value=score, max_value=100.0, allow_nan=False, allow_infinity=False))
    
    return {
        'question_type': question_type,
        'question_image_hash': question_image_hash,
        'student_answer_text': student_answer_text,
        'score': score,
        'max_score': max_score
    }


@st.composite
def teacher_info_strategy(draw):
    """生成随机的教师信息"""
    teacher_id = draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))))
    teacher_feedback = draw(st.text(min_size=1, max_size=500))
    return teacher_id, teacher_feedback


def create_mock_pool():
    """创建正确配置的 Mock 数据库池"""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    
    # 创建异步上下文管理器
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.return_value = mock_conn
    mock_acquire.__aexit__.return_value = None
    mock_pool.acquire.return_value = mock_acquire
    
    return mock_pool, mock_conn


# ============================================================================
# 属性测试
# ============================================================================

class TestExemplarStorageIntegrity:
    """判例存储完整性的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        grading_result=grading_result_strategy(),
        teacher_info=teacher_info_strategy()
    )
    @pytest.mark.asyncio
    async def test_stored_exemplar_contains_all_required_fields(
        self,
        grading_result: dict,
        teacher_info: tuple
    ):
        """
        **功能: self-evolving-grading, 属性 8: 判例存储完整性**
        **验证: 需求 4.1, 4.2**
        
        验证：存储的判例包含所有必需字段。
        """
        teacher_id, teacher_feedback = teacher_info
        
        # 确保输入有效
        assume(len(teacher_id.strip()) > 0)
        assume(len(teacher_feedback.strip()) > 0)
        assume(len(grading_result['student_answer_text'].strip()) > 0)
        
        # 创建 Mock 数据库连接
        mock_conn = AsyncMock()
        
        # 捕获存储的数据
        stored_data = {}
        
        async def capture_execute(query, *args):
            if 'INSERT INTO exemplars' in query:
                # 根据参数数量判断是否包含 embedding
                if len(args) >= 10:
                    stored_data['exemplar_id'] = args[0]
                    stored_data['question_type'] = args[1]
                    stored_data['question_image_hash'] = args[2]
                    stored_data['student_answer_text'] = args[3]
                    stored_data['score'] = args[4]
                    stored_data['max_score'] = args[5]
                    stored_data['teacher_feedback'] = args[6]
                    stored_data['teacher_id'] = args[7]
                    stored_data['confirmed_at'] = args[8]
                    stored_data['usage_count'] = args[9]
                    if len(args) > 10:
                        stored_data['embedding'] = args[10]
            return None
        
        mock_conn.execute.side_effect = capture_execute
        
        # 创建 Mock 池管理器，使用正确的上下文管理器
        mock_pool_manager = MagicMock()
        mock_pg_context = AsyncMock()
        mock_pg_context.__aenter__.return_value = mock_conn
        mock_pg_context.__aexit__.return_value = None
        mock_pool_manager.pg_connection.return_value = mock_pg_context
        
        # 创建 Mock 嵌入模型
        mock_embedding_model = AsyncMock()
        mock_embedding_model.aembed_query.return_value = [0.1] * 768
        
        # 创建判例记忆服务
        exemplar_memory = ExemplarMemory(
            pool_manager=mock_pool_manager,
            embedding_model=mock_embedding_model
        )
        
        # 存储判例
        exemplar_id = await exemplar_memory.store_exemplar(
            grading_result=grading_result,
            teacher_id=teacher_id,
            teacher_feedback=teacher_feedback
        )
        
        # 验证：返回了判例ID
        assert exemplar_id is not None
        assert len(exemplar_id) > 0
        
        # 验证：所有必需字段都被存储
        assert stored_data['question_type'] == grading_result['question_type']
        assert stored_data['student_answer_text'] == grading_result['student_answer_text']
        assert stored_data['score'] == grading_result['score']
        assert stored_data['max_score'] == grading_result['max_score']
        assert stored_data['teacher_feedback'] == teacher_feedback
        assert isinstance(stored_data['confirmed_at'], datetime)
        assert stored_data['teacher_id'] == teacher_id
        assert stored_data['usage_count'] == 0
        assert stored_data['embedding'] is not None

    @settings(max_examples=100, deadline=None)
    @given(
        grading_result=grading_result_strategy(),
        teacher_info=teacher_info_strategy()
    )
    @pytest.mark.asyncio
    async def test_stored_exemplar_generates_embedding(
        self,
        grading_result: dict,
        teacher_info: tuple
    ):
        """
        **功能: self-evolving-grading, 属性 8: 判例存储完整性**
        **验证: 需求 4.1, 4.2**
        
        验证：存储判例时生成向量嵌入。
        """
        teacher_id, teacher_feedback = teacher_info
        
        # 确保输入有效
        assume(len(teacher_id.strip()) > 0)
        assume(len(teacher_feedback.strip()) > 0)
        assume(len(grading_result['student_answer_text'].strip()) > 0)
        
        # 创建 Mock 数据库连接
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.execute.return_value = None
        
        # 创建 Mock 池管理器
        mock_pool_manager = MagicMock()
        mock_pool_manager.get_db_pool.return_value = mock_pool
        
        # 创建 Mock 嵌入模型
        mock_embedding_model = AsyncMock()
        mock_embedding_model.aembed_query.return_value = [0.1] * 768
        
        # 创建判例记忆服务
        exemplar_memory = ExemplarMemory(
            pool_manager=mock_pool_manager,
            embedding_model=mock_embedding_model
        )
        
        # 存储判例
        await exemplar_memory.store_exemplar(
            grading_result=grading_result,
            teacher_id=teacher_id,
            teacher_feedback=teacher_feedback
        )
        
        # 验证：调用了嵌入模型
        assert mock_embedding_model.aembed_query.called
        
        # 验证：嵌入输入包含题目类型、学生答案和教师评语
        call_args = mock_embedding_model.aembed_query.call_args[0][0]
        assert grading_result['question_type'] in call_args
        assert grading_result['student_answer_text'] in call_args
        assert teacher_feedback in call_args

    @settings(max_examples=100, deadline=None)
    @given(
        teacher_info=teacher_info_strategy()
    )
    @pytest.mark.asyncio
    async def test_missing_required_field_raises_error(
        self,
        teacher_info: tuple
    ):
        """
        **功能: self-evolving-grading, 属性 8: 判例存储完整性**
        **验证: 需求 4.1, 4.2**
        
        验证：缺少必需字段时抛出错误。
        """
        teacher_id, teacher_feedback = teacher_info
        
        # 确保输入有效
        assume(len(teacher_id.strip()) > 0)
        assume(len(teacher_feedback.strip()) > 0)
        
        # 创建 Mock 数据库连接
        mock_pool, mock_conn = create_mock_pool()
        mock_conn.execute.return_value = None
        
        # 创建 Mock 池管理器
        mock_pool_manager = MagicMock()
        mock_pool_manager.get_db_pool.return_value = mock_pool
        
        # 创建 Mock 嵌入模型
        mock_embedding_model = AsyncMock()
        mock_embedding_model.aembed_query.return_value = [0.1] * 768
        
        # 创建判例记忆服务
        exemplar_memory = ExemplarMemory(
            pool_manager=mock_pool_manager,
            embedding_model=mock_embedding_model
        )
        
        # 测试缺少各个必需字段的情况
        required_fields = [
            'question_type', 'question_image_hash', 
            'student_answer_text', 'score', 'max_score'
        ]
        
        for missing_field in required_fields:
            # 创建缺少一个字段的批改结果
            incomplete_result = {
                'question_type': 'objective',
                'question_image_hash': 'hash123',
                'student_answer_text': 'answer',
                'score': 5.0,
                'max_score': 10.0
            }
            del incomplete_result[missing_field]
            
            # 验证：抛出 ValueError
            with pytest.raises(ValueError) as exc_info:
                await exemplar_memory.store_exemplar(
                    grading_result=incomplete_result,
                    teacher_id=teacher_id,
                    teacher_feedback=teacher_feedback
                )
            
            # 验证：错误消息包含缺失字段名
            assert missing_field in str(exc_info.value)
