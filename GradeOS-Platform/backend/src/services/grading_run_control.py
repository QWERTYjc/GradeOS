from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Literal

import redis.asyncio as redis
from redis.exceptions import RedisError

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError
from src.utils.redis_logger import log_redis_operation


logger = logging.getLogger(__name__)

RunStatus = Literal["queued", "running", "completed", "failed"]

RUN_RECORD_TTL_SECONDS = int(os.getenv("GRADING_RUN_RECORD_TTL_SECONDS", "172800"))
RUN_SLOT_TTL_SECONDS = int(os.getenv("GRADING_RUN_SLOT_TTL_SECONDS", "10800"))
RUN_QUEUE_TTL_SECONDS = int(os.getenv("GRADING_RUN_QUEUE_TTL_SECONDS", str(RUN_RECORD_TTL_SECONDS)))
RUN_KEY_PREFIX = os.getenv("GRADING_RUN_REDIS_PREFIX", "grading_run")


@dataclass
class GradingRunSnapshot:
    batch_id: str
    teacher_id: str
    status: RunStatus
    class_id: Optional[str] = None
    homework_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_pages: Optional[int] = None
    progress: Optional[float] = None
    current_stage: Optional[str] = None

    def to_redis_hash(self) -> Dict[str, str]:
        payload: Dict[str, str] = {
            "batch_id": self.batch_id,
            "teacher_id": self.teacher_id,
            "status": self.status,
        }
        if self.class_id:
            payload["class_id"] = self.class_id
        if self.homework_id:
            payload["homework_id"] = self.homework_id
        if self.created_at:
            payload["created_at"] = self.created_at
        if self.updated_at:
            payload["updated_at"] = self.updated_at
        if self.started_at:
            payload["started_at"] = self.started_at
        if self.completed_at:
            payload["completed_at"] = self.completed_at
        if self.total_pages is not None:
            payload["total_pages"] = str(self.total_pages)
        if self.progress is not None:
            payload["progress"] = f"{self.progress:.4f}"
        if self.current_stage:
            payload["current_stage"] = self.current_stage
        return payload

    @classmethod
    def from_redis(cls, data: Mapping[str, Any]) -> "GradingRunSnapshot":
        def _decode(value: Any) -> str:
            if isinstance(value, (bytes, bytearray)):
                return value.decode("utf-8", errors="ignore")
            return str(value)

        normalized = {_decode(k): _decode(v) for k, v in data.items()}
        progress = normalized.get("progress")
        total_pages = normalized.get("total_pages")
        return cls(
            batch_id=normalized.get("batch_id", ""),
            teacher_id=normalized.get("teacher_id", ""),
            status=normalized.get("status", "queued"),
            class_id=normalized.get("class_id") or None,
            homework_id=normalized.get("homework_id") or None,
            created_at=normalized.get("created_at") or None,
            updated_at=normalized.get("updated_at") or None,
            started_at=normalized.get("started_at") or None,
            completed_at=normalized.get("completed_at") or None,
            total_pages=int(total_pages) if total_pages and total_pages.isdigit() else None,
            progress=float(progress) if progress else None,
            current_stage=normalized.get("current_stage") or None,
        )


