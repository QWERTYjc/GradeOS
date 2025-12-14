"""批改结果仓储类"""

from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from datetime import datetime
import json
import logging

from src.utils.database import Database
from src.utils.pool_manager import UnifiedPoolManager
from src.models.enums import SubmissionStatus


logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """事务错误"""
    pass


class GradingResultRepository:
    """批改结果仓储"""
    
    def __init__(self, db: Optional[Database] = None, pool_manager: Optional[UnifiedPoolManager] = None):
        """
        初始化批改结果仓储
        
        Args:
            db: 传统数据库连接（向后兼容）
            pool_manager: 统一连接池管理器（推荐）
        """
        self.db = db
        self.pool_manager = pool_manager
    
    async def create(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any],
        student_feedback: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建批改结果"""
        query = """
            INSERT INTO grading_results (
                submission_id, question_id, score, max_score, confidence_score,
                visual_annotations, agent_trace, student_feedback
            )
            VALUES (
                %(submission_id)s, %(question_id)s, %(score)s, %(max_score)s,
                %(confidence_score)s, %(visual_annotations)s, %(agent_trace)s,
                %(student_feedback)s
            )
            RETURNING submission_id, question_id, score, max_score, confidence_score,
                      visual_annotations, agent_trace, student_feedback, created_at, updated_at
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "question_id": question_id,
                        "score": score,
                        "max_score": max_score,
                        "confidence_score": confidence_score,
                        "visual_annotations": json.dumps(visual_annotations),
                        "agent_trace": json.dumps(agent_trace),
                        "student_feedback": json.dumps(student_feedback)
                    }
                )
                result = await cur.fetchone()
                return self._format_result(result)
    
    async def get_by_composite_key(
        self,
        submission_id: str,
        question_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据复合键获取批改结果"""
        query = """
            SELECT submission_id, question_id, score, max_score, confidence_score,
                   visual_annotations, agent_trace, student_feedback, created_at, updated_at
            FROM grading_results
            WHERE submission_id = %(submission_id)s AND question_id = %(question_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "question_id": question_id
                    }
                )
                result = await cur.fetchone()
                return self._format_result(result) if result else None
    
    async def get_by_submission(self, submission_id: str) -> List[Dict[str, Any]]:
        """获取提交的所有批改结果"""
        query = """
            SELECT submission_id, question_id, score, max_score, confidence_score,
                   visual_annotations, agent_trace, student_feedback, created_at, updated_at
            FROM grading_results
            WHERE submission_id = %(submission_id)s
            ORDER BY question_id
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"submission_id": UUID(submission_id)})
                results = await cur.fetchall()
                return [self._format_result(row) for row in results]
    
    async def get_by_submission_id(self, submission_id: str) -> List[Dict[str, Any]]:
        """获取提交的所有批改结果（别名方法）"""
        return await self.get_by_submission(submission_id)
    
    async def update_score(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        feedback: Optional[str] = None
    ) -> bool:
        """更新题目评分和反馈"""
        updates = ["score = %(score)s", "updated_at = NOW()"]
        params = {
            "submission_id": UUID(submission_id),
            "question_id": question_id,
            "score": score
        }
        
        if feedback is not None:
            updates.append("student_feedback = %(student_feedback)s")
            params["student_feedback"] = json.dumps({"text": feedback})
        
        query = f"""
            UPDATE grading_results
            SET {', '.join(updates)}
            WHERE submission_id = %(submission_id)s AND question_id = %(question_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount > 0
    
    async def update(
        self,
        submission_id: str,
        question_id: str,
        score: Optional[float] = None,
        confidence_score: Optional[float] = None,
        visual_annotations: Optional[List[Dict[str, Any]]] = None,
        agent_trace: Optional[Dict[str, Any]] = None,
        student_feedback: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新批改结果"""
        updates = []
        params = {
            "submission_id": UUID(submission_id),
            "question_id": question_id
        }
        
        if score is not None:
            updates.append("score = %(score)s")
            params["score"] = score
        
        if confidence_score is not None:
            updates.append("confidence_score = %(confidence_score)s")
            params["confidence_score"] = confidence_score
        
        if visual_annotations is not None:
            updates.append("visual_annotations = %(visual_annotations)s")
            params["visual_annotations"] = json.dumps(visual_annotations)
        
        if agent_trace is not None:
            updates.append("agent_trace = %(agent_trace)s")
            params["agent_trace"] = json.dumps(agent_trace)
        
        if student_feedback is not None:
            updates.append("student_feedback = %(student_feedback)s")
            params["student_feedback"] = json.dumps(student_feedback)
        
        if not updates:
            return False
        
        updates.append("updated_at = NOW()")
        
        query = f"""
            UPDATE grading_results
            SET {', '.join(updates)}
            WHERE submission_id = %(submission_id)s AND question_id = %(question_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount > 0
    
    async def get_low_confidence_results(
        self,
        threshold: float = 0.75,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取低置信度的批改结果"""
        query = """
            SELECT submission_id, question_id, score, max_score, confidence_score,
                   visual_annotations, agent_trace, student_feedback, created_at, updated_at
            FROM grading_results
            WHERE confidence_score < %(threshold)s
            ORDER BY confidence_score ASC, created_at DESC
            LIMIT %(limit)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "threshold": threshold,
                        "limit": limit
                    }
                )
                results = await cur.fetchall()
                return [self._format_result(row) for row in results]
    
    async def delete(self, submission_id: str, question_id: str) -> bool:
        """删除批改结果"""
        query = """
            DELETE FROM grading_results
            WHERE submission_id = %(submission_id)s AND question_id = %(question_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "question_id": question_id
                    }
                )
                return cur.rowcount > 0
    
    async def delete_by_submission(self, submission_id: str) -> int:
        """删除提交的所有批改结果"""
        query = "DELETE FROM grading_results WHERE submission_id = %(submission_id)s"
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"submission_id": UUID(submission_id)})
                return cur.rowcount
    
    async def save_with_submission_update(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any],
        student_feedback: Dict[str, Any],
        new_submission_status: Optional[Union[str, SubmissionStatus]] = None,
        total_score: Optional[float] = None,
        max_total_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        在单个事务中保存批改结果并更新提交状态
        
        此方法确保 grading_results 表更新和 submissions 状态更新
        在同一数据库事务中完成，要么全部成功要么全部回滚。
        
        Args:
            submission_id: 提交 ID
            question_id: 题目 ID
            score: 得分
            max_score: 满分
            confidence_score: 置信度分数
            visual_annotations: 视觉标注
            agent_trace: 智能体追踪
            student_feedback: 学生反馈
            new_submission_status: 新的提交状态（可选）
            total_score: 总分（可选）
            max_total_score: 满分总分（可选）
            
        Returns:
            Dict[str, Any]: 保存的批改结果
            
        Raises:
            TransactionError: 事务执行失败时抛出
            
        验证：需求 2.2, 2.3
        """
        if self.pool_manager is None:
            raise TransactionError("需要 UnifiedPoolManager 来执行事务性操作")
        
        # 准备批改结果插入 SQL
        grading_insert_query = """
            INSERT INTO grading_results (
                submission_id, question_id, score, max_score, confidence_score,
                visual_annotations, agent_trace, student_feedback
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (submission_id, question_id) 
            DO UPDATE SET
                score = EXCLUDED.score,
                max_score = EXCLUDED.max_score,
                confidence_score = EXCLUDED.confidence_score,
                visual_annotations = EXCLUDED.visual_annotations,
                agent_trace = EXCLUDED.agent_trace,
                student_feedback = EXCLUDED.student_feedback,
                updated_at = NOW()
            RETURNING submission_id, question_id, score, max_score, confidence_score,
                      visual_annotations, agent_trace, student_feedback, created_at, updated_at
        """
        
        try:
            async with self.pool_manager.pg_transaction() as conn:
                # 1. 保存批改结果
                result = await conn.execute(
                    grading_insert_query,
                    (
                        UUID(submission_id),
                        question_id,
                        score,
                        max_score,
                        confidence_score,
                        json.dumps(visual_annotations),
                        json.dumps(agent_trace),
                        json.dumps(student_feedback),
                    )
                )
                grading_row = await result.fetchone()
                
                # 2. 更新提交状态（如果需要）
                if new_submission_status is not None or total_score is not None:
                    updates = ["updated_at = NOW()"]
                    params = [UUID(submission_id)]
                    
                    if new_submission_status is not None:
                        status_value = (
                            new_submission_status.value 
                            if isinstance(new_submission_status, SubmissionStatus) 
                            else new_submission_status
                        )
                        updates.insert(0, "status = %s")
                        params.insert(0, status_value)
                    
                    if total_score is not None:
                        updates.insert(0, "total_score = %s")
                        params.insert(0, total_score)
                    
                    if max_total_score is not None:
                        updates.insert(0, "max_total_score = %s")
                        params.insert(0, max_total_score)
                    
                    submission_update_query = f"""
                        UPDATE submissions
                        SET {', '.join(updates)}
                        WHERE submission_id = %s
                    """
                    await conn.execute(submission_update_query, params)
                
                logger.debug(
                    f"事务性保存完成: submission_id={submission_id}, "
                    f"question_id={question_id}, score={score}"
                )
                
                return self._format_result(grading_row)
                
        except Exception as e:
            logger.error(f"事务性保存失败: {e}")
            raise TransactionError(f"事务性保存失败: {e}") from e
    
    async def batch_save_with_submission_update(
        self,
        submission_id: str,
        grading_results: List[Dict[str, Any]],
        new_submission_status: Optional[Union[str, SubmissionStatus]] = None,
        total_score: Optional[float] = None,
        max_total_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        在单个事务中批量保存批改结果并更新提交状态
        
        此方法确保所有 grading_results 表更新和 submissions 状态更新
        在同一数据库事务中完成，要么全部成功要么全部回滚。
        
        Args:
            submission_id: 提交 ID
            grading_results: 批改结果列表，每个元素包含:
                - question_id: 题目 ID
                - score: 得分
                - max_score: 满分
                - confidence_score: 置信度分数
                - visual_annotations: 视觉标注
                - agent_trace: 智能体追踪
                - student_feedback: 学生反馈
            new_submission_status: 新的提交状态（可选）
            total_score: 总分（可选）
            max_total_score: 满分总分（可选）
            
        Returns:
            List[Dict[str, Any]]: 保存的批改结果列表
            
        Raises:
            TransactionError: 事务执行失败时抛出
            
        验证：需求 2.2, 2.3
        """
        if self.pool_manager is None:
            raise TransactionError("需要 UnifiedPoolManager 来执行事务性操作")
        
        if not grading_results:
            return []
        
        grading_insert_query = """
            INSERT INTO grading_results (
                submission_id, question_id, score, max_score, confidence_score,
                visual_annotations, agent_trace, student_feedback
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (submission_id, question_id) 
            DO UPDATE SET
                score = EXCLUDED.score,
                max_score = EXCLUDED.max_score,
                confidence_score = EXCLUDED.confidence_score,
                visual_annotations = EXCLUDED.visual_annotations,
                agent_trace = EXCLUDED.agent_trace,
                student_feedback = EXCLUDED.student_feedback,
                updated_at = NOW()
            RETURNING submission_id, question_id, score, max_score, confidence_score,
                      visual_annotations, agent_trace, student_feedback, created_at, updated_at
        """
        
        try:
            async with self.pool_manager.pg_transaction() as conn:
                saved_results = []
                
                # 1. 批量保存批改结果
                for gr in grading_results:
                    result = await conn.execute(
                        grading_insert_query,
                        (
                            UUID(submission_id),
                            gr["question_id"],
                            gr["score"],
                            gr["max_score"],
                            gr["confidence_score"],
                            json.dumps(gr.get("visual_annotations", [])),
                            json.dumps(gr.get("agent_trace", {})),
                            json.dumps(gr.get("student_feedback", {})),
                        )
                    )
                    row = await result.fetchone()
                    saved_results.append(self._format_result(row))
                
                # 2. 更新提交状态（如果需要）
                if new_submission_status is not None or total_score is not None:
                    updates = ["updated_at = NOW()"]
                    params = [UUID(submission_id)]
                    
                    if new_submission_status is not None:
                        status_value = (
                            new_submission_status.value 
                            if isinstance(new_submission_status, SubmissionStatus) 
                            else new_submission_status
                        )
                        updates.insert(0, "status = %s")
                        params.insert(0, status_value)
                    
                    if total_score is not None:
                        updates.insert(0, "total_score = %s")
                        params.insert(0, total_score)
                    
                    if max_total_score is not None:
                        updates.insert(0, "max_total_score = %s")
                        params.insert(0, max_total_score)
                    
                    submission_update_query = f"""
                        UPDATE submissions
                        SET {', '.join(updates)}
                        WHERE submission_id = %s
                    """
                    await conn.execute(submission_update_query, params)
                
                logger.debug(
                    f"批量事务性保存完成: submission_id={submission_id}, "
                    f"count={len(saved_results)}"
                )
                
                return saved_results
                
        except Exception as e:
            logger.error(f"批量事务性保存失败: {e}")
            raise TransactionError(f"批量事务性保存失败: {e}") from e
    
    async def save_with_checkpoint(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any],
        student_feedback: Dict[str, Any],
        checkpoint_data: bytes,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str = "",
        is_compressed: bool = False,
        is_delta: bool = False,
        base_checkpoint_id: Optional[str] = None,
        new_submission_status: Optional[Union[str, SubmissionStatus]] = None,
    ) -> Dict[str, Any]:
        """
        在单个事务中保存批改结果、检查点和更新提交状态
        
        此方法确保 grading_results、enhanced_checkpoints 和 submissions 
        的更新在同一数据库事务中完成，要么全部成功要么全部回滚。
        
        Args:
            submission_id: 提交 ID
            question_id: 题目 ID
            score: 得分
            max_score: 满分
            confidence_score: 置信度分数
            visual_annotations: 视觉标注
            agent_trace: 智能体追踪
            student_feedback: 学生反馈
            checkpoint_data: 检查点数据
            thread_id: LangGraph 线程 ID
            checkpoint_id: 检查点 ID
            checkpoint_ns: 检查点命名空间
            is_compressed: 是否已压缩
            is_delta: 是否为增量
            base_checkpoint_id: 基础检查点 ID
            new_submission_status: 新的提交状态（可选）
            
        Returns:
            Dict[str, Any]: 保存的批改结果
            
        Raises:
            TransactionError: 事务执行失败时抛出
            
        验证：需求 2.2, 2.3
        """
        if self.pool_manager is None:
            raise TransactionError("需要 UnifiedPoolManager 来执行事务性操作")
        
        grading_insert_query = """
            INSERT INTO grading_results (
                submission_id, question_id, score, max_score, confidence_score,
                visual_annotations, agent_trace, student_feedback
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (submission_id, question_id) 
            DO UPDATE SET
                score = EXCLUDED.score,
                max_score = EXCLUDED.max_score,
                confidence_score = EXCLUDED.confidence_score,
                visual_annotations = EXCLUDED.visual_annotations,
                agent_trace = EXCLUDED.agent_trace,
                student_feedback = EXCLUDED.student_feedback,
                updated_at = NOW()
            RETURNING submission_id, question_id, score, max_score, confidence_score,
                      visual_annotations, agent_trace, student_feedback, created_at, updated_at
        """
        
        checkpoint_insert_query = """
            INSERT INTO enhanced_checkpoints (
                thread_id, checkpoint_ns, checkpoint_id, checkpoint_data,
                is_compressed, is_delta, base_checkpoint_id, data_size_bytes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) 
            DO UPDATE SET
                checkpoint_data = EXCLUDED.checkpoint_data,
                is_compressed = EXCLUDED.is_compressed,
                is_delta = EXCLUDED.is_delta,
                base_checkpoint_id = EXCLUDED.base_checkpoint_id,
                data_size_bytes = EXCLUDED.data_size_bytes
        """
        
        try:
            async with self.pool_manager.pg_transaction() as conn:
                # 1. 保存批改结果
                result = await conn.execute(
                    grading_insert_query,
                    (
                        UUID(submission_id),
                        question_id,
                        score,
                        max_score,
                        confidence_score,
                        json.dumps(visual_annotations),
                        json.dumps(agent_trace),
                        json.dumps(student_feedback),
                    )
                )
                grading_row = await result.fetchone()
                
                # 2. 保存检查点
                await conn.execute(
                    checkpoint_insert_query,
                    (
                        thread_id,
                        checkpoint_ns,
                        checkpoint_id,
                        checkpoint_data,
                        is_compressed,
                        is_delta,
                        base_checkpoint_id,
                        len(checkpoint_data),
                    )
                )
                
                # 3. 更新提交状态（如果需要）
                if new_submission_status is not None:
                    status_value = (
                        new_submission_status.value 
                        if isinstance(new_submission_status, SubmissionStatus) 
                        else new_submission_status
                    )
                    submission_update_query = """
                        UPDATE submissions
                        SET status = %s, updated_at = NOW()
                        WHERE submission_id = %s
                    """
                    await conn.execute(
                        submission_update_query, 
                        (status_value, UUID(submission_id))
                    )
                
                logger.debug(
                    f"事务性保存（含检查点）完成: submission_id={submission_id}, "
                    f"question_id={question_id}, checkpoint_id={checkpoint_id}"
                )
                
                return self._format_result(grading_row)
                
        except Exception as e:
            logger.error(f"事务性保存（含检查点）失败: {e}")
            raise TransactionError(f"事务性保存（含检查点）失败: {e}") from e
    
    def _format_result(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """格式化批改结果"""
        if not row:
            return {}
        
        return {
            "submission_id": str(row["submission_id"]),
            "question_id": row["question_id"],
            "score": float(row["score"]) if row["score"] else None,
            "max_score": float(row["max_score"]) if row["max_score"] else None,
            "confidence_score": float(row["confidence_score"]) if row["confidence_score"] else None,
            "visual_annotations": row["visual_annotations"],
            "agent_trace": row["agent_trace"],
            "student_feedback": row["student_feedback"],
            "created_at": row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else row["created_at"],
            "updated_at": row["updated_at"].isoformat() if isinstance(row["updated_at"], datetime) else row["updated_at"]
        }
