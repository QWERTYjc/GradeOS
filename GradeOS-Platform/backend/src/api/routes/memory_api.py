"""
记忆管理 API

提供记忆系统的管理接口，包括：
- 统计信息查询
- 记忆列表查询
- 记忆验证
- 记忆软删除
- 记忆回滚

Requirements: Task 10 (记忆管理 API)
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.grading_memory import (
    get_memory_service,
    MemoryType,
    MemoryVerificationStatus,
    MemoryImportance,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


# ==================== 请求/响应模型 ====================


class MemoryStatsResponse(BaseModel):
    """记忆统计响应"""

    total_count: int = Field(..., description="总记忆数")
    by_status: dict = Field(..., description="按验证状态统计")
    by_subject: dict = Field(..., description="按科目统计")
    by_type: dict = Field(..., description="按类型统计")
    avg_confidence: float = Field(..., description="平均置信度")


class MemoryEntryResponse(BaseModel):
    """记忆条目响应"""

    memory_id: str
    memory_type: str
    importance: str
    pattern: str
    lesson: str
    subject: str
    verification_status: str
    confidence: float
    occurrence_count: int
    confirmation_count: int
    contradiction_count: int
    created_at: str
    last_updated_at: str
    is_soft_deleted: bool
    deleted_at: Optional[str] = None
    deleted_reason: Optional[str] = None


class MemoryListResponse(BaseModel):
    """记忆列表响应"""

    total: int
    items: List[MemoryEntryResponse]
    page: int
    page_size: int


class VerifyMemoryRequest(BaseModel):
    """验证记忆请求"""

    action: str = Field(..., description="操作类型: verify, reject, promote_to_core")
    reason: str = Field("", description="操作原因")
    verified_by: str = Field("api_user", description="操作者标识")


class DeleteMemoryRequest(BaseModel):
    """删除记忆请求"""

    reason: str = Field(..., description="删除原因")
    deleted_by: str = Field("api_user", description="删除者标识")


class RollbackMemoryRequest(BaseModel):
    """回滚记忆请求"""

    reason: str = Field("", description="回滚原因")
    rollback_by: str = Field("api_user", description="回滚者标识")


class OperationResponse(BaseModel):
    """操作响应"""

    success: bool
    message: str
    memory_id: str


# ==================== API 端点 ====================


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats():
    """
    获取记忆统计信息

    返回记忆系统的整体统计，包括：
    - 总记忆数
    - 按验证状态分布
    - 按科目分布
    - 按类型分布
    - 平均置信度
    """
    try:
        memory_service = get_memory_service()
        stats = memory_service.get_stats()

        # 计算平均置信度
        total_confidence = 0.0
        count = 0
        for entry in memory_service._long_term_memory.values():
            if not entry.is_soft_deleted:
                total_confidence += entry.confidence
                count += 1

        avg_confidence = total_confidence / count if count > 0 else 0.0

        return MemoryStatsResponse(
            total_count=stats.get("total_memories", 0),
            by_status=stats.get("memory_by_verification_status", {}),
            by_subject=stats.get("memory_by_subject", {}),
            by_type=stats.get("memory_by_type", {}),
            avg_confidence=round(avg_confidence, 3),
        )
    except Exception as e:
        logger.error(f"[MemoryAPI] 获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=MemoryListResponse)
async def list_memories(
    subject: Optional[str] = Query(None, description="科目过滤"),
    status: Optional[str] = Query(None, description="验证状态过滤"),
    memory_type: Optional[str] = Query(None, description="记忆类型过滤"),
    include_deleted: bool = Query(False, description="是否包含已删除记忆"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """
    查询记忆列表

    支持按科目、验证状态、记忆类型过滤。
    """
    try:
        memory_service = get_memory_service()

        # 构建过滤条件
        memory_types = None
        if memory_type:
            try:
                memory_types = [MemoryType(memory_type)]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的记忆类型: {memory_type}")

        # 检索记忆
        memories = memory_service.retrieve_relevant_memories(
            memory_types=memory_types,
            subject=subject,
            include_deleted=include_deleted,
            max_results=1000,  # 获取所有，然后在内存中过滤
        )

        # 按验证状态过滤
        if status:
            try:
                target_status = MemoryVerificationStatus(status)
                memories = [m for m in memories if m.verification_status == target_status]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的验证状态: {status}")

        # 分页
        total = len(memories)
        start = (page - 1) * page_size
        end = start + page_size
        page_memories = memories[start:end]

        # 转换为响应格式
        items = [
            MemoryEntryResponse(
                memory_id=m.memory_id,
                memory_type=m.memory_type.value,
                importance=m.importance.value,
                pattern=m.pattern,
                lesson=m.lesson,
                subject=m.subject,
                verification_status=m.verification_status.value,
                confidence=m.confidence,
                occurrence_count=m.occurrence_count,
                confirmation_count=m.confirmation_count,
                contradiction_count=m.contradiction_count,
                created_at=m.created_at,
                last_updated_at=m.last_updated_at,
                is_soft_deleted=m.is_soft_deleted,
                deleted_at=m.deleted_at,
                deleted_reason=m.deleted_reason,
            )
            for m in page_memories
        ]

        return MemoryListResponse(
            total=total,
            items=items,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MemoryAPI] 查询记忆列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}", response_model=MemoryEntryResponse)
async def get_memory(memory_id: str):
    """
    获取单条记忆详情
    """
    try:
        memory_service = get_memory_service()
        entry = memory_service.get_memory_by_id(memory_id)

        if not entry:
            raise HTTPException(status_code=404, detail=f"记忆 {memory_id} 不存在")

        return MemoryEntryResponse(
            memory_id=entry.memory_id,
            memory_type=entry.memory_type.value,
            importance=entry.importance.value,
            pattern=entry.pattern,
            lesson=entry.lesson,
            subject=entry.subject,
            verification_status=entry.verification_status.value,
            confidence=entry.confidence,
            occurrence_count=entry.occurrence_count,
            confirmation_count=entry.confirmation_count,
            contradiction_count=entry.contradiction_count,
            created_at=entry.created_at,
            last_updated_at=entry.last_updated_at,
            is_soft_deleted=entry.is_soft_deleted,
            deleted_at=entry.deleted_at,
            deleted_reason=entry.deleted_reason,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MemoryAPI] 获取记忆详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{memory_id}/verify", response_model=OperationResponse)
async def verify_memory(memory_id: str, request: VerifyMemoryRequest):
    """
    验证记忆

    支持的操作：
    - verify: 从 PENDING 转为 VERIFIED
    - reject: 标记为 SUSPICIOUS
    - promote_to_core: 从 VERIFIED 转为 CORE
    """
    try:
        memory_service = get_memory_service()

        if request.action == "verify":
            success = memory_service.verify_memory(
                memory_id=memory_id,
                verified_by=request.verified_by,
                reason=request.reason,
            )
            message = "记忆已验证" if success else "验证失败"
        elif request.action == "reject":
            success = memory_service.mark_suspicious(
                memory_id=memory_id,
                marked_by=request.verified_by,
                reason=request.reason,
            )
            message = "记忆已标记为可疑" if success else "标记失败"
        elif request.action == "promote_to_core":
            success = memory_service.promote_to_core(
                memory_id=memory_id,
                promoted_by=request.verified_by,
                reason=request.reason,
            )
            message = "记忆已提升为核心" if success else "提升失败"
        else:
            raise HTTPException(status_code=400, detail=f"无效的操作类型: {request.action}")

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return OperationResponse(
            success=success,
            message=message,
            memory_id=memory_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MemoryAPI] 验证记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}", response_model=OperationResponse)
async def delete_memory(memory_id: str, request: DeleteMemoryRequest):
    """
    软删除记忆

    软删除不会真正删除记忆，可以通过 rollback 恢复。
    """
    try:
        memory_service = get_memory_service()

        success = memory_service.soft_delete_memory(
            memory_id=memory_id,
            deleted_by=request.deleted_by,
            reason=request.reason,
        )

        if not success:
            raise HTTPException(status_code=400, detail="删除失败")

        return OperationResponse(
            success=success,
            message="记忆已软删除",
            memory_id=memory_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MemoryAPI] 删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{memory_id}/rollback", response_model=OperationResponse)
async def rollback_memory(memory_id: str, request: RollbackMemoryRequest):
    """
    回滚记忆

    将已软删除的记忆恢复到删除前的状态。
    """
    try:
        memory_service = get_memory_service()

        success = memory_service.rollback_memory(
            memory_id=memory_id,
            rollback_by=request.rollback_by,
            reason=request.reason,
        )

        if not success:
            raise HTTPException(status_code=400, detail="回滚失败")

        return OperationResponse(
            success=success,
            message="记忆已回滚",
            memory_id=memory_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MemoryAPI] 回滚记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 导出
__all__ = ["router"]
