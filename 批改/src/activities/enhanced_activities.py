"""
增强型 Activity 定义

包含分布式锁、检查点检查、LangGraph 状态同步等 Activity。
这些 Activity 原本在 enhanced_workflow.py 中，为了避免 Temporal 工作流沙箱限制而移动到此处。

验证：需求 1.4, 1.5, 10.1, 10.4
"""

import logging
from typing import Any, Dict
from temporalio import activity

from src.utils.pool_manager import UnifiedPoolManager
from src.utils.enhanced_checkpointer import EnhancedPostgresCheckpointer
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CheckpointStatus:
    """检查点状态数据类"""
    exists: bool
    valid: bool
    checkpoint_id: Optional[str] = None
    data_size_bytes: Optional[int] = None
    is_corrupted: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exists": self.exists,
            "valid": self.valid,
            "checkpoint_id": self.checkpoint_id,
            "data_size_bytes": self.data_size_bytes,
            "is_corrupted": self.is_corrupted,
            "error": self.error,
        }


@activity.defn
async def check_checkpoint_exists_activity(
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """检查检查点是否存在"""
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        
        async with pool_manager.pg_connection() as conn:
            result = await conn.execute(
                """
                SELECT checkpoint_id, is_compressed, is_delta, data_size_bytes
                FROM enhanced_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (thread_id, checkpoint_ns)
            )
            row = await result.fetchone()
            
            if row:
                return {
                    "exists": True,
                    "valid": True,
                    "checkpoint_id": row["checkpoint_id"],
                    "data_size_bytes": row["data_size_bytes"],
                }
            
            return {"exists": False, "valid": False}
            
    except Exception as e:
        logger.error(f"检查检查点存在性失败: {e}")
        return {"exists": False, "valid": False, "error": str(e)}

@activity.defn
async def acquire_lock_activity(
    resource_id: str,
    lock_token: str,
    lock_timeout_seconds: int
) -> Dict[str, Any]:
    """获取分布式锁"""
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        redis_client = pool_manager.get_redis_client()
        
        lock_key = f"lock:{resource_id}"
        
        acquired = await redis_client.set(
            lock_key,
            lock_token,
            nx=True,
            ex=lock_timeout_seconds
        )
        
        return {
            "acquired": acquired is not None,
            "lock_key": lock_key,
            "lock_token": lock_token if acquired else None,
        }
        
    except Exception as e:
        logger.error(f"获取分布式锁失败: {e}")
        return {"acquired": False, "error": str(e)}

@activity.defn
async def release_lock_activity(
    resource_id: str,
    lock_token: str
) -> Dict[str, Any]:
    """释放分布式锁"""
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        redis_client = pool_manager.get_redis_client()
        
        lock_key = f"lock:{resource_id}"
        
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        result = await redis_client.eval(
            release_script,
            1,
            lock_key,
            lock_token
        )
        
        return {
            "released": result == 1,
            "lock_key": lock_key,
        }
        
    except Exception as e:
        logger.error(f"释放分布式锁失败: {e}")
        return {"released": False, "error": str(e)}

@activity.defn
async def forward_redis_event_activity(
    workflow_id: str,
    event: Dict[str, Any]
) -> Dict[str, Any]:
    """转发 Redis 事件到工作流"""
    logger.info(f"转发 Redis 事件到工作流: workflow_id={workflow_id}")
    return {
        "forwarded": True,
        "workflow_id": workflow_id,
        "event_type": event.get("event_type"),
    }

@activity.defn
async def sync_langgraph_state_activity(
    workflow_id: str,
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """同步 LangGraph 状态到工作流"""
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        checkpointer = EnhancedPostgresCheckpointer(pool_manager)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
        
        checkpoint_tuple = await checkpointer.aget(config)
        
        if checkpoint_tuple:
            return {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_tuple.config.get("configurable", {}).get("checkpoint_id"),
                "channel_values": checkpoint_tuple.checkpoint.get("channel_values", {}),
                "metadata": checkpoint_tuple.metadata.__dict__ if checkpoint_tuple.metadata else {},
                "updated_at": ""
            }
        
        return {
            "thread_id": thread_id,
            "checkpoint_id": None,
            "channel_values": {},
            "metadata": {},
            "updated_at": "",
        }
        
    except Exception as e:
        logger.error(f"同步 LangGraph 状态失败: {e}")
        return {
            "thread_id": thread_id,
            "error": str(e),
        }

@activity.defn
async def get_latest_langgraph_state_activity(
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """获取最新 LangGraph 状态"""
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        checkpointer = EnhancedPostgresCheckpointer(pool_manager)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
        
        checkpoint_tuple = await checkpointer.aget(config)
        
        if checkpoint_tuple:
            checkpoint_config = checkpoint_tuple.config.get("configurable", {})
            return {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_config.get("checkpoint_id"),
                "channel_values": checkpoint_tuple.checkpoint.get("channel_values", {}),
                "metadata": {
                    "source": getattr(checkpoint_tuple.metadata, 'source', 'unknown'),
                    "step": getattr(checkpoint_tuple.metadata, 'step', -1),
                } if checkpoint_tuple.metadata else {},
                "exists": True,
            }
        
        return {
            "thread_id": thread_id,
            "checkpoint_id": None,
            "channel_values": {},
            "metadata": {},
            "exists": False,
        }
        
    except Exception as e:
        logger.error(f"获取 LangGraph 状态失败: {e}")
        return {
            "thread_id": thread_id,
            "error": str(e),
            "exists": False,
        }

@activity.defn
async def check_checkpoint_validity_activity(
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """检查检查点有效性"""
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        
        async with pool_manager.pg_connection() as conn:
            result = await conn.execute(
                """
                SELECT checkpoint_id, checkpoint_data, is_compressed, 
                       is_delta, data_size_bytes, base_checkpoint_id
                FROM enhanced_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (thread_id, checkpoint_ns)
            )
            row = await result.fetchone()
            
            if not row:
                return CheckpointStatus(
                    exists=False,
                    valid=False,
                ).to_dict()
            
            # 验证检查点数据完整性
            try:
                checkpoint_data = bytes(row["checkpoint_data"])
                
                if row["is_compressed"]:
                    import zlib
                    try:
                        zlib.decompress(checkpoint_data)
                    except zlib.error:
                        return CheckpointStatus(
                            exists=True,
                            valid=False,
                            checkpoint_id=row["checkpoint_id"],
                            data_size_bytes=row["data_size_bytes"],
                            is_corrupted=True,
                            error="压缩数据损坏",
                        ).to_dict()
                
                if row["is_delta"] and row["base_checkpoint_id"]:
                    base_result = await conn.execute(
                        """
                        SELECT 1 FROM enhanced_checkpoints
                        WHERE thread_id = %s AND checkpoint_ns = %s 
                              AND checkpoint_id = %s
                        """,
                        (thread_id, checkpoint_ns, row["base_checkpoint_id"])
                    )
                    base_row = await base_result.fetchone()
                    
                    if not base_row:
                        return CheckpointStatus(
                            exists=True,
                            valid=False,
                            checkpoint_id=row["checkpoint_id"],
                            data_size_bytes=row["data_size_bytes"],
                            is_corrupted=True,
                            error="基础检查点丢失",
                        ).to_dict()
                
                return CheckpointStatus(
                    exists=True,
                    valid=True,
                    checkpoint_id=row["checkpoint_id"],
                    data_size_bytes=row["data_size_bytes"],
                ).to_dict()
                
            except Exception as e:
                return CheckpointStatus(
                    exists=True,
                    valid=False,
                    checkpoint_id=row["checkpoint_id"],
                    error=str(e),
                ).to_dict()
                
    except Exception as e:
        logger.error(f"检查检查点有效性失败: {e}")
        return CheckpointStatus(
            exists=False,
            valid=False,
            error=str(e),
        ).to_dict()

@activity.defn
async def create_langgraph_config_activity(
    workflow_run_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """创建 LangGraph 配置"""
    return {
        "configurable": {
            "thread_id": workflow_run_id,
            "checkpoint_ns": checkpoint_ns,
        }
    }
