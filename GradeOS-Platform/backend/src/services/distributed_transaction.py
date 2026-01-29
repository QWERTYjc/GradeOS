"""
分布式事务协调器

采用 Saga 模式协调跨组件的分布式事务，包括：
- 缓存写入
- 数据库写入
- 通知发送

验证：需求 4.1, 4.2, 4.3, 4.4, 4.5
"""

import asyncio
import logging
import uuid
from typing import List, Callable, Any, Optional, Awaitable, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError


logger = logging.getLogger(__name__)


class SagaStepStatus(str, Enum):
    """
    Saga 步骤状态枚举

    验证：需求 4.1
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"


class SagaTransactionStatus(str, Enum):
    """Saga 事务最终状态枚举"""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"
    REQUIRES_INTERVENTION = "requires_intervention"


@dataclass
class SagaStep:
    """
    Saga 步骤定义

    每个步骤包含：
    - 名称：用于日志和追踪
    - 动作：要执行的异步操作
    - 补偿：失败时的回滚操作
    - 状态：当前执行状态

    验证：需求 4.1
    """

    name: str
    action: Callable[[], Awaitable[Any]]
    compensation: Callable[[], Awaitable[None]]
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于日志记录）"""
        return {
            "name": self.name,
            "status": self.status.value,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class SagaTransaction:
    """Saga 事务记录"""

    saga_id: str
    steps: List[Dict[str, Any]]
    final_status: SagaTransactionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "saga_id": self.saga_id,
            "steps": self.steps,
            "final_status": self.final_status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class DistributedTransactionCoordinator:
    """
    分布式事务协调器

    采用 Saga 模式协调跨组件事务：
    - 按顺序执行步骤
    - 记录每步状态
    - 失败时触发补偿（逆序执行）
    - 记录详细事务日志

    验证：需求 4.1, 4.2, 4.3, 4.4, 4.5
    """

    def __init__(
        self,
        pool_manager: UnifiedPoolManager,
        max_compensation_retries: int = 3,
        enable_logging: bool = True,
    ):
        """
        初始化分布式事务协调器

        Args:
            pool_manager: 统一连接池管理器
            max_compensation_retries: 补偿操作最大重试次数
            enable_logging: 是否启用事务日志记录到数据库
        """
        self.pool_manager = pool_manager
        self.max_compensation_retries = max_compensation_retries
        self.enable_logging = enable_logging
        self._logger = logger

    def generate_saga_id(self) -> str:
        """生成唯一的 Saga ID"""
        return str(uuid.uuid4())

    async def execute_saga(self, saga_id: str, steps: List[SagaStep]) -> bool:
        """
        执行 Saga 事务

        按顺序执行所有步骤，任一步骤失败时执行补偿操作。

        Args:
            saga_id: Saga 事务 ID
            steps: 要执行的步骤列表

        Returns:
            事务是否成功完成

        验证：需求 4.1, 4.2
        """
        started_at = datetime.now(timezone.utc)
        completed_steps: List[SagaStep] = []
        final_status = SagaTransactionStatus.STARTED
        error_message: Optional[str] = None

        self._logger.info(f"开始执行 Saga 事务: {saga_id}, 步骤数: {len(steps)}")

        # 记录事务开始
        if self.enable_logging:
            await self._log_transaction_start(saga_id, steps, started_at)

        try:
            # 按顺序执行步骤
            for step in steps:
                step.status = SagaStepStatus.RUNNING
                step.started_at = datetime.now(timezone.utc)

                self._logger.debug(f"Saga {saga_id}: 执行步骤 '{step.name}'")

                try:
                    step.result = await step.action()
                    step.status = SagaStepStatus.COMPLETED
                    step.completed_at = datetime.now(timezone.utc)
                    completed_steps.append(step)

                    self._logger.debug(f"Saga {saga_id}: 步骤 '{step.name}' 完成")

                except Exception as e:
                    step.status = SagaStepStatus.FAILED
                    step.error = str(e)
                    step.completed_at = datetime.now(timezone.utc)
                    error_message = f"步骤 '{step.name}' 失败: {e}"

                    self._logger.error(f"Saga {saga_id}: 步骤 '{step.name}' 失败: {e}")

                    # 触发补偿
                    compensation_success = await self.compensate(saga_id, completed_steps)

                    if compensation_success:
                        final_status = SagaTransactionStatus.COMPENSATED
                    else:
                        final_status = SagaTransactionStatus.COMPENSATION_FAILED
                        error_message += "; 补偿操作也失败，需要人工干预"

                    # 记录事务结束
                    if self.enable_logging:
                        await self.log_transaction(
                            saga_id, steps, final_status, started_at, error_message
                        )

                    return False

            # 所有步骤成功
            final_status = SagaTransactionStatus.COMPLETED
            self._logger.info(f"Saga 事务 {saga_id} 成功完成")

            # 记录事务结束
            if self.enable_logging:
                await self.log_transaction(saga_id, steps, final_status, started_at)

            return True

        except Exception as e:
            error_message = f"Saga 事务执行异常: {e}"
            self._logger.error(f"Saga {saga_id}: {error_message}")

            # 尝试补偿
            if completed_steps:
                compensation_success = await self.compensate(saga_id, completed_steps)
                if compensation_success:
                    final_status = SagaTransactionStatus.COMPENSATED
                else:
                    final_status = SagaTransactionStatus.COMPENSATION_FAILED
            else:
                final_status = SagaTransactionStatus.FAILED

            # 记录事务结束
            if self.enable_logging:
                await self.log_transaction(saga_id, steps, final_status, started_at, error_message)

            return False

    async def compensate(self, saga_id: str, completed_steps: List[SagaStep]) -> bool:
        """
        执行补偿操作

        逆序执行已完成步骤的补偿操作。

        Args:
            saga_id: Saga 事务 ID
            completed_steps: 已完成的步骤列表

        Returns:
            补偿是否全部成功

        验证：需求 4.2
        """
        if not completed_steps:
            return True

        self._logger.info(f"Saga {saga_id}: 开始补偿操作，需补偿 {len(completed_steps)} 个步骤")

        all_compensated = True

        # 逆序执行补偿
        for step in reversed(completed_steps):
            step.status = SagaStepStatus.COMPENSATING

            self._logger.debug(f"Saga {saga_id}: 补偿步骤 '{step.name}'")

            success = False
            last_error: Optional[str] = None

            # 重试补偿操作
            for attempt in range(self.max_compensation_retries):
                try:
                    await step.compensation()
                    step.status = SagaStepStatus.COMPENSATED
                    success = True

                    self._logger.debug(f"Saga {saga_id}: 步骤 '{step.name}' 补偿成功")
                    break

                except Exception as e:
                    last_error = str(e)
                    self._logger.warning(
                        f"Saga {saga_id}: 步骤 '{step.name}' 补偿失败 "
                        f"(尝试 {attempt + 1}/{self.max_compensation_retries}): {e}"
                    )

                    if attempt < self.max_compensation_retries - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避

            if not success:
                step.status = SagaStepStatus.COMPENSATION_FAILED
                step.error = f"补偿失败: {last_error}"
                all_compensated = False

                self._logger.error(f"Saga {saga_id}: 步骤 '{step.name}' 补偿最终失败，需要人工干预")

        if all_compensated:
            self._logger.info(f"Saga {saga_id}: 所有补偿操作成功完成")
        else:
            self._logger.error(f"Saga {saga_id}: 部分补偿操作失败，需要人工干预")

        return all_compensated

    async def _log_transaction_start(
        self, saga_id: str, steps: List[SagaStep], started_at: datetime
    ) -> None:
        """记录事务开始"""
        try:
            async with self.pool_manager.pg_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO saga_transactions 
                    (saga_id, steps, final_status, started_at, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (saga_id) DO UPDATE SET
                        steps = EXCLUDED.steps,
                        final_status = EXCLUDED.final_status,
                        started_at = EXCLUDED.started_at
                    """,
                    (
                        saga_id,
                        [step.to_dict() for step in steps],
                        SagaTransactionStatus.STARTED.value,
                        started_at,
                        datetime.now(timezone.utc),
                    ),
                )
        except PoolNotInitializedError:
            self._logger.warning("数据库连接池未初始化，跳过事务日志记录")
        except Exception as e:
            self._logger.warning(f"记录事务开始失败: {e}")

    async def log_transaction(
        self,
        saga_id: str,
        steps: List[SagaStep],
        final_status: SagaTransactionStatus,
        started_at: datetime,
        error_message: Optional[str] = None,
    ) -> None:
        """
        记录事务日志

        记录事务的完整执行过程，支持人工干预查询。

        Args:
            saga_id: Saga 事务 ID
            steps: 步骤列表
            final_status: 最终状态
            started_at: 开始时间
            error_message: 错误信息（可选）

        验证：需求 4.5
        """
        completed_at = datetime.now(timezone.utc)

        try:
            async with self.pool_manager.pg_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO saga_transactions 
                    (saga_id, steps, final_status, started_at, completed_at, 
                     error_message, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (saga_id) DO UPDATE SET
                        steps = EXCLUDED.steps,
                        final_status = EXCLUDED.final_status,
                        completed_at = EXCLUDED.completed_at,
                        error_message = EXCLUDED.error_message
                    """,
                    (
                        saga_id,
                        [step.to_dict() for step in steps],
                        final_status.value,
                        started_at,
                        completed_at,
                        error_message,
                        datetime.now(timezone.utc),
                    ),
                )

            self._logger.debug(f"Saga {saga_id}: 事务日志已记录")

        except PoolNotInitializedError:
            self._logger.warning("数据库连接池未初始化，跳过事务日志记录")
        except Exception as e:
            self._logger.warning(f"记录事务日志失败: {e}")

    async def get_transaction_log(self, saga_id: str) -> Optional[SagaTransaction]:
        """
        获取事务日志

        Args:
            saga_id: Saga 事务 ID

        Returns:
            事务记录，未找到返回 None
        """
        try:
            async with self.pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT saga_id, steps, final_status, started_at, 
                           completed_at, error_message
                    FROM saga_transactions
                    WHERE saga_id = %s
                    """,
                    (saga_id,),
                )
                row = await result.fetchone()

                if row:
                    return SagaTransaction(
                        saga_id=row["saga_id"],
                        steps=row["steps"],
                        final_status=SagaTransactionStatus(row["final_status"]),
                        started_at=row["started_at"],
                        completed_at=row["completed_at"],
                        error_message=row["error_message"],
                    )
                return None

        except PoolNotInitializedError:
            self._logger.warning("数据库连接池未初始化")
            return None
        except Exception as e:
            self._logger.warning(f"获取事务日志失败: {e}")
            return None

    async def list_failed_transactions(self, limit: int = 100) -> List[SagaTransaction]:
        """
        列出需要人工干预的失败事务

        Args:
            limit: 返回数量限制

        Returns:
            失败事务列表

        验证：需求 4.5
        """
        try:
            async with self.pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT saga_id, steps, final_status, started_at, 
                           completed_at, error_message
                    FROM saga_transactions
                    WHERE final_status IN (%s, %s)
                    ORDER BY started_at DESC
                    LIMIT %s
                    """,
                    (
                        SagaTransactionStatus.COMPENSATION_FAILED.value,
                        SagaTransactionStatus.REQUIRES_INTERVENTION.value,
                        limit,
                    ),
                )
                rows = await result.fetchall()

                return [
                    SagaTransaction(
                        saga_id=row["saga_id"],
                        steps=row["steps"],
                        final_status=SagaTransactionStatus(row["final_status"]),
                        started_at=row["started_at"],
                        completed_at=row["completed_at"],
                        error_message=row["error_message"],
                    )
                    for row in rows
                ]

        except PoolNotInitializedError:
            self._logger.warning("数据库连接池未初始化")
            return []
        except Exception as e:
            self._logger.warning(f"列出失败事务失败: {e}")
            return []

    async def cleanup_partial_state(
        self, saga_id: str, cleanup_actions: Optional[List[Callable[[], Awaitable[None]]]] = None
    ) -> bool:
        """
        清理部分写入状态

        当 Activity 超时时，清理可能的部分写入状态。

        Args:
            saga_id: Saga 事务 ID
            cleanup_actions: 清理操作列表（可选）

        Returns:
            清理是否成功

        验证：需求 4.3
        """
        self._logger.info(f"Saga {saga_id}: 开始清理部分状态")

        all_cleaned = True

        if cleanup_actions:
            for i, action in enumerate(cleanup_actions):
                try:
                    await action()
                    self._logger.debug(f"Saga {saga_id}: 清理操作 {i + 1} 成功")
                except Exception as e:
                    all_cleaned = False
                    self._logger.error(f"Saga {saga_id}: 清理操作 {i + 1} 失败: {e}")

        # 更新事务状态
        if self.enable_logging:
            try:
                async with self.pool_manager.pg_connection() as conn:
                    await conn.execute(
                        """
                        UPDATE saga_transactions
                        SET final_status = %s,
                            completed_at = %s,
                            error_message = COALESCE(error_message, '') || %s
                        WHERE saga_id = %s
                        """,
                        (
                            (
                                SagaTransactionStatus.REQUIRES_INTERVENTION.value
                                if not all_cleaned
                                else SagaTransactionStatus.COMPENSATED.value
                            ),
                            datetime.now(timezone.utc),
                            "; 已执行部分状态清理" if all_cleaned else "; 部分状态清理失败",
                            saga_id,
                        ),
                    )
            except Exception as e:
                self._logger.warning(f"更新事务状态失败: {e}")

        if all_cleaned:
            self._logger.info(f"Saga {saga_id}: 部分状态清理完成")
        else:
            self._logger.error(f"Saga {saga_id}: 部分状态清理失败，需要人工干预")

        return all_cleaned


class ReviewOverrideSagaBuilder:
    """
    审核覆盖事务构建器

    构建人工审核覆盖分数的 Saga 事务，包含：
    - 数据库更新
    - 缓存失效
    - 通知发送

    验证：需求 4.4
    """

    def __init__(
        self, coordinator: DistributedTransactionCoordinator, pool_manager: UnifiedPoolManager
    ):
        self.coordinator = coordinator
        self.pool_manager = pool_manager
        self._db_updated = False
        self._cache_invalidated = False
        self._notification_sent = False

    async def execute_review_override(
        self,
        submission_id: str,
        question_id: str,
        new_score: float,
        reviewer_id: str,
        reason: str,
        notify_callback: Optional[Callable[[], Awaitable[None]]] = None,
        cache_service: Optional[Any] = None,
    ) -> bool:
        """
        执行审核覆盖事务

        在单个 Saga 事务中完成：
        1. 数据库更新（更新分数和审核记录）
        2. 缓存失效（删除相关缓存）
        3. 通知发送（通知相关方）

        Args:
            submission_id: 提交 ID
            question_id: 题目 ID
            new_score: 新分数
            reviewer_id: 审核人 ID
            reason: 覆盖原因
            notify_callback: 通知回调函数
            cache_service: 缓存服务实例

        Returns:
            事务是否成功

        验证：需求 4.4
        """
        saga_id = self.coordinator.generate_saga_id()

        # 保存原始数据用于补偿
        original_data: Dict[str, Any] = {}

        # 步骤 1：数据库更新
        async def db_update_action() -> None:
            async with self.pool_manager.pg_transaction() as conn:
                # 获取原始数据
                result = await conn.execute(
                    """
                    SELECT score, reviewed, reviewer_id, review_reason
                    FROM grading_results
                    WHERE submission_id = %s AND question_id = %s
                    """,
                    (submission_id, question_id),
                )
                row = await result.fetchone()
                if row:
                    original_data["score"] = row["score"]
                    original_data["reviewed"] = row["reviewed"]
                    original_data["reviewer_id"] = row["reviewer_id"]
                    original_data["review_reason"] = row["review_reason"]

                # 更新分数
                await conn.execute(
                    """
                    UPDATE grading_results
                    SET score = %s, 
                        reviewed = TRUE,
                        reviewer_id = %s,
                        review_reason = %s,
                        reviewed_at = %s
                    WHERE submission_id = %s AND question_id = %s
                    """,
                    (
                        new_score,
                        reviewer_id,
                        reason,
                        datetime.now(timezone.utc),
                        submission_id,
                        question_id,
                    ),
                )
            self._db_updated = True

        async def db_update_compensation() -> None:
            if not self._db_updated:
                return
            async with self.pool_manager.pg_transaction() as conn:
                await conn.execute(
                    """
                    UPDATE grading_results
                    SET score = %s,
                        reviewed = %s,
                        reviewer_id = %s,
                        review_reason = %s,
                        reviewed_at = NULL
                    WHERE submission_id = %s AND question_id = %s
                    """,
                    (
                        original_data.get("score"),
                        original_data.get("reviewed", False),
                        original_data.get("reviewer_id"),
                        original_data.get("review_reason"),
                        submission_id,
                        question_id,
                    ),
                )
            self._db_updated = False

        # 步骤 2：缓存失效
        async def cache_invalidate_action() -> None:
            if cache_service is not None:
                await cache_service.invalidate_with_notification(
                    f"grading_result:{submission_id}:{question_id}"
                )
            self._cache_invalidated = True

        async def cache_invalidate_compensation() -> None:
            # 缓存失效的补偿：无需操作，缓存会自动重建
            self._cache_invalidated = False

        # 步骤 3：通知发送
        async def notify_action() -> None:
            if notify_callback is not None:
                await notify_callback()
            self._notification_sent = True

        async def notify_compensation() -> None:
            # 通知的补偿：记录需要发送撤销通知
            # 实际实现中可能需要发送撤销通知
            self._notification_sent = False

        # 构建步骤列表
        steps = [
            SagaStep(
                name="数据库更新",
                action=db_update_action,
                compensation=db_update_compensation,
            ),
            SagaStep(
                name="缓存失效",
                action=cache_invalidate_action,
                compensation=cache_invalidate_compensation,
            ),
            SagaStep(
                name="通知发送",
                action=notify_action,
                compensation=notify_compensation,
            ),
        ]

        return await self.coordinator.execute_saga(saga_id, steps)
