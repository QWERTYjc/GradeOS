"""批改日志服务

记录批改过程的完整上下文，支持改判记录和日志查询。
验证：需求 8.1, 8.2, 8.3, 8.4, 8.5
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from collections import deque

from src.models.grading_log import GradingLog, GradingLogCreate, GradingLogOverride
from src.utils.database import db


logger = logging.getLogger(__name__)


class GradingLogger:
    """批改日志服务

    功能：
    1. 记录批改日志（log_grading）
    2. 记录改判信息（log_override）
    3. 查询改判样本（get_override_samples）
    4. 日志写入容错（flush_pending）

    验证：需求 8.1, 8.2, 8.3, 8.4, 8.5
    """

    def __init__(self, max_pending_size: int = 1000):
        """初始化批改日志服务

        Args:
            max_pending_size: 暂存队列最大容量
        """
        self._pending_logs: deque = deque(maxlen=max_pending_size)
        self._flush_lock = asyncio.Lock()

    async def log_grading(self, log: GradingLog) -> str:
        """记录批改日志

        记录批改过程各阶段的详细信息：
        - 提取阶段：extracted_answer, extraction_confidence, evidence_snippets
        - 规范化阶段：normalized_answer, normalization_rules_applied
        - 匹配阶段：match_result, match_failure_reason
        - 评分阶段：score, max_score, confidence, reasoning_trace

        验证：需求 8.1, 8.2, 8.3

        Args:
            log: 批改日志对象

        Returns:
            log_id: 日志唯一标识

        Raises:
            Exception: 数据库写入失败时，日志会被暂存到本地队列
        """
        try:
            async with db.transaction() as conn:
                # 插入日志记录
                result = await conn.execute(
                    """
                    INSERT INTO grading_logs (
                        log_id, submission_id, question_id,
                        extracted_answer, extraction_confidence, evidence_snippets,
                        normalized_answer, normalization_rules_applied,
                        match_result, match_failure_reason,
                        score, max_score, confidence, reasoning_trace,
                        was_overridden, created_at
                    ) VALUES (
                        %(log_id)s, %(submission_id)s, %(question_id)s,
                        %(extracted_answer)s, %(extraction_confidence)s, %(evidence_snippets)s,
                        %(normalized_answer)s, %(normalization_rules_applied)s,
                        %(match_result)s, %(match_failure_reason)s,
                        %(score)s, %(max_score)s, %(confidence)s, %(reasoning_trace)s,
                        %(was_overridden)s, %(created_at)s
                    )
                    RETURNING log_id
                    """,
                    {
                        "log_id": log.log_id,
                        "submission_id": log.submission_id,
                        "question_id": log.question_id,
                        "extracted_answer": log.extracted_answer,
                        "extraction_confidence": log.extraction_confidence,
                        "evidence_snippets": log.evidence_snippets,
                        "normalized_answer": log.normalized_answer,
                        "normalization_rules_applied": log.normalization_rules_applied,
                        "match_result": log.match_result,
                        "match_failure_reason": log.match_failure_reason,
                        "score": log.score,
                        "max_score": log.max_score,
                        "confidence": log.confidence,
                        "reasoning_trace": log.reasoning_trace,
                        "was_overridden": log.was_overridden,
                        "created_at": log.created_at,
                    },
                )

                log_id = (await result.fetchone())[0]
                logger.info(f"批改日志已记录: {log_id}")
                return str(log_id)

        except Exception as e:
            logger.error(f"批改日志写入失败，暂存到本地队列: {e}")
            # 验证：需求 8.5 - 日志写入失败时暂存本地
            self._pending_logs.append(log)
            return log.log_id

    async def log_override(
        self, log_id: str, override_score: float, override_reason: str, teacher_id: str
    ) -> bool:
        """记录改判信息

        更新日志记录，标记为已改判，并记录改判详情。
        验证：需求 8.4

        Args:
            log_id: 日志ID
            override_score: 改判后的分数
            override_reason: 改判原因
            teacher_id: 改判教师ID

        Returns:
            是否成功更新
        """
        try:
            async with db.transaction() as conn:
                result = await conn.execute(
                    """
                    UPDATE grading_logs
                    SET was_overridden = TRUE,
                        override_score = %(override_score)s,
                        override_reason = %(override_reason)s,
                        override_teacher_id = %(override_teacher_id)s,
                        override_at = NOW()
                    WHERE log_id = %(log_id)s
                    """,
                    {
                        "log_id": log_id,
                        "override_score": override_score,
                        "override_reason": override_reason,
                        "override_teacher_id": teacher_id,
                    },
                )

                if result.rowcount > 0:
                    logger.info(f"改判日志已记录: {log_id}")
                    return True
                else:
                    logger.warning(f"未找到日志记录: {log_id}")
                    return False

        except Exception as e:
            logger.error(f"改判日志记录失败: {e}")
            return False

    async def get_override_samples(self, min_count: int = 100, days: int = 7) -> List[GradingLog]:
        """获取改判样本用于规则挖掘

        查询指定时间窗口内的改判记录，用于分析失败模式和生成规则补丁。
        验证：需求 9.1

        Args:
            min_count: 最小样本数量
            days: 时间窗口（天数）

        Returns:
            改判样本列表
        """
        try:
            async with db.connection() as conn:
                # 计算时间窗口
                cutoff_time = datetime.utcnow() - timedelta(days=days)

                result = await conn.execute(
                    """
                    SELECT 
                        log_id, submission_id, question_id,
                        extracted_answer, extraction_confidence, evidence_snippets,
                        normalized_answer, normalization_rules_applied,
                        match_result, match_failure_reason,
                        score, max_score, confidence, reasoning_trace,
                        was_overridden, override_score, override_reason,
                        override_teacher_id, override_at, created_at
                    FROM grading_logs
                    WHERE was_overridden = TRUE
                        AND override_at >= %(cutoff_time)s
                    ORDER BY override_at DESC
                    LIMIT %(limit)s
                    """,
                    {"cutoff_time": cutoff_time, "limit": min_count},
                )

                rows = await result.fetchall()

                # 转换为 GradingLog 对象
                samples = []
                for row in rows:
                    log = GradingLog(
                        log_id=str(row[0]),
                        submission_id=str(row[1]),
                        question_id=row[2],
                        extracted_answer=row[3],
                        extraction_confidence=float(row[4]) if row[4] else None,
                        evidence_snippets=row[5] or [],
                        normalized_answer=row[6],
                        normalization_rules_applied=row[7] or [],
                        match_result=row[8],
                        match_failure_reason=row[9],
                        score=float(row[10]) if row[10] else None,
                        max_score=float(row[11]) if row[11] else None,
                        confidence=float(row[12]) if row[12] else None,
                        reasoning_trace=row[13] or [],
                        was_overridden=row[14],
                        override_score=float(row[15]) if row[15] else None,
                        override_reason=row[16],
                        override_teacher_id=str(row[17]) if row[17] else None,
                        override_at=row[18],
                        created_at=row[19],
                    )
                    samples.append(log)

                logger.info(f"查询到 {len(samples)} 条改判样本")
                return samples

        except Exception as e:
            logger.error(f"查询改判样本失败: {e}")
            return []

    async def flush_pending(self) -> int:
        """刷新暂存的日志

        将本地暂存队列中的日志重新尝试写入数据库。
        验证：需求 8.5

        Returns:
            成功写入的日志数量
        """
        async with self._flush_lock:
            if not self._pending_logs:
                return 0

            success_count = 0
            failed_logs = []

            while self._pending_logs:
                log = self._pending_logs.popleft()
                try:
                    await self.log_grading(log)
                    success_count += 1
                except Exception as e:
                    logger.error(f"重试写入日志失败: {e}")
                    failed_logs.append(log)

            # 将失败的日志重新放回队列
            for log in failed_logs:
                self._pending_logs.append(log)

            logger.info(f"刷新暂存日志: 成功 {success_count}, 失败 {len(failed_logs)}")
            return success_count

    def get_pending_count(self) -> int:
        """获取暂存队列中的日志数量"""
        return len(self._pending_logs)


# 全局单例
_grading_logger: Optional[GradingLogger] = None


def get_grading_logger() -> GradingLogger:
    """获取批改日志服务单例"""
    global _grading_logger
    if _grading_logger is None:
        _grading_logger = GradingLogger()
    return _grading_logger
