"""
OpenBoard 论坛系统 API

实现类似贴吧的学习社区功能，包括：
- 论坛管理（创建、审核）
- 帖子管理（发帖、查看）
- 回复系统
- 搜索功能
- 老师管理（删帖、封禁）

Requirements: 1.1-1.5, 2.1-2.5, 3.1-3.3, 4.1-4.4, 5.1-5.3, 6.1-6.5, 7.1-7.3
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from src.utils.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/openboard", tags=["OpenBoard论坛"])


# ==================== Pydantic 模型 ====================

class ForumStatus(str, Enum):
    """论坛状态"""
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"


class ForumCreate(BaseModel):
    """创建论坛请求"""
    name: str = Field(..., min_length=1, max_length=100, description="论坛名称")
    description: str = Field("", max_length=500, description="论坛描述")
    creator_id: str = Field(..., description="创建者ID")


class ForumApprove(BaseModel):
    """审核论坛请求"""
    approved: bool = Field(..., description="是否通过")
    reason: Optional[str] = Field(None, description="拒绝原因")
    moderator_id: str = Field(..., description="审核者ID")


class ForumResponse(BaseModel):
    """论坛响应"""
    forum_id: str
    name: str
    description: str
    creator_id: str
    creator_name: Optional[str] = None
    status: ForumStatus
    rejection_reason: Optional[str] = None
    post_count: int = 0
    reply_count: int = 0
    last_activity_at: Optional[datetime] = None
    created_at: datetime


class PostCreate(BaseModel):
    """创建帖子请求"""
    forum_id: str = Field(..., description="论坛ID")
    title: str = Field(..., min_length=1, max_length=200, description="帖子标题")
    content: str = Field(..., min_length=1, description="帖子内容")
    author_id: str = Field(..., description="作者ID")
    images: List[str] = Field(default=[], description="图片列表（base64或URL）")


class PostResponse(BaseModel):
    """帖子响应"""
    post_id: str
    forum_id: str
    forum_name: Optional[str] = None
    title: str
    content: str
    images: List[str] = []
    author_id: str
    author_name: Optional[str] = None
    reply_count: int = 0
    created_at: datetime
    updated_at: datetime


class ReplyCreate(BaseModel):
    """创建回复请求"""
    content: str = Field(..., min_length=1, description="回复内容")
    author_id: str = Field(..., description="作者ID")
    images: List[str] = Field(default=[], description="图片列表（base64或URL）")


class ReplyResponse(BaseModel):
    """回复响应"""
    reply_id: str
    post_id: str
    content: str
    images: List[str] = []
    author_id: str
    author_name: Optional[str] = None
    created_at: datetime


class SearchResult(BaseModel):
    """搜索结果"""
    post_id: str
    title: str
    content_snippet: str
    forum_id: str
    forum_name: str
    author_name: str
    created_at: datetime


class PostDetailResponse(BaseModel):
    """帖子详情响应（包含回复）"""
    post: PostResponse
    replies: List[ReplyResponse] = []


class AdminDeletePost(BaseModel):
    """删除帖子请求"""
    moderator_id: str = Field(..., description="管理员ID")
    reason: Optional[str] = Field(None, description="删除原因")


class AdminBanUser(BaseModel):
    """封禁用户请求"""
    user_id: str = Field(..., description="用户ID")
    moderator_id: str = Field(..., description="管理员ID")
    banned: bool = Field(..., description="是否封禁")
    reason: Optional[str] = Field(None, description="封禁原因")


# ==================== 辅助函数 ====================

def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


async def check_user_banned(user_id: str) -> bool:
    """检查用户是否被封禁"""
    try:
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT is_banned FROM forum_user_status WHERE user_id = %s",
                (user_id,)
            )
            result = await cursor.fetchone()
            return result["is_banned"] if result else False
    except Exception as e:
        logger.warning(f"检查用户封禁状态失败: {e}")
        return False


async def get_user_name(user_id: str) -> Optional[str]:
    """获取用户名"""
    try:
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT COALESCE(real_name, username) as name FROM users WHERE user_id = %s",
                (user_id,)
            )
            result = await cursor.fetchone()
            return result["name"] if result else None
    except Exception as e:
        logger.warning(f"获取用户名失败: {e}")
        return None


async def log_mod_action(
    moderator_id: str,
    action: str,
    target_type: str,
    target_id: str,
    reason: Optional[str] = None
):
    """记录管理操作日志"""
    try:
        log_id = generate_id("log_")
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO forum_mod_logs (log_id, moderator_id, action, target_type, target_id, reason, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (log_id, moderator_id, action, target_type, target_id, reason)
            )
            await conn.commit()
    except Exception as e:
        logger.error(f"记录管理操作日志失败: {e}")


# ==================== 论坛管理 API (Task 2.2) ====================

@router.get("/forums", response_model=List[ForumResponse])
async def get_forums(
    status: Optional[ForumStatus] = Query(None, description="按状态筛选"),
    include_pending: bool = Query(False, description="是否包含待审核论坛（老师用）")
):
    """
    获取论坛列表
    
    - 默认只返回已激活的论坛
    - 按最近活动时间排序
    
    Requirements: 1.4, 1.5
    """
    try:
        async with db.connection() as conn:
            if include_pending:
                # 老师视图：包含所有状态
                status_val = status.value if status else None
                cursor = await conn.execute(
                    """
                    SELECT f.*, COALESCE(u.real_name, u.username) as creator_name,
                           COALESCE((SELECT COUNT(*) FROM forum_replies r 
                                    JOIN forum_posts p ON r.post_id = p.post_id 
                                    WHERE p.forum_id = f.forum_id AND p.is_deleted = FALSE), 0) as reply_count
                    FROM forums f
                    LEFT JOIN users u ON f.creator_id = u.user_id
                    WHERE (%s IS NULL OR f.status = %s)
                    ORDER BY f.last_activity_at DESC NULLS LAST, f.created_at DESC
                    """,
                    (status_val, status_val)
                )
            else:
                # 学生视图：只显示已激活的论坛
                cursor = await conn.execute(
                    """
                    SELECT f.*, COALESCE(u.real_name, u.username) as creator_name,
                           COALESCE((SELECT COUNT(*) FROM forum_replies r 
                                    JOIN forum_posts p ON r.post_id = p.post_id 
                                    WHERE p.forum_id = f.forum_id AND p.is_deleted = FALSE), 0) as reply_count
                    FROM forums f
                    LEFT JOIN users u ON f.creator_id = u.user_id
                    WHERE f.status = 'active'
                    ORDER BY f.last_activity_at DESC NULLS LAST, f.created_at DESC
                    """
                )
            
            rows = await cursor.fetchall()
            
            return [
                ForumResponse(
                    forum_id=row["forum_id"],
                    name=row["name"],
                    description=row["description"] or "",
                    creator_id=row["creator_id"],
                    creator_name=row["creator_name"],
                    status=ForumStatus(row["status"]),
                    rejection_reason=row.get("rejection_reason"),
                    post_count=row["post_count"] or 0,
                    reply_count=row["reply_count"] or 0,
                    last_activity_at=row["last_activity_at"],
                    created_at=row["created_at"]
                )
                for row in rows
            ]
    except Exception as e:
        logger.error(f"获取论坛列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取论坛列表失败: {str(e)}")


@router.post("/forums", response_model=ForumResponse)
async def create_forum(data: ForumCreate):
    """
    创建论坛申请
    
    - 创建后状态为 pending，等待老师审核
    
    Requirements: 1.1
    """
    # 检查用户是否被封禁
    if await check_user_banned(data.creator_id):
        raise HTTPException(status_code=403, detail="您已被禁言，无法创建论坛")
    
    forum_id = generate_id("forum_")
    
    try:
        async with db.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO forums (forum_id, name, description, creator_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'pending', NOW(), NOW())
                RETURNING *
                """,
                (forum_id, data.name, data.description, data.creator_id)
            )
            row = await cursor.fetchone()
            await conn.commit()
        
        creator_name = await get_user_name(data.creator_id)
        
        logger.info(f"论坛创建申请: {forum_id} by {data.creator_id}")
        
        return ForumResponse(
            forum_id=row["forum_id"],
            name=row["name"],
            description=row["description"] or "",
            creator_id=row["creator_id"],
            creator_name=creator_name,
            status=ForumStatus(row["status"]),
            post_count=0,
            reply_count=0,
            created_at=row["created_at"]
        )
    except Exception as e:
        logger.error(f"创建论坛失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建论坛失败: {str(e)}")


