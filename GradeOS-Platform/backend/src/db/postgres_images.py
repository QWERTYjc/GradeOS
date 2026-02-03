"""PostgreSQL 图片存储服务

使用 PostgreSQL BYTEA 类型直接存储图片二进制数据，
替代本地文件存储，实现真正的持久化。

优点：
- 不需要额外的对象存储服务（S3/R2）
- 数据持久化，容器重启不丢失
- 事务一致性好
- 已有 Railway PostgreSQL 支持
"""

import uuid
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from src.utils.database import db
from src.utils.sql_logger import log_sql_operation

logger = logging.getLogger(__name__)

_BATCH_IMAGES_TABLE_READY = False


@dataclass
class BatchImage:
    """批次图片记录"""
    id: str
    batch_id: str
    image_index: int
    image_type: str  # 'answer' | 'rubric'
    image_data: bytes  # 图片二进制数据
    content_type: str = "image/jpeg"
    created_at: str = ""


async def ensure_batch_images_table() -> None:
    """确保 batch_images 表存在"""
    global _BATCH_IMAGES_TABLE_READY
    if _BATCH_IMAGES_TABLE_READY:
        return
    
    create_query = """
        CREATE TABLE IF NOT EXISTS batch_images (
            id UUID PRIMARY KEY,
            batch_id VARCHAR(100) NOT NULL,
            image_index INTEGER NOT NULL,
            image_type VARCHAR(20) NOT NULL,
            image_data BYTEA NOT NULL,
            content_type VARCHAR(50) DEFAULT 'image/jpeg',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_batch_image UNIQUE (batch_id, image_type, image_index)
        )
    """
    index_query = "CREATE INDEX IF NOT EXISTS idx_batch_images_batch ON batch_images(batch_id)"
    
    try:
        log_sql_operation("CREATE TABLE", "batch_images")
        async with db.connection() as conn:
            await conn.execute(create_query)
            await conn.execute(index_query)
            await conn.commit()
        _BATCH_IMAGES_TABLE_READY = True
        logger.info("[BatchImages] 表创建/检查完成")
    except Exception as e:
        log_sql_operation("CREATE TABLE", "batch_images", error=e)
        logger.error(f"[BatchImages] 表创建失败: {e}")
        raise


async def save_batch_images(
    batch_id: str,
    images: List[bytes],
    image_type: str = "answer",
    content_type: str = "image/jpeg",
) -> int:
    """
    批量保存图片到 PostgreSQL
    
    Args:
        batch_id: 批次 ID
        images: 图片二进制数据列表
        image_type: 图片类型 ('answer' | 'rubric')
        content_type: MIME 类型
    
    Returns:
        int: 保存的图片数量
    """
    if not images:
        return 0
    
    await ensure_batch_images_table()
    
    query = """
        INSERT INTO batch_images (id, batch_id, image_index, image_type, image_data, content_type, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (batch_id, image_type, image_index) DO UPDATE SET
            image_data = EXCLUDED.image_data,
            content_type = EXCLUDED.content_type,
            created_at = EXCLUDED.created_at
    """
    
    now = datetime.now().isoformat()
    saved_count = 0
    
    try:
        log_sql_operation("BATCH INSERT", "batch_images", result_count=len(images))
        async with db.connection() as conn:
            for idx, img_data in enumerate(images):
                image_id = str(uuid.uuid4())
                params = (image_id, batch_id, idx, image_type, img_data, content_type, now)
                await conn.execute(query, params)
                saved_count += 1
            await conn.commit()
        
        logger.info(f"[BatchImages] 保存完成: batch_id={batch_id}, type={image_type}, count={saved_count}")
        return saved_count
    except Exception as e:
        log_sql_operation("BATCH INSERT", "batch_images", error=e)
        logger.error(f"[BatchImages] 保存失败: {e}")
        raise


async def save_batch_images_concurrent(
    batch_id: str,
    images: List[bytes],
    image_type: str = "answer",
    content_type: str = "image/jpeg",
    max_concurrent: int = 10,
) -> int:
    """
    并发批量保存图片（更高性能）
    
    Args:
        batch_id: 批次 ID
        images: 图片二进制数据列表
        image_type: 图片类型
        content_type: MIME 类型
        max_concurrent: 最大并发数
    
    Returns:
        int: 保存的图片数量
    """
    if not images:
        return 0
    
    await ensure_batch_images_table()
    
    query = """
        INSERT INTO batch_images (id, batch_id, image_index, image_type, image_data, content_type, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (batch_id, image_type, image_index) DO UPDATE SET
            image_data = EXCLUDED.image_data,
            content_type = EXCLUDED.content_type,
            created_at = EXCLUDED.created_at
    """
    
    now = datetime.now().isoformat()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def save_single(idx: int, img_data: bytes) -> bool:
        async with semaphore:
            try:
                image_id = str(uuid.uuid4())
                params = (image_id, batch_id, idx, image_type, img_data, content_type, now)
                async with db.connection() as conn:
                    await conn.execute(query, params)
                    await conn.commit()
                return True
            except Exception as e:
                logger.error(f"[BatchImages] 保存单张图片失败 idx={idx}: {e}")
                return False
    
    try:
        log_sql_operation("CONCURRENT INSERT", "batch_images", result_count=len(images))
        tasks = [save_single(idx, img) for idx, img in enumerate(images)]
        results = await asyncio.gather(*tasks)
        saved_count = sum(1 for r in results if r)
        
        logger.info(f"[BatchImages] 并发保存完成: batch_id={batch_id}, type={image_type}, count={saved_count}/{len(images)}")
        return saved_count
    except Exception as e:
        log_sql_operation("CONCURRENT INSERT", "batch_images", error=e)
        logger.error(f"[BatchImages] 并发保存失败: {e}")
        raise


