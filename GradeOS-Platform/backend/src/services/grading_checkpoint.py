import json
import logging
import os
from typing import Any, Optional

from redis.exceptions import RedisError

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError

logger = logging.getLogger(__name__)

REDIS_CHECKPOINT_KEY_PREFIX = os.getenv("REDIS_CHECKPOINT_KEY_PREFIX", "batch_checkpoint")
REDIS_CHECKPOINT_TTL_SECONDS = int(os.getenv("REDIS_CHECKPOINT_TTL_SECONDS", "172800"))


def _checkpoint_key(batch_id: str) -> str:
    return f"{REDIS_CHECKPOINT_KEY_PREFIX}:{batch_id}"


async def _get_redis_client():
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        if not getattr(pool_manager, "is_initialized", False):
            return None
        return pool_manager.get_redis_client()
    except PoolNotInitializedError:
        return None
    except Exception as exc:
        logger.debug(f"Redis checkpoint client unavailable: {exc}")
        return None


async def save_student_checkpoint(
    *,
    batch_id: str,
    student_key: str,
    field: str,
    payload: Any,
    ttl_seconds: Optional[int] = None,
) -> None:
    """Best-effort Redis checkpointing (no-op if Redis unavailable)."""
    redis_client = await _get_redis_client()
    if not redis_client:
        return

    cache_key = _checkpoint_key(batch_id)
    ttl = int(ttl_seconds or REDIS_CHECKPOINT_TTL_SECONDS)
    redis_field = f"student:{student_key}:{field}"
    try:
        raw = json.dumps(payload, ensure_ascii=False, default=str)
        await redis_client.hset(cache_key, redis_field, raw)
        if ttl > 0:
            await redis_client.expire(cache_key, ttl)
    except (TypeError, ValueError) as exc:
        logger.debug(f"Failed to serialize checkpoint payload: {exc}")
    except RedisError as exc:
        logger.debug(f"Failed to write checkpoint to Redis: {exc}")