@router.post("/forums/{forum_id}/approve", response_model=ForumResponse)
async def approve_forum(forum_id: str, data: ForumApprove):
    """
    审核论坛申请（老师专用）
    
    - approved=True: 论坛状态变为 active
    - approved=False: 论坛状态变为 rejected，需提供原因
    
    Requirements: 1.2, 1.3
    """
    try:
        async with db.connection() as conn:
            # 检查论坛是否存在
            cursor = await conn.execute(
                "SELECT * FROM forums WHERE forum_id = %s",
                (forum_id,)
            )
            forum = await cursor.fetchone()
            
            if not forum:
                raise HTTPException(status_code=404, detail="论坛不存在")
            
            new_status = "active" if data.approved else "rejected"
            rejection_reason = None if data.approved else data.reason
            
            cursor = await conn.execute(
                """
                UPDATE forums 
                SET status = %s, rejection_reason = %s, updated_at = NOW()
                WHERE forum_id = %s
                RETURNING *
                """,
                (new_status, rejection_reason, forum_id)
            )
            row = await cursor.fetchone()
            await conn.commit()
        
        # 记录管理操作
        action = "approve_forum" if data.approved else "reject_forum"
        await log_mod_action(data.moderator_id, action, "forum", forum_id, data.reason)
        
        creator_name = await get_user_name(row["creator_id"])
        
        logger.info(f"论坛审核: {forum_id} -> {new_status} by {data.moderator_id}")
        
        return ForumResponse(
            forum_id=row["forum_id"],
            name=row["name"],
            description=row["description"] or "",
            creator_id=row["creator_id"],
            creator_name=creator_name,
            status=ForumStatus(row["status"]),
            rejection_reason=row.get("rejection_reason"),
            post_count=row["post_count"] or 0,
            reply_count=0,
            created_at=row["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"审核论坛失败: {e}")
        raise HTTPException(status_code=500, detail=f"审核论坛失败: {str(e)}")


# ==================== 帖子管理 API (Task 2.3) ====================

@router.get("/forums/{forum_id}/posts", response_model=List[PostResponse])
async def get_forum_posts(
    forum_id: str,
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取论坛帖子列表
    
    - 按创建时间倒序排列
    - 支持分页
    
    Requirements: 2.4, 2.5
    """
    try:
        async with db.connection() as conn:
            # 检查论坛是否存在且已激活
            cursor = await conn.execute(
                "SELECT * FROM forums WHERE forum_id = %s",
                (forum_id,)
            )
            forum = await cursor.fetchone()
            
            if not forum:
                raise HTTPException(status_code=404, detail="论坛不存在")
            
            if forum["status"] != "active":
                raise HTTPException(status_code=400, detail="论坛未通过审核")
            
            offset = (page - 1) * limit
            
            cursor = await conn.execute(
                """
                SELECT p.*, COALESCE(u.real_name, u.username) as author_name, f.name as forum_name
                FROM forum_posts p
                LEFT JOIN users u ON p.author_id = u.user_id
                LEFT JOIN forums f ON p.forum_id = f.forum_id
                WHERE p.forum_id = %s AND p.is_deleted = FALSE
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (forum_id, limit, offset)
            )
            rows = await cursor.fetchall()
            
            return [
                PostResponse(
                    post_id=row["post_id"],
                    forum_id=row["forum_id"],
                    forum_name=row["forum_name"],
                    title=row["title"],
                    content=row["content"],
                    images=row.get("images") or [],
                    author_id=row["author_id"],
                    author_name=row["author_name"],
                    reply_count=row["reply_count"] or 0,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                for row in rows
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取帖子列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取帖子列表失败: {str(e)}")


@router.post("/posts", response_model=PostResponse)
async def create_post(data: PostCreate):
    """
    创建帖子
    
    - 检查用户是否被封禁
    - 检查论坛是否已激活
    - 更新论坛统计信息
    - 支持图片上传
    
    Requirements: 2.1, 2.2
    """
    # 检查用户是否被封禁
    if await check_user_banned(data.author_id):
        raise HTTPException(status_code=403, detail="您已被禁言，无法发帖")
    
    # 限制图片数量（最多9张）
    images = data.images[:9] if data.images else []
    
    try:
        async with db.connection() as conn:
            # 检查论坛是否存在且已激活
            cursor = await conn.execute(
                "SELECT * FROM forums WHERE forum_id = %s",
                (data.forum_id,)
            )
            forum = await cursor.fetchone()
            
            if not forum:
                raise HTTPException(status_code=404, detail="论坛不存在")
            
            if forum["status"] != "active":
                raise HTTPException(status_code=400, detail="论坛未通过审核，无法发帖")
            
            post_id = generate_id("post_")
            
            # 将图片列表转为 JSON
            import json
            images_json = json.dumps(images)
            
            cursor = await conn.execute(
                """
                INSERT INTO forum_posts (post_id, forum_id, title, content, images, author_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW())
                RETURNING *
                """,
                (post_id, data.forum_id, data.title, data.content, images_json, data.author_id)
            )
            row = await cursor.fetchone()
            
            # 更新论坛统计
            await conn.execute(
                """
                UPDATE forums 
                SET post_count = post_count + 1, last_activity_at = NOW(), updated_at = NOW()
                WHERE forum_id = %s
                """,
                (data.forum_id,)
            )
            await conn.commit()
        
        author_name = await get_user_name(data.author_id)
        
        logger.info(f"帖子创建: {post_id} in {data.forum_id} by {data.author_id}, 图片数: {len(images)}")
        
        return PostResponse(
            post_id=row["post_id"],
            forum_id=row["forum_id"],
            forum_name=forum["name"],
            title=row["title"],
            content=row["content"],
            images=row.get("images") or [],
            author_id=row["author_id"],
            author_name=author_name,
            reply_count=0,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建帖子失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建帖子失败: {str(e)}")


@router.get("/posts/{post_id}", response_model=PostDetailResponse)
async def get_post(post_id: str):
    """
    获取帖子详情（包含回复）
    
    Requirements: 2.3
    """
    try:
        async with db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT p.*, COALESCE(u.real_name, u.username) as author_name, f.name as forum_name
                FROM forum_posts p
                LEFT JOIN users u ON p.author_id = u.user_id
                LEFT JOIN forums f ON p.forum_id = f.forum_id
                WHERE p.post_id = %s AND p.is_deleted = FALSE
                """,
                (post_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="帖子不存在")
            
            post = PostResponse(
                post_id=row["post_id"],
                forum_id=row["forum_id"],
                forum_name=row["forum_name"],
                title=row["title"],
                content=row["content"],
                images=row.get("images") or [],
                author_id=row["author_id"],
                author_name=row["author_name"],
                reply_count=row["reply_count"] or 0,
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            
            # 获取回复列表
            cursor = await conn.execute(
                """
                SELECT r.*, COALESCE(u.real_name, u.username) as author_name
                FROM forum_replies r
                LEFT JOIN users u ON r.author_id = u.user_id
                WHERE r.post_id = %s AND r.is_deleted = FALSE
                ORDER BY r.created_at ASC
                LIMIT 100
                """,
                (post_id,)
            )
            reply_rows = await cursor.fetchall()
            
            replies = [
                ReplyResponse(
                    reply_id=r["reply_id"],
                    post_id=r["post_id"],
                    content=r["content"],
                    images=r.get("images") or [],
                    author_id=r["author_id"],
                    author_name=r["author_name"],
                    created_at=r["created_at"]
                )
                for r in reply_rows
            ]
            
            return PostDetailResponse(post=post, replies=replies)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取帖子详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取帖子详情失败: {str(e)}")


# ==================== 回复管理 API (Task 2.4) ====================

@router.get("/posts/{post_id}/replies", response_model=List[ReplyResponse])
async def get_post_replies(
    post_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    获取帖子回复列表
    
    - 按时间正序排列
    
    Requirements: 3.2, 3.3
    """
    try:
        async with db.connection() as conn:
            # 检查帖子是否存在
            cursor = await conn.execute(
                "SELECT * FROM forum_posts WHERE post_id = %s AND is_deleted = FALSE",
                (post_id,)
            )
            post = await cursor.fetchone()
            
            if not post:
                raise HTTPException(status_code=404, detail="帖子不存在")
            
            offset = (page - 1) * limit
            
            cursor = await conn.execute(
                """
                SELECT r.*, COALESCE(u.real_name, u.username) as author_name
                FROM forum_replies r
                LEFT JOIN users u ON r.author_id = u.user_id
                WHERE r.post_id = %s AND r.is_deleted = FALSE
                ORDER BY r.created_at ASC
                LIMIT %s OFFSET %s
                """,
                (post_id, limit, offset)
            )
            rows = await cursor.fetchall()
            
            return [
                ReplyResponse(
                    reply_id=row["reply_id"],
                    post_id=row["post_id"],
                    content=row["content"],
                    images=row.get("images") or [],
                    author_id=row["author_id"],
                    author_name=row["author_name"],
                    created_at=row["created_at"]
                )
                for row in rows
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回复列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取回复列表失败: {str(e)}")


@router.post("/posts/{post_id}/replies", response_model=ReplyResponse)
async def create_reply(post_id: str, data: ReplyCreate):
    """
    创建回复
    
    - 检查用户是否被封禁
    - 更新帖子回复计数
    - 更新论坛最后活动时间
    - 支持图片上传（最多5张）
    
    Requirements: 3.1
    """
    # 检查用户是否被封禁
    if await check_user_banned(data.author_id):
        raise HTTPException(status_code=403, detail="您已被禁言，无法回复")
    
    # 限制图片数量（最多5张）
    images = data.images[:5] if data.images else []
    
    try:
        async with db.connection() as conn:
            # 检查帖子是否存在
            cursor = await conn.execute(
                "SELECT * FROM forum_posts WHERE post_id = %s AND is_deleted = FALSE",
                (post_id,)
            )
            post = await cursor.fetchone()
            
            if not post:
                raise HTTPException(status_code=404, detail="帖子不存在")
            
            reply_id = generate_id("reply_")
            
            # 将图片列表转为 JSON
            import json
            images_json = json.dumps(images)
            
            cursor = await conn.execute(
                """
                INSERT INTO forum_replies (reply_id, post_id, content, images, author_id, created_at)
                VALUES (%s, %s, %s, %s::jsonb, %s, NOW())
                RETURNING *
                """,
                (reply_id, post_id, data.content, images_json, data.author_id)
            )
            row = await cursor.fetchone()
            
            # 更新帖子回复计数
            await conn.execute(
                "UPDATE forum_posts SET reply_count = reply_count + 1, updated_at = NOW() WHERE post_id = %s",
                (post_id,)
            )
            
            # 更新论坛最后活动时间
            await conn.execute(
                "UPDATE forums SET last_activity_at = NOW(), updated_at = NOW() WHERE forum_id = %s",
                (post["forum_id"],)
            )
            await conn.commit()
        
        author_name = await get_user_name(data.author_id)
        
        logger.info(f"回复创建: {reply_id} on {post_id} by {data.author_id}, 图片数: {len(images)}")
        
        return ReplyResponse(
            reply_id=row["reply_id"],
            post_id=row["post_id"],
            content=row["content"],
            images=row.get("images") or [],
            author_id=row["author_id"],
            author_name=author_name,
            created_at=row["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建回复失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建回复失败: {str(e)}")


# ==================== 搜索 API (Task 2.5) ====================

@router.get("/search", response_model=List[SearchResult])
async def search_posts(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    forum_id: Optional[str] = Query(None, description="限定论坛ID"),
    limit: int = Query(20, ge=1, le=50, description="结果数量")
):
    """
    搜索帖子
    
    - 搜索标题和内容
    - 可按论坛筛选
    
    Requirements: 4.1, 4.2, 4.3
    """
    try:
        async with db.connection() as conn:
            search_pattern = f"%{q}%"
            
            if forum_id:
                cursor = await conn.execute(
                    """
                    SELECT p.post_id, p.title, p.content, p.forum_id, p.created_at,
                           f.name as forum_name, COALESCE(u.real_name, u.username) as author_name
                    FROM forum_posts p
                    JOIN forums f ON p.forum_id = f.forum_id
                    LEFT JOIN users u ON p.author_id = u.user_id
                    WHERE p.is_deleted = FALSE 
                      AND f.status = 'active'
                      AND p.forum_id = %s
                      AND (p.title ILIKE %s OR p.content ILIKE %s)
                    ORDER BY p.created_at DESC
                    LIMIT %s
                    """,
                    (forum_id, search_pattern, search_pattern, limit)
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT p.post_id, p.title, p.content, p.forum_id, p.created_at,
                           f.name as forum_name, COALESCE(u.real_name, u.username) as author_name
                    FROM forum_posts p
                    JOIN forums f ON p.forum_id = f.forum_id
                    LEFT JOIN users u ON p.author_id = u.user_id
                    WHERE p.is_deleted = FALSE 
                      AND f.status = 'active'
                      AND (p.title ILIKE %s OR p.content ILIKE %s)
                    ORDER BY p.created_at DESC
                    LIMIT %s
                    """,
                    (search_pattern, search_pattern, limit)
                )
            
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                # 生成内容摘要
                content = row["content"]
                snippet = content[:150] + "..." if len(content) > 150 else content
                
                results.append(SearchResult(
                    post_id=row["post_id"],
                    title=row["title"],
                    content_snippet=snippet,
                    forum_id=row["forum_id"],
                    forum_name=row["forum_name"],
                    author_name=row["author_name"] or "匿名用户",
                    created_at=row["created_at"]
                ))
            
            return results
    except Exception as e:
        logger.error(f"搜索帖子失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索帖子失败: {str(e)}")


# ==================== 管理员 API (Task 2.6) ====================

@router.delete("/admin/posts/{post_id}")
async def delete_post(post_id: str, data: AdminDeletePost):
    """
    删除帖子（老师专用）
    
    - 软删除帖子
    - 记录操作日志
    
    Requirements: 5.1, 5.2
    """
    try:
        async with db.connection() as conn:
            # 检查帖子是否存在
            cursor = await conn.execute(
                "SELECT * FROM forum_posts WHERE post_id = %s",
                (post_id,)
            )
            post = await cursor.fetchone()
            
            if not post:
                raise HTTPException(status_code=404, detail="帖子不存在")
            
            # 软删除帖子
            await conn.execute(
                "UPDATE forum_posts SET is_deleted = TRUE, updated_at = NOW() WHERE post_id = %s",
                (post_id,)
            )
            
            # 更新论坛帖子计数
            await conn.execute(
                "UPDATE forums SET post_count = GREATEST(post_count - 1, 0), updated_at = NOW() WHERE forum_id = %s",
                (post["forum_id"],)
            )
            await conn.commit()
        
        # 记录管理操作
        await log_mod_action(data.moderator_id, "delete_post", "post", post_id, data.reason)
        
        logger.info(f"帖子删除: {post_id} by {data.moderator_id}")
        
        return {"success": True, "message": "帖子已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除帖子失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除帖子失败: {str(e)}")


@router.post("/admin/ban")
async def ban_user(data: AdminBanUser):
    """
    封禁/解封用户（老师专用）
    
    Requirements: 6.1, 6.2, 6.3
    """
    try:
        async with db.connection() as conn:
            if data.banned:
                # 封禁用户
                await conn.execute(
                    """
                    INSERT INTO forum_user_status (user_id, is_banned, banned_at, banned_by, ban_reason)
                    VALUES (%s, TRUE, NOW(), %s, %s)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET is_banned = TRUE, banned_at = NOW(), banned_by = %s, ban_reason = %s
                    """,
                    (data.user_id, data.moderator_id, data.reason, data.moderator_id, data.reason)
                )
                action = "ban_user"
            else:
                # 解封用户
                await conn.execute(
                    """
                    UPDATE forum_user_status 
                    SET is_banned = FALSE, banned_at = NULL, banned_by = NULL, ban_reason = NULL
                    WHERE user_id = %s
                    """,
                    (data.user_id,)
                )
                action = "unban_user"
            
            await conn.commit()
        
        # 记录管理操作
        await log_mod_action(data.moderator_id, action, "user", data.user_id, data.reason)
        
        status = "封禁" if data.banned else "解封"
        logger.info(f"用户{status}: {data.user_id} by {data.moderator_id}")
        
        return {"success": True, "message": f"用户已{status}"}
    except Exception as e:
        logger.error(f"封禁/解封用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.get("/admin/users/{user_id}/status")
async def get_user_status(user_id: str):
    """
    获取用户论坛状态
    
    Requirements: 6.4
    """
    try:
        async with db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT fus.*, COALESCE(u.real_name, u.username) as user_name,
                       COALESCE(m.real_name, m.username) as banned_by_name
                FROM forum_user_status fus
                LEFT JOIN users u ON fus.user_id = u.user_id
                LEFT JOIN users m ON fus.banned_by = m.user_id
                WHERE fus.user_id = %s
                """,
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {
                    "user_id": user_id,
                    "is_banned": False,
                    "banned_at": None,
                    "banned_by": None,
                    "ban_reason": None
                }
            
            return {
                "user_id": row["user_id"],
                "user_name": row["user_name"],
                "is_banned": row["is_banned"],
                "banned_at": row["banned_at"].isoformat() if row["banned_at"] else None,
                "banned_by": row["banned_by"],
                "banned_by_name": row["banned_by_name"],
                "ban_reason": row["ban_reason"]
            }
    except Exception as e:
        logger.error(f"获取用户状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户状态失败: {str(e)}")


@router.get("/admin/pending-forums", response_model=List[ForumResponse])
async def get_pending_forums():
    """
    获取待审核论坛列表（老师专用）
    
    Requirements: 1.5
    """
    try:
        async with db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT f.*, COALESCE(u.real_name, u.username) as creator_name
                FROM forums f
                LEFT JOIN users u ON f.creator_id = u.user_id
                WHERE f.status = 'pending'
                ORDER BY f.created_at DESC
                """
            )
            rows = await cursor.fetchall()
            
            return [
                ForumResponse(
                    forum_id=row["forum_id"],
                    name=row["name"],
                    description=row["description"] or "",
                    creator_id=row["creator_id"],
                    creator_name=row["creator_name"],
                    status=ForumStatus(row["status"]),
                    post_count=0,
                    reply_count=0,
                    created_at=row["created_at"]
                )
                for row in rows
            ]
    except Exception as e:
        logger.error(f"获取待审核论坛失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取待审核论坛失败: {str(e)}")


@router.get("/admin/mod-logs")
async def get_mod_logs(
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None, description="筛选操作类型")
):
    """
    获取管理操作日志（老师专用）
    
    Requirements: 5.3
    """
    try:
        async with db.connection() as conn:
            if action:
                cursor = await conn.execute(
                    """
                    SELECT l.*, COALESCE(u.real_name, u.username) as moderator_name
                    FROM forum_mod_logs l
                    LEFT JOIN users u ON l.moderator_id = u.user_id
                    WHERE l.action = %s
                    ORDER BY l.created_at DESC
                    LIMIT %s
                    """,
                    (action, limit)
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT l.*, COALESCE(u.real_name, u.username) as moderator_name
                    FROM forum_mod_logs l
                    LEFT JOIN users u ON l.moderator_id = u.user_id
                    ORDER BY l.created_at DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
            
            rows = await cursor.fetchall()
            
            return [
                {
                    "log_id": row["log_id"],
                    "moderator_id": row["moderator_id"],
                    "moderator_name": row["moderator_name"],
                    "action": row["action"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "reason": row["reason"],
                    "created_at": row["created_at"].isoformat()
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"获取管理日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取管理日志失败: {str(e)}")