async def get_batch_images(
    batch_id: str,
    image_type: Optional[str] = None,
) -> List[Tuple[int, bytes]]:
    """
    获取批次的图片数据
    
    Args:
        batch_id: 批次 ID
        image_type: 图片类型过滤（可选）
    
    Returns:
        List[Tuple[int, bytes]]: [(image_index, image_data), ...]
    """
    await ensure_batch_images_table()
    
    if image_type:
        query = """
            SELECT image_index, image_data 
            FROM batch_images 
            WHERE batch_id = %s AND image_type = %s
            ORDER BY image_index
        """
        params = (batch_id, image_type)
    else:
        query = """
            SELECT image_index, image_data 
            FROM batch_images 
            WHERE batch_id = %s
            ORDER BY image_type, image_index
        """
        params = (batch_id,)
    
    try:
        log_sql_operation("SELECT", "batch_images")
        async with db.connection() as conn:
            result = await conn.execute(query, params)
            rows = await result.fetchall()
        
        images = []
        for row in rows:
            try:
                image_index = row["image_index"]
                image_data = row["image_data"]
            except Exception:
                image_index = row[0]
                image_data = row[1]
            images.append((image_index, image_data))
        log_sql_operation("SELECT", "batch_images", result_count=len(images))
        logger.debug(f"[BatchImages] 获取图片: batch_id={batch_id}, count={len(images)}")
        return images
    except Exception as e:
        log_sql_operation("SELECT", "batch_images", error=e)
        logger.error(f"[BatchImages] 获取图片失败: {e}")
        return []


async def get_batch_images_as_bytes_list(
    batch_id: str,
    image_type: str = "answer",
) -> List[bytes]:
    """
    获取批次图片作为 bytes 列表（按 index 排序）
    
    这是最常用的方法，直接返回可以传给 LLM 的图片数据。
    
    Args:
        batch_id: 批次 ID
        image_type: 图片类型
    
    Returns:
        List[bytes]: 图片数据列表
    """
    images = await get_batch_images(batch_id, image_type)
    return [img_data for _, img_data in images]


async def delete_batch_images(batch_id: str) -> int:
    """
    删除批次的所有图片
    
    Args:
        batch_id: 批次 ID
    
    Returns:
        int: 删除的图片数量
    """
    await ensure_batch_images_table()
    
    query = "DELETE FROM batch_images WHERE batch_id = %s"
    
    try:
        log_sql_operation("DELETE", "batch_images")
        async with db.connection() as conn:
            result = await conn.execute(query, (batch_id,))
            deleted = result.rowcount if hasattr(result, 'rowcount') else 0
            await conn.commit()
        
        log_sql_operation("DELETE", "batch_images", result_count=deleted)
        logger.info(f"[BatchImages] 删除完成: batch_id={batch_id}, count={deleted}")
        return deleted
    except Exception as e:
        log_sql_operation("DELETE", "batch_images", error=e)
        logger.error(f"[BatchImages] 删除失败: {e}")
        raise


async def get_batch_image_count(batch_id: str) -> Dict[str, int]:
    """
    获取批次图片数量统计
    
    Args:
        batch_id: 批次 ID
    
    Returns:
        Dict: {"answer": N, "rubric": M, "total": N+M}
    """
    await ensure_batch_images_table()
    
    query = """
        SELECT image_type, COUNT(*) as cnt
        FROM batch_images
        WHERE batch_id = %s
        GROUP BY image_type
    """
    
    try:
        async with db.connection() as conn:
            result = await conn.execute(query, (batch_id,))
            rows = await result.fetchall()
        
        counts = {"answer": 0, "rubric": 0, "total": 0}
        for row in rows:
            counts[row[0]] = row[1]
            counts["total"] += row[1]
        
        return counts
    except Exception as e:
        logger.error(f"[BatchImages] 统计失败: {e}")
        return {"answer": 0, "rubric": 0, "total": 0}
