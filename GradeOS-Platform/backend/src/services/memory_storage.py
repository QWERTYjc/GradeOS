"""批改记忆系统 - 存储后端适配器

提供多种存储后端支持：
1. 内存存储（本地开发、测试）
2. Redis 存储（分布式缓存、快速读写）
3. PostgreSQL 存储（持久化、长期记忆）

设计原则：
- 策略模式：可插拔的存储后端
- 优雅降级：Redis 故障时降级到 PostgreSQL 或内存
- 分层存储：热数据在 Redis，冷数据在 PostgreSQL
"""

import json
import logging
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ==================== 存储后端接口 ====================


class MemoryStorageBackend(ABC):
    """记忆存储后端抽象基类"""

    @abstractmethod
    async def save_memory(
        self, memory_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        """保存单条记忆"""
        pass

    @abstractmethod
    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """获取单条记忆"""
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """删除单条记忆"""
        pass

    @abstractmethod
    async def list_memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        subject: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出记忆

        Args:
            memory_type: 记忆类型过滤
            limit: 返回数量限制
            offset: 分页偏移
            subject: 科目过滤（重要！用于科目隔离）
        """
        pass

    @abstractmethod
    async def save_batch_memory(
        self, batch_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        """保存批次记忆"""
        pass

    @abstractmethod
    async def get_batch_memory(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批次记忆"""
        pass

    @abstractmethod
    async def save_calibration_stats(self, question_type: str, data: Dict[str, Any]) -> bool:
        """保存校准统计"""
        pass

    @abstractmethod
    async def get_calibration_stats(self, question_type: str) -> Optional[Dict[str, Any]]:
        """获取校准统计"""
        pass

    @abstractmethod
    async def get_all_calibration_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有校准统计"""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass


# ==================== 内存存储后端 ====================


class InMemoryStorageBackend(MemoryStorageBackend):
    """内存存储后端（用于本地开发和测试）"""

    def __init__(self):
        self._memories: Dict[str, Dict[str, Any]] = {}
        self._batch_memories: Dict[str, Dict[str, Any]] = {}
        self._calibration_stats: Dict[str, Dict[str, Any]] = {}
        self._expiry_times: Dict[str, datetime] = {}

    async def save_memory(
        self, memory_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        try:
            self._memories[memory_id] = data
            if ttl_seconds:
                self._expiry_times[memory_id] = datetime.now() + timedelta(seconds=ttl_seconds)
            return True
        except Exception as e:
            logger.error(f"[InMemory] 保存记忆失败: {e}")
            return False

    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        # 检查过期
        if memory_id in self._expiry_times:
            if datetime.now() > self._expiry_times[memory_id]:
                del self._memories[memory_id]
                del self._expiry_times[memory_id]
                return None
        return self._memories.get(memory_id)

    async def delete_memory(self, memory_id: str) -> bool:
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._expiry_times.pop(memory_id, None)
            return True
        return False

    async def list_memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        subject: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        memories = list(self._memories.values())
        if memory_type:
            memories = [m for m in memories if m.get("memory_type") == memory_type]
        if subject:
            memories = [m for m in memories if m.get("subject") == subject]
        return memories[offset : offset + limit]

    async def save_batch_memory(
        self, batch_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        try:
            self._batch_memories[batch_id] = data
            return True
        except Exception as e:
            logger.error(f"[InMemory] 保存批次记忆失败: {e}")
            return False

    async def get_batch_memory(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self._batch_memories.get(batch_id)

    async def save_calibration_stats(self, question_type: str, data: Dict[str, Any]) -> bool:
        self._calibration_stats[question_type] = data
        return True

    async def get_calibration_stats(self, question_type: str) -> Optional[Dict[str, Any]]:
        return self._calibration_stats.get(question_type)

    async def get_all_calibration_stats(self) -> Dict[str, Dict[str, Any]]:
        return self._calibration_stats.copy()

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "backend": "in_memory",
            "memory_count": len(self._memories),
            "batch_memory_count": len(self._batch_memories),
        }

    async def close(self) -> None:
        pass


# ==================== Redis 存储后端 ====================


class RedisStorageBackend(MemoryStorageBackend):
    """Redis 存储后端（分布式缓存）"""

    # Redis Key 前缀
    MEMORY_PREFIX = "grading_memory:entry:"
    BATCH_PREFIX = "grading_memory:batch:"
    CALIBRATION_PREFIX = "grading_memory:calibration:"
    INDEX_PREFIX = "grading_memory:index:"

    def __init__(self, redis_client, default_ttl_seconds: int = 86400 * 90):
        """
        初始化 Redis 存储后端

        Args:
            redis_client: Redis 异步客户端
            default_ttl_seconds: 默认 TTL（秒），默认 90 天
        """
        self._redis = redis_client
        self._default_ttl = default_ttl_seconds

    async def save_memory(
        self, memory_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        try:
            key = f"{self.MEMORY_PREFIX}{memory_id}"
            ttl = ttl_seconds or self._default_ttl

            # 序列化数据
            json_data = json.dumps(data, ensure_ascii=False, default=str)

            # 保存到 Redis
            await self._redis.setex(key, ttl, json_data)

            # 更新类型索引
            memory_type = data.get("memory_type")
            if memory_type:
                index_key = f"{self.INDEX_PREFIX}type:{memory_type}"
                await self._redis.sadd(index_key, memory_id)
                await self._redis.expire(index_key, ttl)

            logger.debug(f"[Redis] 保存记忆成功: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"[Redis] 保存记忆失败: {e}")
            return False

    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = f"{self.MEMORY_PREFIX}{memory_id}"
            data = await self._redis.get(key)

            if data is None:
                return None

            # 处理字节类型
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            return json.loads(data)

        except Exception as e:
            logger.error(f"[Redis] 获取记忆失败: {e}")
            return None

    async def delete_memory(self, memory_id: str) -> bool:
        try:
            key = f"{self.MEMORY_PREFIX}{memory_id}"

            # 先获取数据以更新索引
            data = await self.get_memory(memory_id)
            if data:
                memory_type = data.get("memory_type")
                if memory_type:
                    index_key = f"{self.INDEX_PREFIX}type:{memory_type}"
                    await self._redis.srem(index_key, memory_id)

            deleted = await self._redis.delete(key)
            return deleted > 0

        except Exception as e:
            logger.error(f"[Redis] 删除记忆失败: {e}")
            return False

    async def list_memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        subject: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if memory_type:
                # 使用类型索引
                index_key = f"{self.INDEX_PREFIX}type:{memory_type}"
                memory_ids = await self._redis.smembers(index_key)
                memory_ids = [
                    mid.decode("utf-8") if isinstance(mid, bytes) else mid for mid in memory_ids
                ]
            else:
                # 扫描所有记忆
                memory_ids = []
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor=cursor, match=f"{self.MEMORY_PREFIX}*", count=100
                    )
                    for key in keys:
                        key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                        memory_id = key_str.replace(self.MEMORY_PREFIX, "")
                        memory_ids.append(memory_id)
                    if cursor == 0:
                        break

            # 批量获取（在分页前先过滤科目，以确保正确的分页）
            memories = []
            for memory_id in memory_ids:
                data = await self.get_memory(memory_id)
                if data:
                    # 按科目过滤
                    if subject and data.get("subject") != subject:
                        continue
                    memories.append(data)

            # 分页
            return memories[offset : offset + limit]

        except Exception as e:
            logger.error(f"[Redis] 列出记忆失败: {e}")
            return []

    async def save_batch_memory(
        self, batch_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        try:
            key = f"{self.BATCH_PREFIX}{batch_id}"
            ttl = ttl_seconds or 86400  # 批次记忆默认 1 天

            json_data = json.dumps(data, ensure_ascii=False, default=str)
            await self._redis.setex(key, ttl, json_data)

            logger.debug(f"[Redis] 保存批次记忆成功: {batch_id}")
            return True

        except Exception as e:
            logger.error(f"[Redis] 保存批次记忆失败: {e}")
            return False

    async def get_batch_memory(self, batch_id: str) -> Optional[Dict[str, Any]]:
        try:
            key = f"{self.BATCH_PREFIX}{batch_id}"
            data = await self._redis.get(key)

            if data is None:
                return None

            if isinstance(data, bytes):
                data = data.decode("utf-8")

            return json.loads(data)

        except Exception as e:
            logger.error(f"[Redis] 获取批次记忆失败: {e}")
            return None

    async def save_calibration_stats(self, question_type: str, data: Dict[str, Any]) -> bool:
        try:
            key = f"{self.CALIBRATION_PREFIX}{question_type}"

            json_data = json.dumps(data, ensure_ascii=False, default=str)
            await self._redis.set(key, json_data)

            # 添加到校准类型集合
            await self._redis.sadd(f"{self.CALIBRATION_PREFIX}types", question_type)

            return True

        except Exception as e:
            logger.error(f"[Redis] 保存校准统计失败: {e}")
            return False

    async def get_calibration_stats(self, question_type: str) -> Optional[Dict[str, Any]]:
        try:
            key = f"{self.CALIBRATION_PREFIX}{question_type}"
            data = await self._redis.get(key)

            if data is None:
                return None

            if isinstance(data, bytes):
                data = data.decode("utf-8")

            return json.loads(data)

        except Exception as e:
            logger.error(f"[Redis] 获取校准统计失败: {e}")
            return None

    async def get_all_calibration_stats(self) -> Dict[str, Dict[str, Any]]:
        try:
            # 获取所有校准类型
            types_key = f"{self.CALIBRATION_PREFIX}types"
            question_types = await self._redis.smembers(types_key)

            result = {}
            for qt in question_types:
                qt_str = qt.decode("utf-8") if isinstance(qt, bytes) else qt
                stats = await self.get_calibration_stats(qt_str)
                if stats:
                    result[qt_str] = stats

            return result

        except Exception as e:
            logger.error(f"[Redis] 获取所有校准统计失败: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        try:
            await self._redis.ping()

            # 统计数量
            memory_count = 0
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=f"{self.MEMORY_PREFIX}*", count=100
                )
                memory_count += len(keys)
                if cursor == 0:
                    break

            return {
                "status": "healthy",
                "backend": "redis",
                "memory_count": memory_count,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "redis",
                "error": str(e),
            }

    async def close(self) -> None:
        # Redis 客户端由 UnifiedPoolManager 管理，不需要在这里关闭
        pass


# ==================== PostgreSQL 存储后端 ====================


class PostgresStorageBackend(MemoryStorageBackend):
    """PostgreSQL 存储后端（持久化存储）"""

    def __init__(self, pool_manager):
        """
        初始化 PostgreSQL 存储后端

        Args:
            pool_manager: UnifiedPoolManager 实例
        """
        self._pool_manager = pool_manager
        self._table_initialized = False

    async def _ensure_tables(self) -> None:
        """确保表存在"""
        if self._table_initialized:
            return

        try:
            async with self._pool_manager.pg_connection() as conn:
                # 创建记忆表
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS grading_memories (
                        memory_id VARCHAR(64) PRIMARY KEY,
                        memory_type VARCHAR(50) NOT NULL,
                        importance VARCHAR(20) NOT NULL,
                        pattern TEXT NOT NULL,
                        context JSONB DEFAULT '{}',
                        lesson TEXT,
                        subject VARCHAR(100) DEFAULT 'general',
                        occurrence_count INTEGER DEFAULT 1,
                        confirmation_count INTEGER DEFAULT 0,
                        contradiction_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        related_question_types TEXT[] DEFAULT '{}',
                        related_rubric_ids TEXT[] DEFAULT '{}',
                        source_batch_ids TEXT[] DEFAULT '{}',
                        metadata JSONB DEFAULT '{}',
                        expires_at TIMESTAMP
                    )
                """
                )

                # 为已存在的表添加 subject 列（如果不存在）
                await conn.execute(
                    """
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='grading_memories' AND column_name='subject'
                        ) THEN 
                            ALTER TABLE grading_memories ADD COLUMN subject VARCHAR(100) DEFAULT 'general';
                        END IF;
                    END $$;
                """
                )

                # 创建索引
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_grading_memories_type 
                    ON grading_memories(memory_type)
                """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_grading_memories_importance 
                    ON grading_memories(importance)
                """
                )
                # 科目索引（重要！用于按科目查询记忆）
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_grading_memories_subject 
                    ON grading_memories(subject)
                """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_grading_memories_expires 
                    ON grading_memories(expires_at)
                """
                )

                # 创建批次记忆表
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS grading_batch_memories (
                        batch_id VARCHAR(64) PRIMARY KEY,
                        data JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP
                    )
                """
                )

                # 创建校准统计表
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS grading_calibration_stats (
                        question_type VARCHAR(100) PRIMARY KEY,
                        predicted_confidences JSONB DEFAULT '[]',
                        actual_accuracies JSONB DEFAULT '[]',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

            self._table_initialized = True
            logger.info("[PostgreSQL] 记忆系统表初始化完成")

        except Exception as e:
            logger.error(f"[PostgreSQL] 初始化表失败: {e}")
            raise

    async def save_memory(
        self, memory_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        await self._ensure_tables()

        try:
            expires_at = None
            if ttl_seconds:
                expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

            async with self._pool_manager.pg_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO grading_memories (
                        memory_id, memory_type, importance, pattern, context, lesson,
                        subject,
                        occurrence_count, confirmation_count, contradiction_count,
                        created_at, last_accessed_at, last_updated_at,
                        related_question_types, related_rubric_ids, source_batch_ids,
                        metadata, expires_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (memory_id) DO UPDATE SET
                        pattern = EXCLUDED.pattern,
                        context = EXCLUDED.context,
                        lesson = EXCLUDED.lesson,
                        subject = EXCLUDED.subject,
                        occurrence_count = EXCLUDED.occurrence_count,
                        confirmation_count = EXCLUDED.confirmation_count,
                        contradiction_count = EXCLUDED.contradiction_count,
                        last_updated_at = EXCLUDED.last_updated_at,
                        related_question_types = EXCLUDED.related_question_types,
                        related_rubric_ids = EXCLUDED.related_rubric_ids,
                        source_batch_ids = EXCLUDED.source_batch_ids,
                        metadata = EXCLUDED.metadata,
                        expires_at = EXCLUDED.expires_at
                """,
                    (
                        memory_id,
                        data.get("memory_type"),
                        data.get("importance"),
                        data.get("pattern"),
                        json.dumps(data.get("context", {})),
                        data.get("lesson"),
                        data.get("subject", "general"),  # 科目字段
                        data.get("occurrence_count", 1),
                        data.get("confirmation_count", 0),
                        data.get("contradiction_count", 0),
                        data.get("created_at", datetime.now().isoformat()),
                        data.get("last_accessed_at", datetime.now().isoformat()),
                        data.get("last_updated_at", datetime.now().isoformat()),
                        data.get("related_question_types", []),
                        data.get("related_rubric_ids", []),
                        data.get("source_batch_ids", []),
                        json.dumps(data.get("metadata", {})),
                        expires_at,
                    ),
                )

            logger.debug(f"[PostgreSQL] 保存记忆成功: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"[PostgreSQL] 保存记忆失败: {e}")
            return False

    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_tables()

        try:
            async with self._pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT * FROM grading_memories 
                    WHERE memory_id = %s 
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                """,
                    (memory_id,),
                )
                row = await result.fetchone()

                if not row:
                    return None

                # 更新访问时间
                await conn.execute(
                    """
                    UPDATE grading_memories 
                    SET last_accessed_at = CURRENT_TIMESTAMP 
                    WHERE memory_id = %s
                """,
                    (memory_id,),
                )

                return self._row_to_dict(row)

        except Exception as e:
            logger.error(f"[PostgreSQL] 获取记忆失败: {e}")
            return None

    async def delete_memory(self, memory_id: str) -> bool:
        await self._ensure_tables()

        try:
            async with self._pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM grading_memories WHERE memory_id = %s
                """,
                    (memory_id,),
                )
                return result.rowcount > 0

        except Exception as e:
            logger.error(f"[PostgreSQL] 删除记忆失败: {e}")
            return False

    async def list_memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        subject: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await self._ensure_tables()

        try:
            async with self._pool_manager.pg_connection() as conn:
                # 构建动态查询以支持科目过滤
                conditions = ["(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"]
                params = []

                if memory_type:
                    conditions.append("memory_type = %s")
                    params.append(memory_type)

                if subject:
                    conditions.append("subject = %s")
                    params.append(subject)

                where_clause = " AND ".join(conditions)
                params.extend([limit, offset])

                result = await conn.execute(
                    f"""
                    SELECT * FROM grading_memories 
                    WHERE {where_clause}
                    ORDER BY last_updated_at DESC
                    LIMIT %s OFFSET %s
                """,
                    tuple(params),
                )

                rows = await result.fetchall()
                return [self._row_to_dict(row) for row in rows]

        except Exception as e:
            logger.error(f"[PostgreSQL] 列出记忆失败: {e}")
            return []

    async def save_batch_memory(
        self, batch_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        await self._ensure_tables()

        try:
            expires_at = None
            if ttl_seconds:
                expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

            async with self._pool_manager.pg_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO grading_batch_memories (batch_id, data, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (batch_id) DO UPDATE SET
                        data = EXCLUDED.data,
                        expires_at = EXCLUDED.expires_at
                """,
                    (batch_id, json.dumps(data, default=str), expires_at),
                )

            return True

        except Exception as e:
            logger.error(f"[PostgreSQL] 保存批次记忆失败: {e}")
            return False

    async def get_batch_memory(self, batch_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_tables()

        try:
            async with self._pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT data FROM grading_batch_memories 
                    WHERE batch_id = %s 
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                """,
                    (batch_id,),
                )
                row = await result.fetchone()

                if not row:
                    return None

                return row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])

        except Exception as e:
            logger.error(f"[PostgreSQL] 获取批次记忆失败: {e}")
            return None

    async def save_calibration_stats(self, question_type: str, data: Dict[str, Any]) -> bool:
        await self._ensure_tables()

        try:
            async with self._pool_manager.pg_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO grading_calibration_stats (
                        question_type, predicted_confidences, actual_accuracies, updated_at
                    )
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (question_type) DO UPDATE SET
                        predicted_confidences = EXCLUDED.predicted_confidences,
                        actual_accuracies = EXCLUDED.actual_accuracies,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        question_type,
                        json.dumps(data.get("predicted_confidences", [])),
                        json.dumps(data.get("actual_accuracies", [])),
                    ),
                )

            return True

        except Exception as e:
            logger.error(f"[PostgreSQL] 保存校准统计失败: {e}")
            return False

    async def get_calibration_stats(self, question_type: str) -> Optional[Dict[str, Any]]:
        await self._ensure_tables()

        try:
            async with self._pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT * FROM grading_calibration_stats WHERE question_type = %s
                """,
                    (question_type,),
                )
                row = await result.fetchone()

                if not row:
                    return None

                return {
                    "question_type": row["question_type"],
                    "predicted_confidences": (
                        row["predicted_confidences"]
                        if isinstance(row["predicted_confidences"], list)
                        else json.loads(row["predicted_confidences"])
                    ),
                    "actual_accuracies": (
                        row["actual_accuracies"]
                        if isinstance(row["actual_accuracies"], list)
                        else json.loads(row["actual_accuracies"])
                    ),
                }

        except Exception as e:
            logger.error(f"[PostgreSQL] 获取校准统计失败: {e}")
            return None

    async def get_all_calibration_stats(self) -> Dict[str, Dict[str, Any]]:
        await self._ensure_tables()

        try:
            async with self._pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT * FROM grading_calibration_stats
                """
                )
                rows = await result.fetchall()

                return {
                    row["question_type"]: {
                        "predicted_confidences": (
                            row["predicted_confidences"]
                            if isinstance(row["predicted_confidences"], list)
                            else json.loads(row["predicted_confidences"])
                        ),
                        "actual_accuracies": (
                            row["actual_accuracies"]
                            if isinstance(row["actual_accuracies"], list)
                            else json.loads(row["actual_accuracies"])
                        ),
                    }
                    for row in rows
                }

        except Exception as e:
            logger.error(f"[PostgreSQL] 获取所有校准统计失败: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        try:
            async with self._pool_manager.pg_connection() as conn:
                result = await conn.execute("SELECT COUNT(*) as cnt FROM grading_memories")
                row = await result.fetchone()
                memory_count = row["cnt"] if row else 0

            return {
                "status": "healthy",
                "backend": "postgresql",
                "memory_count": memory_count,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "postgresql",
                "error": str(e),
            }

    async def close(self) -> None:
        # 连接池由 UnifiedPoolManager 管理
        pass

    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "memory_id": row["memory_id"],
            "memory_type": row["memory_type"],
            "importance": row["importance"],
            "pattern": row["pattern"],
            "context": (
                row["context"]
                if isinstance(row["context"], dict)
                else json.loads(row["context"] or "{}")
            ),
            "lesson": row["lesson"],
            "subject": row.get("subject", "general"),  # 科目字段
            "occurrence_count": row["occurrence_count"],
            "confirmation_count": row["confirmation_count"],
            "contradiction_count": row["contradiction_count"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "last_accessed_at": (
                row["last_accessed_at"].isoformat() if row["last_accessed_at"] else None
            ),
            "last_updated_at": (
                row["last_updated_at"].isoformat() if row["last_updated_at"] else None
            ),
            "related_question_types": row["related_question_types"] or [],
            "related_rubric_ids": row["related_rubric_ids"] or [],
            "source_batch_ids": row["source_batch_ids"] or [],
            "metadata": (
                row["metadata"]
                if isinstance(row["metadata"], dict)
                else json.loads(row["metadata"] or "{}")
            ),
        }


# ==================== 多层存储后端 ====================


class MultiLayerStorageBackend(MemoryStorageBackend):
    """
    多层存储后端

    实现分层存储策略：
    - L1: Redis（热数据，快速读写）
    - L2: PostgreSQL（冷数据，持久化）

    特性：
    - 读取时先查 Redis，未命中则查 PostgreSQL 并回填 Redis
    - 写入时同时写入 Redis 和 PostgreSQL
    - Redis 故障时降级到 PostgreSQL，定期尝试恢复
    """

    # 恢复检查间隔（秒）
    REDIS_RECOVERY_INTERVAL = 60

    def __init__(
        self,
        redis_backend: Optional[RedisStorageBackend],
        postgres_backend: Optional[PostgresStorageBackend],
        redis_ttl_seconds: int = 86400 * 7,  # Redis 中默认 7 天
    ):
        self._redis = redis_backend
        self._postgres = postgres_backend
        self._redis_ttl = redis_ttl_seconds
        self._redis_available = redis_backend is not None
        self._last_redis_check = 0.0  # 上次检查 Redis 健康的时间
        self._redis_failure_count = 0  # 连续失败次数

    async def _maybe_recover_redis(self) -> None:
        """定期检查 Redis 是否恢复"""
        import time

        # 如果 Redis 已可用或没有 Redis 后端，跳过
        if self._redis_available or not self._redis:
            return

        # 检查是否到了恢复检查时间
        now = time.time()
        if now - self._last_redis_check < self.REDIS_RECOVERY_INTERVAL:
            return

        self._last_redis_check = now

        try:
            health = await self._redis.health_check()
            if health.get("status") == "healthy":
                self._redis_available = True
                self._redis_failure_count = 0
                logger.info("[MultiLayer] Redis 已恢复，重新启用 L1 缓存")
        except Exception as e:
            logger.debug(f"[MultiLayer] Redis 恢复检查失败: {e}")

    async def save_memory(
        self, memory_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        success = False

        # 尝试恢复 Redis
        await self._maybe_recover_redis()

        # 写入 PostgreSQL（持久化）
        if self._postgres:
            success = await self._postgres.save_memory(memory_id, data, ttl_seconds)

        # 写入 Redis（缓存）
        if self._redis and self._redis_available:
            try:
                redis_ttl = min(ttl_seconds or self._redis_ttl, self._redis_ttl)
                await self._redis.save_memory(memory_id, data, redis_ttl)
                self._redis_failure_count = 0  # 重置失败计数
            except Exception as e:
                self._redis_failure_count += 1
                if self._redis_failure_count >= 3:  # 连续 3 次失败才降级
                    logger.warning(
                        f"[MultiLayer] Redis 连续 {self._redis_failure_count} 次失败，暂时降级: {e}"
                    )
                    self._redis_available = False

        return success

    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        # 尝试恢复 Redis
        await self._maybe_recover_redis()

        # 先查 Redis
        if self._redis and self._redis_available:
            try:
                data = await self._redis.get_memory(memory_id)
                if data:
                    self._redis_failure_count = 0
                    return data
            except Exception as e:
                self._redis_failure_count += 1
                if self._redis_failure_count >= 3:
                    logger.warning(
                        f"[MultiLayer] Redis 连续 {self._redis_failure_count} 次失败，暂时降级: {e}"
                    )
                    self._redis_available = False

        # 查 PostgreSQL
        if self._postgres:
            data = await self._postgres.get_memory(memory_id)
            if data:
                # 回填 Redis
                if self._redis and self._redis_available:
                    try:
                        await self._redis.save_memory(memory_id, data, self._redis_ttl)
                    except Exception:
                        pass
                return data

        return None

    async def delete_memory(self, memory_id: str) -> bool:
        success = False

        # 从 PostgreSQL 删除
        if self._postgres:
            success = await self._postgres.delete_memory(memory_id)

        # 从 Redis 删除
        if self._redis and self._redis_available:
            try:
                await self._redis.delete_memory(memory_id)
            except Exception:
                pass

        return success

    async def list_memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        subject: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # 从 PostgreSQL 读取（权威数据源）
        if self._postgres:
            return await self._postgres.list_memories(memory_type, limit, offset, subject)

        # 降级到 Redis
        if self._redis and self._redis_available:
            try:
                return await self._redis.list_memories(memory_type, limit, offset, subject)
            except Exception:
                pass

        return []

    async def save_batch_memory(
        self, batch_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        success = False

        # 写入 PostgreSQL
        if self._postgres:
            success = await self._postgres.save_batch_memory(batch_id, data, ttl_seconds)

        # 写入 Redis
        if self._redis and self._redis_available:
            try:
                await self._redis.save_batch_memory(batch_id, data, ttl_seconds or 86400)
            except Exception:
                pass

        return success

    async def get_batch_memory(self, batch_id: str) -> Optional[Dict[str, Any]]:
        # 先查 Redis
        if self._redis and self._redis_available:
            try:
                data = await self._redis.get_batch_memory(batch_id)
                if data:
                    return data
            except Exception:
                pass

        # 查 PostgreSQL
        if self._postgres:
            return await self._postgres.get_batch_memory(batch_id)

        return None

    async def save_calibration_stats(self, question_type: str, data: Dict[str, Any]) -> bool:
        success = False

        if self._postgres:
            success = await self._postgres.save_calibration_stats(question_type, data)

        if self._redis and self._redis_available:
            try:
                await self._redis.save_calibration_stats(question_type, data)
            except Exception:
                pass

        return success

    async def get_calibration_stats(self, question_type: str) -> Optional[Dict[str, Any]]:
        if self._redis and self._redis_available:
            try:
                data = await self._redis.get_calibration_stats(question_type)
                if data:
                    return data
            except Exception:
                pass

        if self._postgres:
            return await self._postgres.get_calibration_stats(question_type)

        return None

    async def get_all_calibration_stats(self) -> Dict[str, Dict[str, Any]]:
        if self._postgres:
            return await self._postgres.get_all_calibration_stats()

        if self._redis and self._redis_available:
            try:
                return await self._redis.get_all_calibration_stats()
            except Exception:
                pass

        return {}

    async def health_check(self) -> Dict[str, Any]:
        result = {
            "status": "healthy",
            "backend": "multi_layer",
            "layers": {},
        }

        if self._redis:
            redis_health = await self._redis.health_check()
            result["layers"]["redis"] = redis_health
            if redis_health["status"] != "healthy":
                self._redis_available = False

        if self._postgres:
            pg_health = await self._postgres.health_check()
            result["layers"]["postgresql"] = pg_health
            if pg_health["status"] != "healthy":
                result["status"] = "degraded"

        return result

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
        if self._postgres:
            await self._postgres.close()


# ==================== 工厂函数 ====================


async def create_storage_backend(
    pool_manager=None,
    redis_client=None,
    prefer_multi_layer: bool = True,
) -> MemoryStorageBackend:
    """
    创建存储后端

    Args:
        pool_manager: UnifiedPoolManager 实例（用于 PostgreSQL）
        redis_client: Redis 客户端（用于 Redis）
        prefer_multi_layer: 是否优先使用多层存储

    Returns:
        MemoryStorageBackend: 存储后端实例
    """
    redis_backend = None
    postgres_backend = None

    # 创建 Redis 后端
    if redis_client:
        try:
            await redis_client.ping()
            redis_backend = RedisStorageBackend(redis_client)
            logger.info("[Storage] Redis 后端初始化成功")
        except Exception as e:
            logger.warning(f"[Storage] Redis 后端初始化失败: {e}")

    # 创建 PostgreSQL 后端
    if pool_manager:
        try:
            postgres_backend = PostgresStorageBackend(pool_manager)
            await postgres_backend._ensure_tables()
            logger.info("[Storage] PostgreSQL 后端初始化成功")
        except Exception as e:
            logger.warning(f"[Storage] PostgreSQL 后端初始化失败: {e}")

    # 选择后端
    if prefer_multi_layer and (redis_backend or postgres_backend):
        return MultiLayerStorageBackend(redis_backend, postgres_backend)
    elif redis_backend:
        return redis_backend
    elif postgres_backend:
        return postgres_backend
    else:
        logger.warning("[Storage] 没有可用的数据库后端，使用内存存储")
        return InMemoryStorageBackend()


# 导出
__all__ = [
    "MemoryStorageBackend",
    "InMemoryStorageBackend",
    "RedisStorageBackend",
    "PostgresStorageBackend",
    "MultiLayerStorageBackend",
    "create_storage_backend",
]
