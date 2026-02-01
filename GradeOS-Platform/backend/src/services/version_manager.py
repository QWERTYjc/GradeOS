"""版本管理器服务

负责规则补丁的版本分配、部署记录、回滚和历史查询。
验证：需求 10.1, 10.2, 10.3, 10.4, 10.5
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel

from src.models.rule_patch import RulePatch, PatchStatus
from src.utils.database import get_db_pool


logger = logging.getLogger(__name__)


class VersionConflictError(Exception):
    """版本冲突错误"""

    pass


class DependencyError(Exception):
    """依赖关系错误"""

    pass


class PatchVersion(BaseModel):
    """补丁版本模型

    表示补丁的版本信息。
    验证：需求 10.1, 10.2, 10.4
    """

    version: str
    patch_id: str
    created_at: datetime
    deployed_at: Optional[datetime] = None
    status: PatchStatus
    dependencies: List[str] = []


class VersionManager:
    """版本管理器

    功能：
    1. 分配唯一版本号（allocate_version）
    2. 记录部署信息（record_deployment）
    3. 回滚到指定版本（rollback_to_version）
    4. 查询补丁历史（get_history）

    验证：需求 10.1, 10.2, 10.3, 10.4, 10.5
    """

    def __init__(self):
        """初始化版本管理器"""
        self._version_counter = 0
        self._version_lock = asyncio.Lock()

    async def allocate_version(self) -> str:
        """分配唯一版本号

        生成格式为 v{major}.{minor}.{patch} 的版本号。
        验证：需求 10.1

        Returns:
            版本号字符串（如 "v1.0.0"）
        """
        async with self._version_lock:
            # 获取当前最大版本号
            pool = await get_db_pool()
            async with pool.connection() as conn:
                query = """
                    SELECT version
                    FROM rule_patches
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                row = await conn.fetchrow(query)

                if row and row["version"]:
                    # 解析现有版本号
                    last_version = row["version"]
                    try:
                        # 假设格式为 v{major}.{minor}.{patch}
                        parts = last_version.lstrip("v").split(".")
                        major, minor, patch = map(int, parts)
                        # 递增 patch 版本
                        new_version = f"v{major}.{minor}.{patch + 1}"
                    except (ValueError, IndexError):
                        # 如果解析失败，使用时间戳
                        new_version = f"v1.0.{int(datetime.utcnow().timestamp())}"
                else:
                    # 第一个版本
                    new_version = "v1.0.0"

                # 确保版本号唯一
                check_query = """
                    SELECT COUNT(*) as count
                    FROM rule_patches
                    WHERE version = $1
                """
                check_row = await conn.fetchrow(check_query, new_version)

                if check_row["count"] > 0:
                    # 版本号冲突，使用 UUID 后缀
                    new_version = f"{new_version}-{uuid4().hex[:8]}"

                logger.info(f"分配新版本号：{new_version}")
                return new_version

    async def record_deployment(self, patch_id: str, scope: str) -> bool:
        """记录部署信息

        记录补丁的部署时间和部署范围。
        验证：需求 10.2

        Args:
            patch_id: 补丁ID
            scope: 部署范围（"canary" 或 "full"）

        Returns:
            是否成功

        Raises:
            ValueError: 补丁不存在或参数无效
        """
        if scope not in ["canary", "full"]:
            raise ValueError(f"无效的部署范围：{scope}，必须是 'canary' 或 'full'")

        logger.info(f"记录部署信息：补丁 {patch_id}，范围 {scope}")

        try:
            pool = await get_db_pool()
            async with pool.connection() as conn:
                # 检查补丁是否存在
                check_query = """
                    SELECT patch_id, version
                    FROM rule_patches
                    WHERE patch_id = $1
                """
                row = await conn.fetchrow(check_query, patch_id)

                if not row:
                    raise ValueError(f"补丁 {patch_id} 不存在")

                # 更新部署信息
                update_query = """
                    UPDATE rule_patches
                    SET deployed_at = NOW(),
                        deployment_scope = $1,
                        status = CASE
                            WHEN $1 = 'canary' THEN 'testing'
                            WHEN $1 = 'full' THEN 'deployed'
                            ELSE status
                        END,
                        updated_at = NOW()
                    WHERE patch_id = $2
                """
                await conn.execute(update_query, scope, patch_id)

                logger.info(
                    f"部署信息已记录：补丁 {patch_id} (版本 {row['version']})，" f"范围 {scope}"
                )
                return True

        except Exception as e:
            logger.error(f"记录部署信息失败：{e}")
            raise

    async def rollback_to_version(self, target_version: str) -> bool:
        """回滚到指定版本

        将系统恢复到指定版本的规则集，处理依赖关系。
        验证：需求 10.3, 10.5

        Args:
            target_version: 目标版本号

        Returns:
            是否成功

        Raises:
            ValueError: 版本不存在
            DependencyError: 依赖关系冲突
        """
        logger.info(f"开始回滚到版本：{target_version}")

        try:
            pool = await get_db_pool()
            async with pool.connection() as conn:
                # 查找目标版本
                target_query = """
                    SELECT patch_id, version, dependencies, created_at
                    FROM rule_patches
                    WHERE version = $1
                """
                target_row = await conn.fetchrow(target_query, target_version)

                if not target_row:
                    raise ValueError(f"版本 {target_version} 不存在")

                target_created_at = target_row["created_at"]
                target_dependencies = target_row["dependencies"] or []

                # 查找所有需要回滚的补丁（创建时间晚于目标版本）
                rollback_query = """
                    SELECT patch_id, version, status
                    FROM rule_patches
                    WHERE created_at > $1
                    AND status IN ('testing', 'deployed')
                    ORDER BY created_at DESC
                """
                rollback_rows = await conn.fetch(rollback_query, target_created_at)

                if not rollback_rows:
                    logger.info(f"无需回滚，当前已是版本 {target_version}")
                    return True

                # 检查依赖关系
                await self._check_dependencies_for_rollback(
                    conn,
                    target_version,
                    target_dependencies,
                    [row["version"] for row in rollback_rows],
                )

                # 执行回滚
                for row in rollback_rows:
                    patch_id = row["patch_id"]
                    version = row["version"]

                    update_query = """
                        UPDATE rule_patches
                        SET status = 'rolled_back',
                            rolled_back_at = NOW(),
                            deployment_scope = NULL,
                            updated_at = NOW()
                        WHERE patch_id = $1
                    """
                    await conn.execute(update_query, patch_id)

                    logger.info(f"已回滚补丁：{patch_id} (版本 {version})")

                # 确保目标版本处于部署状态
                activate_query = """
                    UPDATE rule_patches
                    SET status = 'deployed',
                        deployment_scope = 'full',
                        deployed_at = NOW(),
                        updated_at = NOW()
                    WHERE version = $1
                """
                await conn.execute(activate_query, target_version)

                logger.info(
                    f"回滚成功：已回滚 {len(rollback_rows)} 个补丁，" f"当前版本 {target_version}"
                )
                return True

        except Exception as e:
            logger.error(f"回滚失败：{e}")
            raise

    async def get_history(self, limit: int = 50) -> List[PatchVersion]:
        """获取补丁历史

        返回补丁的版本历史列表，按创建时间倒序排列。
        验证：需求 10.4

        Args:
            limit: 返回的最大记录数

        Returns:
            补丁版本列表
        """
        logger.info(f"查询补丁历史，限制 {limit} 条")

        try:
            pool = await get_db_pool()
            async with pool.connection() as conn:
                query = """
                    SELECT patch_id, version, status, dependencies,
                           created_at, deployed_at
                    FROM rule_patches
                    ORDER BY created_at DESC
                    LIMIT $1
                """
                rows = await conn.fetch(query, limit)

                history = [
                    PatchVersion(
                        version=row["version"],
                        patch_id=str(row["patch_id"]),
                        created_at=row["created_at"],
                        deployed_at=row["deployed_at"],
                        status=PatchStatus(row["status"]),
                        dependencies=row["dependencies"] or [],
                    )
                    for row in rows
                ]

                logger.info(f"查询到 {len(history)} 条补丁历史")
                return history

        except Exception as e:
            logger.error(f"查询补丁历史失败：{e}")
            raise

    async def _check_dependencies_for_rollback(
        self,
        conn,
        target_version: str,
        target_dependencies: List[str],
        rollback_versions: List[str],
    ) -> None:
        """检查回滚的依赖关系

        确保回滚不会破坏依赖关系。
        验证：需求 10.5

        Args:
            conn: 数据库连接
            target_version: 目标版本
            target_dependencies: 目标版本的依赖列表
            rollback_versions: 将要回滚的版本列表

        Raises:
            DependencyError: 依赖关系冲突
        """
        # 检查目标版本的依赖是否会被回滚
        for dep_version in target_dependencies:
            if dep_version in rollback_versions:
                raise DependencyError(
                    f"无法回滚到版本 {target_version}：依赖的版本 {dep_version} " f"将被回滚"
                )

        # 检查是否有其他已部署的补丁依赖于将要回滚的版本
        for rollback_version in rollback_versions:
            check_query = """
                SELECT patch_id, version
                FROM rule_patches
                WHERE status IN ('testing', 'deployed')
                AND $1 = ANY(dependencies)
                AND version != $2
            """
            dependent_rows = await conn.fetch(check_query, rollback_version, target_version)

            if dependent_rows:
                dependent_versions = [row["version"] for row in dependent_rows]
                raise DependencyError(
                    f"无法回滚版本 {rollback_version}：以下版本依赖于它：{dependent_versions}"
                )

        logger.info("依赖关系检查通过")


# 全局单例
_version_manager: Optional[VersionManager] = None


def get_version_manager() -> VersionManager:
    """获取版本管理器单例"""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager
