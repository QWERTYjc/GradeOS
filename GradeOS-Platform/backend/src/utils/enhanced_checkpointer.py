"""
增强型 PostgreSQL 检查点器

提供增量状态存储、数据压缩、历史检查点恢复和进度心跳集成。

验证：需求 9.1, 9.2, 9.3, 9.4, 1.2
"""

import asyncio
import json
import logging
import uuid
import zlib
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from .pool_manager import UnifiedPoolManager, PoolNotInitializedError


logger = logging.getLogger(__name__)


class CheckpointSaveError(Exception):
    """检查点保存错误"""

    pass


class CheckpointRecoveryError(Exception):
    """检查点恢复错误"""

    pass


class ManualInterventionRequired(Exception):
    """需要人工干预的错误"""

    pass


class EnhancedPostgresCheckpointer(BaseCheckpointSaver):
    """
    增强型 PostgreSQL 检查点器

    特性：
    - 增量状态存储（仅保存变化的部分）
    - 大数据压缩（>1MB 使用 zlib）
    - 与任务执行心跳回调集成
    - 历史检查点恢复
    - 保存失败重试机制

    验证：需求 9.1, 9.2, 9.3, 9.4, 1.2
    """

    # 默认压缩阈值：1MB
    DEFAULT_COMPRESSION_THRESHOLD = 1024 * 1024
    # 默认最大重试次数
    DEFAULT_MAX_RETRIES = 3
    # 重试间隔（秒）
    RETRY_DELAY = 0.5

    def __init__(
        self,
        pool_manager: UnifiedPoolManager,
        compression_threshold: int = DEFAULT_COMPRESSION_THRESHOLD,
        heartbeat_callback: Optional[Callable[[str, float], None]] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        serde: Optional[JsonPlusSerializer] = None,
    ):
        """
        初始化增强型检查点器

        Args:
            pool_manager: 统一连接池管理器
            compression_threshold: 压缩阈值（字节），超过此大小的数据将被压缩
            heartbeat_callback: 进度心跳回调函数，签名为 (stage: str, progress: float)
            max_retries: 保存失败时的最大重试次数
            serde: 序列化器，默认使用 JsonPlusSerializer
        """
        super().__init__(serde=serde or JsonPlusSerializer())
        self.pool_manager = pool_manager
        self.compression_threshold = compression_threshold
        self.heartbeat_callback = heartbeat_callback
        self.max_retries = max_retries
        self._setup_done = False

    def _report_heartbeat(self, stage: str, progress: float) -> None:
        """
        报告心跳进度

        Args:
            stage: 当前阶段
            progress: 进度百分比 (0.0 - 1.0)

        验证：需求 1.2
        """
        if self.heartbeat_callback:
            try:
                self.heartbeat_callback(stage, progress)
            except Exception as e:
                logger.warning(f"心跳回调失败: {e}")

    def _compress(self, data: bytes) -> Tuple[bytes, bool]:
        """
        压缩数据（如果超过阈值）

        Args:
            data: 原始数据

        Returns:
            Tuple[bytes, bool]: (处理后的数据, 是否已压缩)

        验证：需求 9.3
        """
        if len(data) > self.compression_threshold:
            compressed = zlib.compress(data, level=6)
            # 只有压缩后更小才使用压缩
            if len(compressed) < len(data):
                return compressed, True
        return data, False

    def _decompress(self, data: bytes, is_compressed: bool) -> bytes:
        """
        解压数据

        Args:
            data: 可能被压缩的数据
            is_compressed: 是否已压缩

        Returns:
            bytes: 解压后的数据
        """
        if is_compressed:
            return zlib.decompress(data)
        return data

    def _compute_delta(
        self, previous: Optional[Dict[str, Any]], current: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        计算状态增量

        Args:
            previous: 前一个状态
            current: 当前状态

        Returns:
            Tuple[Dict[str, Any], bool]: (增量数据, 是否为增量)

        验证：需求 9.1
        """
        if previous is None:
            return current, False

        delta = {}
        has_changes = False

        # 检查新增和修改的键
        for key, value in current.items():
            if key not in previous:
                delta[key] = {"op": "add", "value": value}
                has_changes = True
            elif previous[key] != value:
                delta[key] = {"op": "update", "value": value}
                has_changes = True

        # 检查删除的键
        for key in previous:
            if key not in current:
                delta[key] = {"op": "delete"}
                has_changes = True

        if not has_changes:
            return {}, True  # 空增量

        return delta, True

    def _apply_delta(self, base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用增量到基础状态

        Args:
            base: 基础状态
            delta: 增量数据

        Returns:
            Dict[str, Any]: 重建后的完整状态
        """
        result = base.copy()

        for key, change in delta.items():
            op = change.get("op")
            if op == "add" or op == "update":
                result[key] = change["value"]
            elif op == "delete":
                result.pop(key, None)

        return result

    async def setup(self) -> None:
        """
        设置检查点表结构

        创建增强型检查点表，支持增量存储和压缩标记。
        """
        if self._setup_done:
            return

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS enhanced_checkpoints (
            thread_id VARCHAR(255) NOT NULL,
            checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
            checkpoint_id VARCHAR(255) NOT NULL,
            parent_checkpoint_id VARCHAR(255),
            checkpoint_data BYTEA NOT NULL,
            metadata JSONB,
            is_compressed BOOLEAN DEFAULT FALSE,
            is_delta BOOLEAN DEFAULT FALSE,
            base_checkpoint_id VARCHAR(255),
            data_size_bytes INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_enhanced_checkpoints_thread 
            ON enhanced_checkpoints(thread_id, checkpoint_ns);
        CREATE INDEX IF NOT EXISTS idx_enhanced_checkpoints_created 
            ON enhanced_checkpoints(created_at);
        CREATE INDEX IF NOT EXISTS idx_enhanced_checkpoints_parent 
            ON enhanced_checkpoints(parent_checkpoint_id);
        
        CREATE TABLE IF NOT EXISTS enhanced_checkpoint_writes (
            thread_id VARCHAR(255) NOT NULL,
            checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
            checkpoint_id VARCHAR(255) NOT NULL,
            task_id VARCHAR(255) NOT NULL,
            idx INTEGER NOT NULL,
            channel VARCHAR(255) NOT NULL,
            type VARCHAR(255),
            blob BYTEA,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        );
        """

        async with self.pool_manager.pg_connection() as conn:
            await conn.execute(create_table_sql)

        self._setup_done = True
        logger.info("增强型检查点表结构已创建")

    async def aget(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """
        异步获取最新检查点

        Args:
            config: 配置字典，包含 thread_id 和可选的 checkpoint_id

        Returns:
            Optional[CheckpointTuple]: 检查点元组，如果不存在则返回 None

        验证：需求 9.2
        """
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = configurable.get("checkpoint_id")

        if not thread_id:
            return None

        self._report_heartbeat("checkpoint_get", 0.0)

        try:
            async with self.pool_manager.pg_connection() as conn:
                if checkpoint_id:
                    # 获取指定检查点
                    query = """
                    SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, 
                           metadata, is_compressed, is_delta, base_checkpoint_id
                    FROM enhanced_checkpoints
                    WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s
                    """
                    result = await conn.execute(query, (thread_id, checkpoint_ns, checkpoint_id))
                else:
                    # 获取最新检查点
                    query = """
                    SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, 
                           metadata, is_compressed, is_delta, base_checkpoint_id
                    FROM enhanced_checkpoints
                    WHERE thread_id = %s AND checkpoint_ns = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                    result = await conn.execute(query, (thread_id, checkpoint_ns))

                row = await result.fetchone()

                if not row:
                    return None

                self._report_heartbeat("checkpoint_get", 0.5)

                # 解压和反序列化
                checkpoint_data = self._decompress(
                    bytes(row["checkpoint_data"]), row["is_compressed"]
                )

                # 如果是增量，需要重建完整状态
                if row["is_delta"] and row["base_checkpoint_id"]:
                    checkpoint = await self._rebuild_from_delta(
                        conn, thread_id, checkpoint_ns, row["base_checkpoint_id"], checkpoint_data
                    )
                else:
                    checkpoint = self.serde.loads_typed(("json", checkpoint_data.decode("utf-8")))

                metadata = row["metadata"] or {}

                # 获取 pending writes
                writes_query = """
                SELECT task_id, channel, type, blob
                FROM enhanced_checkpoint_writes
                WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s
                ORDER BY task_id, idx
                """
                writes_result = await conn.execute(
                    writes_query, (thread_id, checkpoint_ns, row["checkpoint_id"])
                )
                writes_rows = await writes_result.fetchall()

                pending_writes = []
                for w in writes_rows:
                    if w["blob"]:
                        value = self.serde.loads_typed((w["type"], w["blob"]))
                    else:
                        value = None
                    pending_writes.append((w["task_id"], w["channel"], value))

                self._report_heartbeat("checkpoint_get", 1.0)

                return CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": row["checkpoint_id"],
                        }
                    },
                    checkpoint=checkpoint,
                    metadata=CheckpointMetadata(**metadata) if metadata else CheckpointMetadata(),
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": row["parent_checkpoint_id"],
                            }
                        }
                        if row["parent_checkpoint_id"]
                        else None
                    ),
                    pending_writes=pending_writes,
                )

        except Exception as e:
            logger.error(f"获取检查点失败: {e}")
            raise CheckpointRecoveryError(f"获取检查点失败: {e}") from e

    async def _rebuild_from_delta(
        self, conn, thread_id: str, checkpoint_ns: str, base_checkpoint_id: str, delta_data: bytes
    ) -> Dict[str, Any]:
        """
        从增量重建完整状态

        Args:
            conn: 数据库连接
            thread_id: 线程 ID
            checkpoint_ns: 检查点命名空间
            base_checkpoint_id: 基础检查点 ID
            delta_data: 增量数据

        Returns:
            Dict[str, Any]: 重建后的完整状态
        """
        # 获取基础检查点
        query = """
        SELECT checkpoint_data, is_compressed, is_delta, base_checkpoint_id
        FROM enhanced_checkpoints
        WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s
        """
        result = await conn.execute(query, (thread_id, checkpoint_ns, base_checkpoint_id))
        row = await result.fetchone()

        if not row:
            raise CheckpointRecoveryError(f"基础检查点不存在: {base_checkpoint_id}")

        base_data = self._decompress(bytes(row["checkpoint_data"]), row["is_compressed"])

        # 递归处理嵌套增量
        if row["is_delta"] and row["base_checkpoint_id"]:
            base_state = await self._rebuild_from_delta(
                conn, thread_id, checkpoint_ns, row["base_checkpoint_id"], base_data
            )
        else:
            base_state = self.serde.loads_typed(("json", base_data.decode("utf-8")))

        # 应用增量
        delta = json.loads(delta_data.decode("utf-8"))
        return self._apply_delta(base_state, delta)

    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> Dict[str, Any]:
        """
        异步保存检查点（支持增量和压缩）

        Args:
            config: 配置字典
            checkpoint: 检查点数据
            metadata: 检查点元数据
            new_versions: 新版本信息

        Returns:
            Dict[str, Any]: 更新后的配置

        Raises:
            ManualInterventionRequired: 重试次数用尽后抛出

        验证：需求 9.1, 9.3, 9.4, 1.2
        """
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        parent_checkpoint_id = configurable.get("checkpoint_id")

        if not thread_id:
            raise ValueError("thread_id 是必需的")

        checkpoint_id = checkpoint.get("id") or str(uuid.uuid4())

        self._report_heartbeat("checkpoint_put", 0.0)

        # 重试逻辑
        last_error = None
        for attempt in range(self.max_retries):
            try:
                await self._do_put(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=parent_checkpoint_id,
                    checkpoint=checkpoint,
                    metadata=metadata,
                )

                self._report_heartbeat("checkpoint_put", 1.0)

                return {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    }
                }

            except Exception as e:
                last_error = e
                logger.warning(f"检查点保存失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    self._report_heartbeat("checkpoint_put_retry", (attempt + 1) / self.max_retries)

        # 重试次数用尽
        logger.error(f"检查点保存失败，需要人工干预: {last_error}")
        raise ManualInterventionRequired(
            f"检查点保存失败 {self.max_retries} 次，需要人工干预: {last_error}"
        )

    async def _do_put(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        parent_checkpoint_id: Optional[str],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> None:
        """
        实际执行检查点保存
        """
        async with self.pool_manager.pg_transaction() as conn:
            # 尝试获取前一个检查点以计算增量
            previous_checkpoint = None
            base_checkpoint_id = None
            is_delta = False

            if parent_checkpoint_id:
                query = """
                SELECT checkpoint_data, is_compressed, is_delta, base_checkpoint_id
                FROM enhanced_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s
                """
                result = await conn.execute(query, (thread_id, checkpoint_ns, parent_checkpoint_id))
                row = await result.fetchone()

                if row:
                    prev_data = self._decompress(
                        bytes(row["checkpoint_data"]), row["is_compressed"]
                    )
                    if row["is_delta"] and row["base_checkpoint_id"]:
                        previous_checkpoint = await self._rebuild_from_delta(
                            conn, thread_id, checkpoint_ns, row["base_checkpoint_id"], prev_data
                        )
                        # 使用原始基础检查点
                        base_checkpoint_id = row["base_checkpoint_id"]
                    else:
                        previous_checkpoint = self.serde.loads_typed(
                            ("json", prev_data.decode("utf-8"))
                        )
                        # 使用父检查点作为基础
                        base_checkpoint_id = parent_checkpoint_id

            self._report_heartbeat("checkpoint_put", 0.3)

            # 计算增量或完整数据
            if previous_checkpoint:
                delta, is_delta = self._compute_delta(
                    previous_checkpoint.get("channel_values", {}),
                    checkpoint.get("channel_values", {}),
                )
                if is_delta and delta:
                    # 保存增量
                    data_to_save = json.dumps(delta).encode("utf-8")
                else:
                    # 变化太大，保存完整状态
                    is_delta = False
                    base_checkpoint_id = None
                    _, data_to_save = self.serde.dumps_typed(checkpoint)
                    data_to_save = (
                        data_to_save.encode("utf-8")
                        if isinstance(data_to_save, str)
                        else data_to_save
                    )
            else:
                # 没有前一个检查点，保存完整状态
                _, data_to_save = self.serde.dumps_typed(checkpoint)
                data_to_save = (
                    data_to_save.encode("utf-8") if isinstance(data_to_save, str) else data_to_save
                )

            self._report_heartbeat("checkpoint_put", 0.5)

            # 压缩（如果需要）
            original_size = len(data_to_save)
            data_to_save, is_compressed = self._compress(data_to_save)

            self._report_heartbeat("checkpoint_put", 0.7)

            # 序列化元数据
            metadata_dict = {
                "source": metadata.source if hasattr(metadata, "source") else "input",
                "step": metadata.step if hasattr(metadata, "step") else -1,
                "writes": metadata.writes if hasattr(metadata, "writes") else None,
                "parents": metadata.parents if hasattr(metadata, "parents") else {},
            }

            # 插入检查点
            insert_query = """
            INSERT INTO enhanced_checkpoints (
                thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                checkpoint_data, metadata, is_compressed, is_delta, 
                base_checkpoint_id, data_size_bytes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) 
            DO UPDATE SET
                checkpoint_data = EXCLUDED.checkpoint_data,
                metadata = EXCLUDED.metadata,
                is_compressed = EXCLUDED.is_compressed,
                is_delta = EXCLUDED.is_delta,
                base_checkpoint_id = EXCLUDED.base_checkpoint_id,
                data_size_bytes = EXCLUDED.data_size_bytes
            """

            await conn.execute(
                insert_query,
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    parent_checkpoint_id,
                    data_to_save,
                    json.dumps(metadata_dict),
                    is_compressed,
                    is_delta,
                    base_checkpoint_id,
                    original_size,
                ),
            )

            self._report_heartbeat("checkpoint_put", 0.9)

            logger.debug(
                f"检查点已保存: thread_id={thread_id}, checkpoint_id={checkpoint_id}, "
                f"is_delta={is_delta}, is_compressed={is_compressed}, "
                f"size={len(data_to_save)}/{original_size}"
            )

    async def aput_writes(
        self,
        config: Dict[str, Any],
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        异步保存待处理写入

        Args:
            config: 配置字典
            writes: 写入列表，每个元素为 (channel, value) 元组
            task_id: 任务 ID
        """
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = configurable.get("checkpoint_id")

        if not thread_id or not checkpoint_id:
            return

        async with self.pool_manager.pg_transaction() as conn:
            for idx, (channel, value) in enumerate(writes):
                type_str, blob = self.serde.dumps_typed(value)
                blob_bytes = blob.encode("utf-8") if isinstance(blob, str) else blob

                insert_query = """
                INSERT INTO enhanced_checkpoint_writes (
                    thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                DO UPDATE SET channel = EXCLUDED.channel, type = EXCLUDED.type, blob = EXCLUDED.blob
                """

                await conn.execute(
                    insert_query,
                    (
                        thread_id,
                        checkpoint_ns,
                        checkpoint_id,
                        task_id,
                        idx,
                        channel,
                        type_str,
                        blob_bytes,
                    ),
                )

    async def aput_with_grading_result(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
        grading_result: Dict[str, Any],
        submission_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        在同一事务中保存检查点和批改中间结果

        此方法确保检查点与批改中间结果在同一数据库事务中持久化，
        要么全部成功要么全部回滚。

        Args:
            config: 配置字典
            checkpoint: 检查点数据
            metadata: 检查点元数据
            new_versions: 新版本信息
            grading_result: 批改结果，包含:
                - submission_id: 提交 ID
                - question_id: 题目 ID
                - score: 得分
                - max_score: 满分
                - confidence_score: 置信度分数
                - visual_annotations: 视觉标注（可选）
                - agent_trace: 智能体追踪（可选）
                - student_feedback: 学生反馈（可选）
            submission_status: 新的提交状态（可选）

        Returns:
            Dict[str, Any]: 更新后的配置

        Raises:
            ManualInterventionRequired: 重试次数用尽后抛出

        验证：需求 2.3, 9.1, 9.4
        """
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        parent_checkpoint_id = configurable.get("checkpoint_id")

        if not thread_id:
            raise ValueError("thread_id 是必需的")

        checkpoint_id = checkpoint.get("id") or str(uuid.uuid4())

        self._report_heartbeat("checkpoint_put_with_grading", 0.0)

        # 重试逻辑
        last_error = None
        for attempt in range(self.max_retries):
            try:
                await self._do_put_with_grading_result(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=parent_checkpoint_id,
                    checkpoint=checkpoint,
                    metadata=metadata,
                    grading_result=grading_result,
                    submission_status=submission_status,
                )

                self._report_heartbeat("checkpoint_put_with_grading", 1.0)

                return {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    }
                }

            except Exception as e:
                last_error = e
                logger.warning(
                    f"检查点+批改结果保存失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    self._report_heartbeat(
                        "checkpoint_put_with_grading_retry", (attempt + 1) / self.max_retries
                    )

        # 重试次数用尽
        logger.error(f"检查点+批改结果保存失败，需要人工干预: {last_error}")
        raise ManualInterventionRequired(
            f"检查点+批改结果保存失败 {self.max_retries} 次，需要人工干预: {last_error}"
        )

    async def _do_put_with_grading_result(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        parent_checkpoint_id: Optional[str],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        grading_result: Dict[str, Any],
        submission_status: Optional[str] = None,
    ) -> None:
        """
        实际执行检查点和批改结果的事务性保存

        验证：需求 2.3
        """
        async with self.pool_manager.pg_transaction() as conn:
            # ===== 1. 保存检查点 =====
            # 尝试获取前一个检查点以计算增量
            previous_checkpoint = None
            base_checkpoint_id = None
            is_delta = False

            if parent_checkpoint_id:
                query = """
                SELECT checkpoint_data, is_compressed, is_delta, base_checkpoint_id
                FROM enhanced_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s
                """
                result = await conn.execute(query, (thread_id, checkpoint_ns, parent_checkpoint_id))
                row = await result.fetchone()

                if row:
                    prev_data = self._decompress(
                        bytes(row["checkpoint_data"]), row["is_compressed"]
                    )
                    if row["is_delta"] and row["base_checkpoint_id"]:
                        previous_checkpoint = await self._rebuild_from_delta(
                            conn, thread_id, checkpoint_ns, row["base_checkpoint_id"], prev_data
                        )
                        base_checkpoint_id = row["base_checkpoint_id"]
                    else:
                        previous_checkpoint = self.serde.loads_typed(
                            ("json", prev_data.decode("utf-8"))
                        )
                        base_checkpoint_id = parent_checkpoint_id

            self._report_heartbeat("checkpoint_put_with_grading", 0.2)

            # 计算增量或完整数据
            if previous_checkpoint:
                delta, is_delta = self._compute_delta(
                    previous_checkpoint.get("channel_values", {}),
                    checkpoint.get("channel_values", {}),
                )
                if is_delta and delta:
                    data_to_save = json.dumps(delta).encode("utf-8")
                else:
                    is_delta = False
                    base_checkpoint_id = None
                    _, data_to_save = self.serde.dumps_typed(checkpoint)
                    data_to_save = (
                        data_to_save.encode("utf-8")
                        if isinstance(data_to_save, str)
                        else data_to_save
                    )
            else:
                _, data_to_save = self.serde.dumps_typed(checkpoint)
                data_to_save = (
                    data_to_save.encode("utf-8") if isinstance(data_to_save, str) else data_to_save
                )

            self._report_heartbeat("checkpoint_put_with_grading", 0.4)

            # 压缩
            original_size = len(data_to_save)
            data_to_save, is_compressed = self._compress(data_to_save)

            # 序列化元数据
            metadata_dict = {
                "source": metadata.source if hasattr(metadata, "source") else "input",
                "step": metadata.step if hasattr(metadata, "step") else -1,
                "writes": metadata.writes if hasattr(metadata, "writes") else None,
                "parents": metadata.parents if hasattr(metadata, "parents") else {},
            }

            # 插入检查点
            checkpoint_insert_query = """
            INSERT INTO enhanced_checkpoints (
                thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                checkpoint_data, metadata, is_compressed, is_delta, 
                base_checkpoint_id, data_size_bytes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) 
            DO UPDATE SET
                checkpoint_data = EXCLUDED.checkpoint_data,
                metadata = EXCLUDED.metadata,
                is_compressed = EXCLUDED.is_compressed,
                is_delta = EXCLUDED.is_delta,
                base_checkpoint_id = EXCLUDED.base_checkpoint_id,
                data_size_bytes = EXCLUDED.data_size_bytes
            """

            await conn.execute(
                checkpoint_insert_query,
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    parent_checkpoint_id,
                    data_to_save,
                    json.dumps(metadata_dict),
                    is_compressed,
                    is_delta,
                    base_checkpoint_id,
                    original_size,
                ),
            )

            self._report_heartbeat("checkpoint_put_with_grading", 0.6)

            # ===== 2. 保存批改结果 =====
            from uuid import UUID

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
            """

            await conn.execute(
                grading_insert_query,
                (
                    UUID(grading_result["submission_id"]),
                    grading_result["question_id"],
                    grading_result.get("score", 0.0),
                    grading_result.get("max_score", 0.0),
                    grading_result.get("confidence_score", 0.0),
                    json.dumps(grading_result.get("visual_annotations", [])),
                    json.dumps(grading_result.get("agent_trace", {})),
                    json.dumps(grading_result.get("student_feedback", {})),
                ),
            )

            self._report_heartbeat("checkpoint_put_with_grading", 0.8)

            # ===== 3. 更新提交状态（如果需要）=====
            if submission_status:
                submission_update_query = """
                UPDATE submissions
                SET status = %s, updated_at = NOW()
                WHERE submission_id = %s
                """
                await conn.execute(
                    submission_update_query,
                    (submission_status, UUID(grading_result["submission_id"])),
                )

            self._report_heartbeat("checkpoint_put_with_grading", 0.95)

            logger.debug(
                f"检查点+批改结果已保存: thread_id={thread_id}, "
                f"checkpoint_id={checkpoint_id}, "
                f"submission_id={grading_result['submission_id']}, "
                f"question_id={grading_result['question_id']}"
            )

    async def alist(
        self,
        config: Optional[Dict[str, Any]],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """
        异步列出检查点

        Args:
            config: 配置字典
            filter: 过滤条件
            before: 在此检查点之前
            limit: 返回数量限制

        Yields:
            CheckpointTuple: 检查点元组

        验证：需求 9.2
        """
        configurable = (config or {}).get("configurable", {})
        thread_id = configurable.get("thread_id")
        checkpoint_ns = configurable.get("checkpoint_ns", "")

        if not thread_id:
            return

        query = """
        SELECT checkpoint_id, parent_checkpoint_id, checkpoint_data, 
               metadata, is_compressed, is_delta, base_checkpoint_id, created_at
        FROM enhanced_checkpoints
        WHERE thread_id = %s AND checkpoint_ns = %s
        """
        params = [thread_id, checkpoint_ns]

        if before:
            before_config = before.get("configurable", {})
            before_id = before_config.get("checkpoint_id")
            if before_id:
                query += " AND created_at < (SELECT created_at FROM enhanced_checkpoints WHERE checkpoint_id = %s)"
                params.append(before_id)

        query += " ORDER BY created_at DESC"

        if limit:
            query += f" LIMIT {limit}"

        async with self.pool_manager.pg_connection() as conn:
            result = await conn.execute(query, params)
            rows = await result.fetchall()

            for row in rows:
                try:
                    checkpoint_data = self._decompress(
                        bytes(row["checkpoint_data"]), row["is_compressed"]
                    )

                    if row["is_delta"] and row["base_checkpoint_id"]:
                        checkpoint = await self._rebuild_from_delta(
                            conn,
                            thread_id,
                            checkpoint_ns,
                            row["base_checkpoint_id"],
                            checkpoint_data,
                        )
                    else:
                        checkpoint = self.serde.loads_typed(
                            ("json", checkpoint_data.decode("utf-8"))
                        )

                    metadata = row["metadata"] or {}

                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": row["checkpoint_id"],
                            }
                        },
                        checkpoint=checkpoint,
                        metadata=(
                            CheckpointMetadata(**metadata) if metadata else CheckpointMetadata()
                        ),
                        parent_config=(
                            {
                                "configurable": {
                                    "thread_id": thread_id,
                                    "checkpoint_ns": checkpoint_ns,
                                    "checkpoint_id": row["parent_checkpoint_id"],
                                }
                            }
                            if row["parent_checkpoint_id"]
                            else None
                        ),
                        pending_writes=[],
                    )
                except Exception as e:
                    logger.warning(f"解析检查点失败: {row['checkpoint_id']}, {e}")
                    continue

    async def get_by_id(
        self,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str = "",
    ) -> Optional[CheckpointTuple]:
        """
        从任意历史检查点恢复

        Args:
            thread_id: 线程 ID
            checkpoint_id: 检查点 ID
            checkpoint_ns: 检查点命名空间

        Returns:
            Optional[CheckpointTuple]: 检查点元组

        验证：需求 9.2
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }
        return await self.aget(config)

    async def list_checkpoints(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        列出历史检查点（简化版本）

        Args:
            thread_id: 线程 ID
            checkpoint_ns: 检查点命名空间
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 检查点摘要列表

        验证：需求 9.2
        """
        query = """
        SELECT checkpoint_id, parent_checkpoint_id, metadata, 
               is_compressed, is_delta, data_size_bytes, created_at
        FROM enhanced_checkpoints
        WHERE thread_id = %s AND checkpoint_ns = %s
        ORDER BY created_at DESC
        LIMIT %s
        """

        async with self.pool_manager.pg_connection() as conn:
            result = await conn.execute(query, (thread_id, checkpoint_ns, limit))
            rows = await result.fetchall()

            return [
                {
                    "checkpoint_id": row["checkpoint_id"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"],
                    "metadata": row["metadata"],
                    "is_compressed": row["is_compressed"],
                    "is_delta": row["is_delta"],
                    "data_size_bytes": row["data_size_bytes"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows
            ]

    # 同步方法（LangGraph 需要）
    def get(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """同步获取检查点"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.aget(config))

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> Dict[str, Any]:
        """同步保存检查点"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.aput(config, checkpoint, metadata, new_versions))

    def put_writes(
        self,
        config: Dict[str, Any],
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """同步保存待处理写入"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self.aput_writes(config, writes, task_id))

    def list(
        self,
        config: Optional[Dict[str, Any]],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """同步列出检查点"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def collect():
            results = []
            async for item in self.alist(config, filter=filter, before=before, limit=limit):
                results.append(item)
            return results

        results = loop.run_until_complete(collect())
        return iter(results)