class RedisGradingRunController:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def _run_key(self, batch_id: str) -> str:
        return f"{RUN_KEY_PREFIX}:record:{batch_id}"

    def _run_set_key(self, teacher_key: str) -> str:
        return f"{RUN_KEY_PREFIX}:runs:{teacher_key}"

    def _active_set_key(self, teacher_key: str) -> str:
        return f"{RUN_KEY_PREFIX}:active:{teacher_key}"

    def _queue_key(self, teacher_key: str) -> str:
        return f"{RUN_KEY_PREFIX}:queue:{teacher_key}"

    @staticmethod
    def _queue_score(snapshot: GradingRunSnapshot) -> float:
        if snapshot.created_at:
            try:
                raw = snapshot.created_at
                if raw.endswith("Z"):
                    raw = raw[:-1]
                return datetime.fromisoformat(raw).timestamp()
            except ValueError:
                pass
        return time.time()

    async def register_run(self, snapshot: GradingRunSnapshot) -> None:
        payload = snapshot.to_redis_hash()
        run_key = self._run_key(snapshot.batch_id)
        run_set_key = self._run_set_key(snapshot.teacher_id)
        try:
            log_redis_operation("HSET", run_key, value=payload)
            await self._redis.hset(run_key, mapping=payload)
            await self._redis.expire(run_key, RUN_RECORD_TTL_SECONDS)
            
            log_redis_operation("SADD", run_set_key, value=snapshot.batch_id)
            await self._redis.sadd(run_set_key, snapshot.batch_id)
            await self._redis.expire(run_set_key, RUN_RECORD_TTL_SECONDS)
            if snapshot.status == "queued":
                queue_key = self._queue_key(snapshot.teacher_id)
                log_redis_operation("ZADD", queue_key, value={snapshot.batch_id: self._queue_score(snapshot)})
                await self._redis.zadd(queue_key, {snapshot.batch_id: self._queue_score(snapshot)})
                await self._redis.expire(queue_key, RUN_QUEUE_TTL_SECONDS)
        except RedisError as exc:
            log_redis_operation("HSET/SADD/ZADD", run_key, error=exc)
            logger.debug("Failed to register grading run: %s", exc)

    async def update_run(
        self,
        batch_id: str,
        updates: Dict[str, Any],
    ) -> None:
        if not updates:
            return
        run_key = self._run_key(batch_id)
        payload = {key: str(value) for key, value in updates.items() if value is not None}
        if not payload:
            return
        try:
            log_redis_operation("HSET", run_key, value=payload)
            await self._redis.hset(run_key, mapping=payload)
            await self._redis.expire(run_key, RUN_RECORD_TTL_SECONDS)
            log_redis_operation("HSET", run_key, result="success")
        except RedisError as exc:
            log_redis_operation("HSET", run_key, error=exc)
            logger.debug("Failed to update grading run: %s", exc)

    async def try_acquire_slot(
        self,
        teacher_key: str,
        batch_id: str,
        max_active_runs: int,
    ) -> bool:
        if max_active_runs <= 0:
            return True
        active_key = self._active_set_key(teacher_key)
        queue_key = self._queue_key(teacher_key)
        now = int(time.time())
        ttl = RUN_SLOT_TTL_SECONDS
        queue_ttl = RUN_QUEUE_TTL_SECONDS
        script = (
            "local active_key = KEYS[1] "
            "local queue_key = KEYS[2] "
            "local run_id = ARGV[1] "
            "local max_active = tonumber(ARGV[2]) "
            "local now = tonumber(ARGV[3]) "
            "local ttl = tonumber(ARGV[4]) "
            "local queue_ttl = tonumber(ARGV[5]) "
            "redis.call('ZREMRANGEBYSCORE', active_key, '-inf', now - ttl) "
            "local count = redis.call('ZCARD', active_key) "
            "if max_active > 0 and count >= max_active then return 0 end "
            "local rank = redis.call('ZRANK', queue_key, run_id) "
            "if rank ~= false and rank > 0 then return 0 end "
            "redis.call('ZADD', active_key, now, run_id) "
            "redis.call('EXPIRE', active_key, ttl) "
            "if rank ~= false then "
            "  redis.call('ZREM', queue_key, run_id) "
            "  redis.call('EXPIRE', queue_key, queue_ttl) "
            "end "
            "return 1"
        )
        try:
            log_redis_operation("LUA_SCRIPT", f"try_acquire_slot:{active_key}", 
                              value=f"batch_id={batch_id}, max_active={max_active_runs}")
            result = await self._redis.eval(
                script,
                2,
                active_key,
                queue_key,
                batch_id,
                max_active_runs,
                now,
                ttl,
                queue_ttl,
            )
            log_redis_operation("LUA_SCRIPT", f"try_acquire_slot:{active_key}", 
                              result=f"acquired={bool(result)}")
            return bool(result)
        except RedisError as exc:
            log_redis_operation("LUA_SCRIPT", f"try_acquire_slot:{active_key}", error=exc)
            logger.debug("Failed to acquire grading slot: %s", exc)
            return True

    async def wait_for_slot(
        self,
        teacher_key: str,
        batch_id: str,
        max_active_runs: int,
        poll_seconds: float,
        max_wait_seconds: Optional[float] = None,
    ) -> bool:
        if max_active_runs <= 0:
            return True
        start = time.monotonic()
        while True:
            acquired = await self.try_acquire_slot(teacher_key, batch_id, max_active_runs)
            if acquired:
                return True
            if max_wait_seconds is not None and max_wait_seconds > 0:
                if time.monotonic() - start >= max_wait_seconds:
                    return False
            await asyncio.sleep(max(0.5, poll_seconds))

    async def release_slot(self, teacher_key: str, batch_id: str) -> None:
        active_key = self._active_set_key(teacher_key)
        queue_key = self._queue_key(teacher_key)
        try:
            log_redis_operation("ZREM", active_key, value=batch_id)
            await self._redis.zrem(active_key, batch_id)
            log_redis_operation("ZREM", queue_key, value=batch_id)
            await self._redis.zrem(queue_key, batch_id)
            log_redis_operation("ZREM", f"{active_key},{queue_key}", result="success")
        except RedisError as exc:
            log_redis_operation("ZREM", f"{active_key},{queue_key}", error=exc)
            logger.debug("Failed to release grading slot: %s", exc)

    async def force_clear_teacher_slots(self, teacher_key: str) -> None:
        """强制清理该教师的所有活动槽位（用于超时后恢复）"""
        active_key = self._active_set_key(teacher_key)
        try:
            log_redis_operation("DEL", active_key, value="force_clear")
            await self._redis.delete(active_key)
            log_redis_operation("DEL", active_key, result="success")
            logger.info(f"Force cleared all active slots for teacher: {teacher_key}")
        except RedisError as exc:
            log_redis_operation("DEL", active_key, error=exc)
            logger.debug("Failed to force clear teacher slots: %s", exc)
            raise

    async def remove_from_queue(self, teacher_key: str, batch_id: str) -> None:
        queue_key = self._queue_key(teacher_key)
        try:
            log_redis_operation("ZREM", queue_key, value=batch_id)
            await self._redis.zrem(queue_key, batch_id)
            log_redis_operation("ZREM", queue_key, result="success")
        except RedisError as exc:
            log_redis_operation("ZREM", queue_key, error=exc)
            logger.debug("Failed to remove grading run from queue: %s", exc)

    async def list_runs(self, teacher_key: str) -> List[GradingRunSnapshot]:
        run_set_key = self._run_set_key(teacher_key)
        try:
            log_redis_operation("SMEMBERS", run_set_key)
            run_ids = await self._redis.smembers(run_set_key)
            log_redis_operation("SMEMBERS", run_set_key, result=f"count={len(run_ids)}")
        except RedisError as exc:
            log_redis_operation("SMEMBERS", run_set_key, error=exc)
            logger.debug("Failed to list grading runs: %s", exc)
            return []
        if not run_ids:
            return []
        records: List[GradingRunSnapshot] = []
        for run_id in run_ids:
            run_key = self._run_key(
                run_id.decode("utf-8") if isinstance(run_id, (bytes, bytearray)) else str(run_id)
            )
            try:
                log_redis_operation("HGETALL", run_key)
                data = await self._redis.hgetall(run_key)
                log_redis_operation("HGETALL", run_key, result=f"fields={len(data)}")
            except RedisError:
                continue
            if not data:
                continue
            snapshot = GradingRunSnapshot.from_redis(data)
            if snapshot.batch_id:
                records.append(snapshot)
        records.sort(key=lambda item: item.created_at or "", reverse=True)
        return records

    async def get_run(self, batch_id: str) -> Optional[GradingRunSnapshot]:
        run_key = self._run_key(batch_id)
        try:
            log_redis_operation("HGETALL", run_key)
            data = await self._redis.hgetall(run_key)
            log_redis_operation("HGETALL", run_key, result=f"fields={len(data)}" if data else "not_found")
        except RedisError as exc:
            log_redis_operation("HGETALL", run_key, error=exc)
            logger.debug("Failed to fetch grading run: %s", exc)
            return None
        if not data:
            return None
        snapshot = GradingRunSnapshot.from_redis(data)
        if not snapshot.batch_id:
            return None
        return snapshot


async def get_run_controller() -> Optional[RedisGradingRunController]:
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        if not pool_manager.is_initialized:
            return None
        redis_client = pool_manager.get_redis_client()
        return RedisGradingRunController(redis_client)
    except PoolNotInitializedError:
        return None
    except Exception as exc:
        logger.debug("Redis run controller unavailable: %s", exc)
        return None
