"""持久化事务原子性属性测试

使用 Hypothesis 验证批改结果持久化的事务原子性

**功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
**验证: 需求 2.2, 2.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import json
import asyncio


# ===== 模拟事务管理器 =====

class MockTransactionManager:
    """
    模拟事务管理器，用于测试事务原子性
    
    跟踪事务中的所有操作，支持提交和回滚
    """
    
    def __init__(self, should_fail_at: Optional[str] = None):
        """
        初始化模拟事务管理器
        
        Args:
            should_fail_at: 在哪个操作失败（用于测试回滚）
        """
        self.operations: List[Dict[str, Any]] = []
        self.committed = False
        self.rolled_back = False
        self.should_fail_at = should_fail_at
        self._in_transaction = False

    def begin_transaction(self):
        """开始事务"""
        self._in_transaction = True
        self.operations = []
        self.committed = False
        self.rolled_back = False
    
    def add_operation(self, op_type: str, table: str, data: Dict[str, Any]):
        """
        添加操作到事务
        
        Args:
            op_type: 操作类型 (insert, update, delete)
            table: 表名
            data: 操作数据
            
        Raises:
            Exception: 如果操作类型匹配 should_fail_at
        """
        if not self._in_transaction:
            raise RuntimeError("不在事务中")
        
        if self.should_fail_at and op_type == self.should_fail_at:
            raise Exception(f"模拟 {op_type} 操作失败")
        
        self.operations.append({
            "type": op_type,
            "table": table,
            "data": data
        })
    
    def commit(self):
        """提交事务"""
        if not self._in_transaction:
            raise RuntimeError("不在事务中")
        self.committed = True
        self._in_transaction = False
    
    def rollback(self):
        """回滚事务"""
        if not self._in_transaction:
            raise RuntimeError("不在事务中")
        self.rolled_back = True
        self.operations = []
        self._in_transaction = False
    
    def get_operations_for_table(self, table: str) -> List[Dict[str, Any]]:
        """获取指定表的所有操作"""
        return [op for op in self.operations if op["table"] == table]


class MockDatabase:
    """
    模拟数据库，用于验证事务原子性
    
    维护内存中的数据状态，支持事务操作
    """
    
    def __init__(self):
        self.grading_results: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.submissions: Dict[str, Dict[str, Any]] = {}
        self.checkpoints: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._pending_grading_results: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._pending_submissions: Dict[str, Dict[str, Any]] = {}
        self._pending_checkpoints: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._in_transaction = False

    def begin_transaction(self):
        """开始事务"""
        self._in_transaction = True
        self._pending_grading_results = {}
        self._pending_submissions = {}
        self._pending_checkpoints = {}
    
    def insert_grading_result(
        self,
        submission_id: str,
        question_id: str,
        data: Dict[str, Any]
    ):
        """插入批改结果"""
        key = (submission_id, question_id)
        if self._in_transaction:
            self._pending_grading_results[key] = data
        else:
            self.grading_results[key] = data
    
    def update_submission(self, submission_id: str, data: Dict[str, Any]):
        """更新提交状态"""
        if self._in_transaction:
            self._pending_submissions[submission_id] = data
        else:
            self.submissions[submission_id] = data
    
    def insert_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        data: Dict[str, Any]
    ):
        """插入检查点"""
        key = (thread_id, checkpoint_ns, checkpoint_id)
        if self._in_transaction:
            self._pending_checkpoints[key] = data
        else:
            self.checkpoints[key] = data
    
    def commit(self):
        """提交事务"""
        if not self._in_transaction:
            raise RuntimeError("不在事务中")
        
        # 应用所有待处理的更改
        self.grading_results.update(self._pending_grading_results)
        self.submissions.update(self._pending_submissions)
        self.checkpoints.update(self._pending_checkpoints)
        
        # 清理待处理状态
        self._pending_grading_results = {}
        self._pending_submissions = {}
        self._pending_checkpoints = {}
        self._in_transaction = False
    
    def rollback(self):
        """回滚事务"""
        if not self._in_transaction:
            raise RuntimeError("不在事务中")
        
        # 丢弃所有待处理的更改
        self._pending_grading_results = {}
        self._pending_submissions = {}
        self._pending_checkpoints = {}
        self._in_transaction = False
    
    def get_grading_result(
        self, 
        submission_id: str, 
        question_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取批改结果"""
        return self.grading_results.get((submission_id, question_id))
    
    def get_submission(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """获取提交状态"""
        return self.submissions.get(submission_id)
    
    def get_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取检查点"""
        return self.checkpoints.get((thread_id, checkpoint_ns, checkpoint_id))


# ===== 事务性保存函数 =====

def save_grading_result_with_submission_update(
    db: MockDatabase,
    submission_id: str,
    question_id: str,
    score: float,
    max_score: float,
    confidence_score: float,
    new_status: Optional[str] = None,
    total_score: Optional[float] = None,
    should_fail: bool = False
) -> bool:
    """
    在单个事务中保存批改结果并更新提交状态
    
    此函数模拟 GradingResultRepository.save_with_submission_update 的行为
    
    Args:
        db: 模拟数据库
        submission_id: 提交 ID
        question_id: 题目 ID
        score: 得分
        max_score: 满分
        confidence_score: 置信度分数
        new_status: 新的提交状态
        total_score: 总分
        should_fail: 是否模拟失败
        
    Returns:
        bool: 是否成功
    """
    db.begin_transaction()
    
    try:
        # 1. 保存批改结果
        db.insert_grading_result(
            submission_id=submission_id,
            question_id=question_id,
            data={
                "score": score,
                "max_score": max_score,
                "confidence_score": confidence_score,
            }
        )
        
        # 模拟失败
        if should_fail:
            raise Exception("模拟事务失败")
        
        # 2. 更新提交状态（如果需要）
        if new_status is not None or total_score is not None:
            update_data = {}
            if new_status is not None:
                update_data["status"] = new_status
            if total_score is not None:
                update_data["total_score"] = total_score
            db.update_submission(submission_id, update_data)
        
        db.commit()
        return True
        
    except Exception:
        db.rollback()
        return False


def save_grading_result_with_checkpoint(
    db: MockDatabase,
    submission_id: str,
    question_id: str,
    score: float,
    max_score: float,
    confidence_score: float,
    thread_id: str,
    checkpoint_id: str,
    checkpoint_data: bytes,
    checkpoint_ns: str = "",
    new_status: Optional[str] = None,
    should_fail_at: Optional[str] = None
) -> bool:
    """
    在单个事务中保存批改结果、检查点和更新提交状态
    
    此函数模拟 GradingResultRepository.save_with_checkpoint 的行为
    
    Args:
        db: 模拟数据库
        submission_id: 提交 ID
        question_id: 题目 ID
        score: 得分
        max_score: 满分
        confidence_score: 置信度分数
        thread_id: LangGraph 线程 ID
        checkpoint_id: 检查点 ID
        checkpoint_data: 检查点数据
        checkpoint_ns: 检查点命名空间
        new_status: 新的提交状态
        should_fail_at: 在哪个步骤失败 (grading, checkpoint, submission)
        
    Returns:
        bool: 是否成功
    """
    db.begin_transaction()
    
    try:
        # 1. 保存批改结果
        db.insert_grading_result(
            submission_id=submission_id,
            question_id=question_id,
            data={
                "score": score,
                "max_score": max_score,
                "confidence_score": confidence_score,
            }
        )
        
        if should_fail_at == "grading":
            raise Exception("模拟批改结果保存失败")
        
        # 2. 保存检查点
        db.insert_checkpoint(
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            data={"data": checkpoint_data}
        )
        
        if should_fail_at == "checkpoint":
            raise Exception("模拟检查点保存失败")
        
        # 3. 更新提交状态（如果需要）
        if new_status is not None:
            db.update_submission(submission_id, {"status": new_status})
        
        if should_fail_at == "submission":
            raise Exception("模拟提交状态更新失败")
        
        db.commit()
        return True
        
    except Exception:
        db.rollback()
        return False


# ===== Hypothesis 策略定义 =====

# 有效的 UUID 字符串策略
valid_uuid = st.uuids().map(str)

# 有效的题目 ID 策略
valid_question_id = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_'),
    min_size=1,
    max_size=50
).filter(lambda s: s.strip())

# 有效的分数策略
valid_score = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# 有效的置信度策略 [0.0, 1.0]
valid_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# 有效的提交状态策略
valid_status = st.sampled_from([
    "UPLOADED", "PROCESSING", "GRADED", "REVIEWING", "COMPLETED", "FAILED"
])

# 有效的检查点数据策略
valid_checkpoint_data = st.binary(min_size=1, max_size=1000)


class TestPersistenceTransactionAtomicity:
    """持久化事务原子性属性测试
    
    **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
    **验证: 需求 2.2, 2.3**
    """
    
    @given(
        submission_id=valid_uuid,
        question_id=valid_question_id,
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        new_status=valid_status,
        total_score=valid_score
    )
    @settings(max_examples=100)
    def test_successful_transaction_updates_both_tables(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        new_status: str,
        total_score: float
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意成功的事务，grading_results 和 submissions 都应当被更新
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        db = MockDatabase()
        
        # 执行事务性保存
        success = save_grading_result_with_submission_update(
            db=db,
            submission_id=submission_id,
            question_id=question_id,
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            new_status=new_status,
            total_score=total_score,
            should_fail=False
        )
        
        assert success, "事务应当成功"
        
        # 验证批改结果已保存
        grading_result = db.get_grading_result(submission_id, question_id)
        assert grading_result is not None, "批改结果应当已保存"
        assert grading_result["score"] == score, "分数应当正确"
        assert grading_result["max_score"] == max_score, "满分应当正确"
        assert grading_result["confidence_score"] == confidence_score, "置信度应当正确"
        
        # 验证提交状态已更新
        submission = db.get_submission(submission_id)
        assert submission is not None, "提交状态应当已更新"
        assert submission["status"] == new_status, "状态应当正确"
        assert submission["total_score"] == total_score, "总分应当正确"

    
    @given(
        submission_id=valid_uuid,
        question_id=valid_question_id,
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        new_status=valid_status
    )
    @settings(max_examples=100)
    def test_failed_transaction_rolls_back_all_changes(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        new_status: str
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意失败的事务，grading_results 和 submissions 都不应当被更新
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        db = MockDatabase()
        
        # 执行会失败的事务性保存
        success = save_grading_result_with_submission_update(
            db=db,
            submission_id=submission_id,
            question_id=question_id,
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            new_status=new_status,
            should_fail=True  # 模拟失败
        )
        
        assert not success, "事务应当失败"
        
        # 验证批改结果未保存
        grading_result = db.get_grading_result(submission_id, question_id)
        assert grading_result is None, "失败的事务不应当保存批改结果"
        
        # 验证提交状态未更新
        submission = db.get_submission(submission_id)
        assert submission is None, "失败的事务不应当更新提交状态"
    
    @given(
        submission_id=valid_uuid,
        question_id=valid_question_id,
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        thread_id=valid_uuid,
        checkpoint_id=valid_uuid,
        checkpoint_data=valid_checkpoint_data,
        new_status=valid_status
    )
    @settings(max_examples=100)
    def test_checkpoint_transaction_updates_all_three_tables(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_data: bytes,
        new_status: str
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意成功的检查点事务，grading_results、checkpoints 和 submissions 都应当被更新
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        db = MockDatabase()
        
        # 执行事务性保存（含检查点）
        success = save_grading_result_with_checkpoint(
            db=db,
            submission_id=submission_id,
            question_id=question_id,
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            checkpoint_data=checkpoint_data,
            new_status=new_status,
            should_fail_at=None
        )
        
        assert success, "事务应当成功"
        
        # 验证批改结果已保存
        grading_result = db.get_grading_result(submission_id, question_id)
        assert grading_result is not None, "批改结果应当已保存"
        
        # 验证检查点已保存
        checkpoint = db.get_checkpoint(thread_id, "", checkpoint_id)
        assert checkpoint is not None, "检查点应当已保存"
        
        # 验证提交状态已更新
        submission = db.get_submission(submission_id)
        assert submission is not None, "提交状态应当已更新"
        assert submission["status"] == new_status, "状态应当正确"

    
    @given(
        submission_id=valid_uuid,
        question_id=valid_question_id,
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence,
        thread_id=valid_uuid,
        checkpoint_id=valid_uuid,
        checkpoint_data=valid_checkpoint_data,
        new_status=valid_status,
        fail_at=st.sampled_from(["grading", "checkpoint", "submission"])
    )
    @settings(max_examples=100)
    def test_checkpoint_transaction_failure_rolls_back_all(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_data: bytes,
        new_status: str,
        fail_at: str
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意失败的检查点事务，无论在哪个步骤失败，所有更改都应当回滚
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        db = MockDatabase()
        
        # 执行会在指定步骤失败的事务
        success = save_grading_result_with_checkpoint(
            db=db,
            submission_id=submission_id,
            question_id=question_id,
            score=score,
            max_score=max_score,
            confidence_score=confidence_score,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            checkpoint_data=checkpoint_data,
            new_status=new_status,
            should_fail_at=fail_at
        )
        
        assert not success, f"事务应当在 {fail_at} 步骤失败"
        
        # 验证所有更改都已回滚
        grading_result = db.get_grading_result(submission_id, question_id)
        assert grading_result is None, f"在 {fail_at} 失败后，批改结果不应当存在"
        
        checkpoint = db.get_checkpoint(thread_id, "", checkpoint_id)
        assert checkpoint is None, f"在 {fail_at} 失败后，检查点不应当存在"
        
        submission = db.get_submission(submission_id)
        assert submission is None, f"在 {fail_at} 失败后，提交状态不应当被更新"


class TestTransactionConsistency:
    """事务一致性测试
    
    验证事务操作的一致性保证
    """
    
    @given(
        submission_id=valid_uuid,
        question_ids=st.lists(valid_question_id, min_size=1, max_size=5, unique=True),
        scores=st.lists(valid_score, min_size=1, max_size=5),
        max_scores=st.lists(valid_score, min_size=1, max_size=5),
        confidence_scores=st.lists(valid_confidence, min_size=1, max_size=5)
    )
    @settings(max_examples=100)
    def test_batch_save_atomicity(
        self,
        submission_id: str,
        question_ids: List[str],
        scores: List[float],
        max_scores: List[float],
        confidence_scores: List[float]
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意批量保存操作，所有批改结果应当在同一事务中保存
        """
        # 确保列表长度一致
        min_len = min(len(question_ids), len(scores), len(max_scores), len(confidence_scores))
        question_ids = question_ids[:min_len]
        scores = scores[:min_len]
        max_scores = max_scores[:min_len]
        confidence_scores = confidence_scores[:min_len]
        
        # 确保 score <= max_score
        for i in range(len(scores)):
            if max_scores[i] < scores[i]:
                scores[i], max_scores[i] = max_scores[i], scores[i]
        
        db = MockDatabase()
        db.begin_transaction()
        
        try:
            # 批量保存批改结果
            for i, qid in enumerate(question_ids):
                db.insert_grading_result(
                    submission_id=submission_id,
                    question_id=qid,
                    data={
                        "score": scores[i],
                        "max_score": max_scores[i],
                        "confidence_score": confidence_scores[i],
                    }
                )
            
            # 更新提交状态
            total = sum(scores)
            max_total = sum(max_scores)
            db.update_submission(submission_id, {
                "status": "GRADED",
                "total_score": total,
                "max_total_score": max_total
            })
            
            db.commit()
            
            # 验证所有批改结果都已保存
            for i, qid in enumerate(question_ids):
                result = db.get_grading_result(submission_id, qid)
                assert result is not None, f"批改结果 {qid} 应当已保存"
                assert result["score"] == scores[i], f"分数应当正确"
            
            # 验证提交状态已更新
            submission = db.get_submission(submission_id)
            assert submission is not None, "提交状态应当已更新"
            assert submission["total_score"] == total, "总分应当正确"
            
        except Exception as e:
            db.rollback()
            pytest.fail(f"批量保存不应当失败: {e}")

    
    @given(
        submission_id=valid_uuid,
        question_ids=st.lists(valid_question_id, min_size=2, max_size=5, unique=True),
        scores=st.lists(valid_score, min_size=2, max_size=5),
        fail_index=st.integers(min_value=0, max_value=4)
    )
    @settings(max_examples=100)
    def test_batch_save_partial_failure_rolls_back_all(
        self,
        submission_id: str,
        question_ids: List[str],
        scores: List[float],
        fail_index: int
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意批量保存操作，如果任一保存失败，所有更改都应当回滚
        """
        # 确保列表长度一致
        min_len = min(len(question_ids), len(scores))
        question_ids = question_ids[:min_len]
        scores = scores[:min_len]
        
        # 确保 fail_index 在有效范围内
        fail_index = fail_index % len(question_ids)
        
        db = MockDatabase()
        db.begin_transaction()
        
        try:
            # 批量保存批改结果，在指定索引处失败
            for i, qid in enumerate(question_ids):
                if i == fail_index:
                    raise Exception(f"模拟在索引 {i} 处失败")
                
                db.insert_grading_result(
                    submission_id=submission_id,
                    question_id=qid,
                    data={"score": scores[i]}
                )
            
            db.commit()
            
        except Exception:
            db.rollback()
        
        # 验证所有批改结果都未保存（包括失败前已插入的）
        for qid in question_ids:
            result = db.get_grading_result(submission_id, qid)
            assert result is None, f"回滚后批改结果 {qid} 不应当存在"
        
        # 验证提交状态未更新
        submission = db.get_submission(submission_id)
        assert submission is None, "回滚后提交状态不应当被更新"


class TestTransactionIsolation:
    """事务隔离性测试
    
    验证事务操作的隔离性
    """
    
    @given(
        submission_id=valid_uuid,
        question_id=valid_question_id,
        score=valid_score,
        max_score=valid_score,
        confidence_score=valid_confidence
    )
    @settings(max_examples=100)
    def test_uncommitted_changes_not_visible(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意未提交的事务，更改不应当对外部可见
        """
        # 确保 score <= max_score
        if max_score < score:
            score, max_score = max_score, score
        
        db = MockDatabase()
        
        # 开始事务但不提交
        db.begin_transaction()
        db.insert_grading_result(
            submission_id=submission_id,
            question_id=question_id,
            data={
                "score": score,
                "max_score": max_score,
                "confidence_score": confidence_score,
            }
        )
        
        # 在事务提交前，更改不应当对外部可见
        # 注意：这里我们检查的是已提交的数据，而不是待处理的数据
        result = db.grading_results.get((submission_id, question_id))
        assert result is None, "未提交的事务更改不应当对外部可见"
        
        # 提交事务
        db.commit()
        
        # 提交后，更改应当可见
        result = db.get_grading_result(submission_id, question_id)
        assert result is not None, "提交后更改应当可见"
    
    @given(
        submission_id=valid_uuid,
        question_id=valid_question_id,
        initial_score=valid_score,
        new_score=valid_score
    )
    @settings(max_examples=100)
    def test_rollback_restores_original_state(
        self,
        submission_id: str,
        question_id: str,
        initial_score: float,
        new_score: float
    ):
        """
        **功能: architecture-deep-integration, 属性 4: 持久化事务原子性**
        **验证: 需求 2.2, 2.3**
        
        对于任意回滚的事务，数据库应当恢复到事务开始前的状态
        """
        db = MockDatabase()
        
        # 先保存初始数据
        db.grading_results[(submission_id, question_id)] = {"score": initial_score}
        
        # 开始新事务尝试更新
        db.begin_transaction()
        db._pending_grading_results[(submission_id, question_id)] = {"score": new_score}
        
        # 回滚事务
        db.rollback()
        
        # 验证数据恢复到初始状态
        result = db.get_grading_result(submission_id, question_id)
        assert result is not None, "原始数据应当存在"
        assert result["score"] == initial_score, "回滚后应当恢复到初始分数"
