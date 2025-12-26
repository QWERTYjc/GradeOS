"""补丁部署器服务

负责规则补丁的灰度发布、全量发布、回滚和监控。
验证：需求 9.4, 9.5
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.rule_patch import RulePatch, PatchStatus
from src.utils.database import get_db_pool


logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """部署错误"""
    pass


class AnomalyDetected(Exception):
    """检测到异常"""
    pass


class PatchDeployer:
    """补丁部署器
    
    功能：
    1. 灰度发布补丁（deploy_canary）
    2. 全量发布补丁（promote_to_full）
    3. 回滚补丁（rollback）
    4. 监控部署状态（monitor_deployment）
    
    验证：需求 9.4, 9.5
    """
    
    def __init__(
        self,
        canary_duration_minutes: int = 30,
        anomaly_threshold: float = 0.1,
        error_rate_threshold: float = 0.2
    ):
        """初始化补丁部署器
        
        Args:
            canary_duration_minutes: 灰度发布持续时间（分钟）
            anomaly_threshold: 异常阈值（误判率增加超过此值触发回滚）
            error_rate_threshold: 错误率阈值（超过此值触发回滚）
        """
        self.canary_duration_minutes = canary_duration_minutes
        self.anomaly_threshold = anomaly_threshold
        self.error_rate_threshold = error_rate_threshold
        self._active_deployments: Dict[str, Dict[str, Any]] = {}
    
    async def deploy_canary(
        self,
        patch: RulePatch,
        traffic_percentage: float = 0.1
    ) -> str:
        """灰度发布补丁
        
        将补丁部署到一小部分流量（默认10%），用于验证补丁的有效性。
        验证：需求 9.4
        
        Args:
            patch: 待部署的规则补丁
            traffic_percentage: 灰度流量比例（0.0-1.0）
            
        Returns:
            deployment_id: 部署ID
            
        Raises:
            DeploymentError: 部署失败
        """
        if not 0.0 < traffic_percentage <= 1.0:
            raise ValueError(f"流量比例必须在 (0.0, 1.0] 范围内，当前值：{traffic_percentage}")
        
        logger.info(
            f"开始灰度发布：补丁 {patch.patch_id} (版本 {patch.version})，"
            f"流量比例 {traffic_percentage:.1%}"
        )
        
        # 生成部署ID
        deployment_id = f"deploy_{uuid4().hex[:8]}"
        
        try:
            # 更新补丁状态为测试中
            await self._update_patch_status(
                patch.patch_id,
                PatchStatus.TESTING,
                deployment_scope="canary",
                deployed_at=datetime.utcnow()
            )
            
            # 将补丁内容写入部署配置
            await self._write_deployment_config(
                deployment_id=deployment_id,
                patch=patch,
                traffic_percentage=traffic_percentage,
                scope="canary"
            )
            
            # 记录部署信息
            self._active_deployments[deployment_id] = {
                "patch_id": patch.patch_id,
                "version": patch.version,
                "traffic_percentage": traffic_percentage,
                "scope": "canary",
                "started_at": datetime.utcnow(),
                "baseline_metrics": await self._get_current_metrics()
            }
            
            logger.info(f"灰度发布成功：部署ID {deployment_id}")
            return deployment_id
            
        except Exception as e:
            logger.error(f"灰度发布失败：{e}")
            # 尝试清理
            await self._cleanup_deployment(deployment_id)
            raise DeploymentError(f"灰度发布失败：{e}") from e
    
    async def promote_to_full(self, deployment_id: str) -> bool:
        """全量发布
        
        将灰度发布的补丁推广到全部流量。
        验证：需求 9.4
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            是否成功
            
        Raises:
            DeploymentError: 部署不存在或状态不正确
        """
        if deployment_id not in self._active_deployments:
            raise DeploymentError(f"部署 {deployment_id} 不存在")
        
        deployment = self._active_deployments[deployment_id]
        patch_id = deployment["patch_id"]
        version = deployment["version"]
        
        logger.info(f"开始全量发布：部署 {deployment_id}，补丁 {patch_id} (版本 {version})")
        
        try:
            # 更新流量比例为100%
            await self._write_deployment_config(
                deployment_id=deployment_id,
                patch=await self._load_patch(patch_id),
                traffic_percentage=1.0,
                scope="full"
            )
            
            # 更新补丁状态为已部署
            await self._update_patch_status(
                patch_id,
                PatchStatus.DEPLOYED,
                deployment_scope="full",
                deployed_at=datetime.utcnow()
            )
            
            # 更新部署信息
            deployment["scope"] = "full"
            deployment["traffic_percentage"] = 1.0
            deployment["promoted_at"] = datetime.utcnow()
            
            logger.info(f"全量发布成功：部署 {deployment_id}")
            return True
            
        except Exception as e:
            logger.error(f"全量发布失败：{e}")
            raise DeploymentError(f"全量发布失败：{e}") from e
    
    async def rollback(self, deployment_id: str) -> bool:
        """回滚到上一版本
        
        将补丁回滚，恢复到部署前的状态。
        验证：需求 9.5
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            是否成功
        """
        if deployment_id not in self._active_deployments:
            logger.warning(f"部署 {deployment_id} 不存在，可能已经回滚")
            return True
        
        deployment = self._active_deployments[deployment_id]
        patch_id = deployment["patch_id"]
        version = deployment["version"]
        
        logger.warning(f"开始回滚：部署 {deployment_id}，补丁 {patch_id} (版本 {version})")
        
        try:
            # 删除部署配置
            await self._remove_deployment_config(deployment_id)
            
            # 更新补丁状态为已回滚
            await self._update_patch_status(
                patch_id,
                PatchStatus.ROLLED_BACK,
                deployment_scope=None,
                rolled_back_at=datetime.utcnow()
            )
            
            # 移除部署记录
            del self._active_deployments[deployment_id]
            
            logger.info(f"回滚成功：部署 {deployment_id}")
            return True
            
        except Exception as e:
            logger.error(f"回滚失败：{e}")
            return False
    
    async def monitor_deployment(
        self,
        deployment_id: str
    ) -> Dict[str, Any]:
        """监控部署状态
        
        持续监控部署的指标，检测异常并在必要时自动回滚。
        验证：需求 9.5
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            监控结果，包含：
            - status: 状态（healthy/warning/critical）
            - metrics: 当前指标
            - anomalies: 检测到的异常列表
            - action_taken: 采取的行动（none/rollback）
        """
        if deployment_id not in self._active_deployments:
            return {
                "status": "not_found",
                "message": f"部署 {deployment_id} 不存在"
            }
        
        deployment = self._active_deployments[deployment_id]
        patch_id = deployment["patch_id"]
        baseline_metrics = deployment["baseline_metrics"]
        
        logger.info(f"监控部署：{deployment_id}")
        
        try:
            # 获取当前指标
            current_metrics = await self._get_current_metrics()
            
            # 检测异常
            anomalies = self._detect_anomalies(baseline_metrics, current_metrics)
            
            # 判断状态
            if not anomalies:
                status = "healthy"
                action_taken = "none"
            elif any(a["severity"] == "critical" for a in anomalies):
                status = "critical"
                # 自动回滚
                logger.error(f"检测到严重异常，自动回滚部署 {deployment_id}")
                await self.rollback(deployment_id)
                action_taken = "rollback"
            else:
                status = "warning"
                action_taken = "none"
            
            result = {
                "status": status,
                "deployment_id": deployment_id,
                "patch_id": patch_id,
                "metrics": current_metrics,
                "baseline_metrics": baseline_metrics,
                "anomalies": anomalies,
                "action_taken": action_taken,
                "monitored_at": datetime.utcnow().isoformat()
            }
            
            logger.info(
                f"监控结果：{status} | "
                f"异常数 {len(anomalies)} | "
                f"行动 {action_taken}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"监控失败：{e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _detect_anomalies(
        self,
        baseline: Dict[str, float],
        current: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """检测异常
        
        对比基线指标和当前指标，识别异常情况。
        
        Args:
            baseline: 基线指标
            current: 当前指标
            
        Returns:
            异常列表
        """
        anomalies = []
        
        # 检查误判率
        if "error_rate" in baseline and "error_rate" in current:
            error_rate_increase = current["error_rate"] - baseline["error_rate"]
            if error_rate_increase > self.anomaly_threshold:
                anomalies.append({
                    "type": "error_rate_increase",
                    "severity": "critical",
                    "baseline": baseline["error_rate"],
                    "current": current["error_rate"],
                    "increase": error_rate_increase,
                    "message": f"误判率增加 {error_rate_increase:.2%}"
                })
            
            # 检查绝对错误率
            if current["error_rate"] > self.error_rate_threshold:
                anomalies.append({
                    "type": "high_error_rate",
                    "severity": "critical",
                    "current": current["error_rate"],
                    "threshold": self.error_rate_threshold,
                    "message": f"误判率过高 {current['error_rate']:.2%}"
                })
        
        # 检查漏判率
        if "miss_rate" in baseline and "miss_rate" in current:
            miss_rate_increase = current["miss_rate"] - baseline["miss_rate"]
            if miss_rate_increase > self.anomaly_threshold:
                anomalies.append({
                    "type": "miss_rate_increase",
                    "severity": "warning",
                    "baseline": baseline["miss_rate"],
                    "current": current["miss_rate"],
                    "increase": miss_rate_increase,
                    "message": f"漏判率增加 {miss_rate_increase:.2%}"
                })
        
        # 检查复核率
        if "review_rate" in baseline and "review_rate" in current:
            review_rate_increase = current["review_rate"] - baseline["review_rate"]
            if review_rate_increase > self.anomaly_threshold * 2:  # 复核率阈值放宽
                anomalies.append({
                    "type": "review_rate_increase",
                    "severity": "warning",
                    "baseline": baseline["review_rate"],
                    "current": current["review_rate"],
                    "increase": review_rate_increase,
                    "message": f"复核率增加 {review_rate_increase:.2%}"
                })
        
        return anomalies
    
    async def _update_patch_status(
        self,
        patch_id: str,
        status: PatchStatus,
        deployment_scope: Optional[str] = None,
        deployed_at: Optional[datetime] = None,
        rolled_back_at: Optional[datetime] = None
    ) -> None:
        """更新补丁状态
        
        Args:
            patch_id: 补丁ID
            status: 新状态
            deployment_scope: 部署范围
            deployed_at: 部署时间
            rolled_back_at: 回滚时间
        """
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = """
                UPDATE rule_patches
                SET status = $1,
                    deployment_scope = $2,
                    deployed_at = $3,
                    rolled_back_at = $4,
                    updated_at = NOW()
                WHERE patch_id = $5
            """
            await conn.execute(
                query,
                status.value,
                deployment_scope,
                deployed_at,
                rolled_back_at,
                patch_id
            )
        
        logger.info(f"更新补丁状态：{patch_id} -> {status.value}")
    
    async def _write_deployment_config(
        self,
        deployment_id: str,
        patch: RulePatch,
        traffic_percentage: float,
        scope: str
    ) -> None:
        """写入部署配置
        
        将补丁内容写入配置系统，使其生效。
        
        Args:
            deployment_id: 部署ID
            patch: 补丁对象
            traffic_percentage: 流量比例
            scope: 部署范围
        """
        # TODO: 实际实现应该写入配置中心（如 Redis、Consul 等）
        # 这里仅记录日志
        logger.info(
            f"写入部署配置：{deployment_id} | "
            f"补丁 {patch.patch_id} | "
            f"流量 {traffic_percentage:.1%} | "
            f"范围 {scope}"
        )
        
        # 模拟写入配置
        config = {
            "deployment_id": deployment_id,
            "patch_id": patch.patch_id,
            "version": patch.version,
            "patch_type": patch.patch_type.value,
            "content": patch.content,
            "traffic_percentage": traffic_percentage,
            "scope": scope,
            "deployed_at": datetime.utcnow().isoformat()
        }
        
        # 实际实现应该写入 Redis 或其他配置中心
        # await redis.set(f"deployment:{deployment_id}", json.dumps(config))
    
    async def _remove_deployment_config(self, deployment_id: str) -> None:
        """删除部署配置
        
        Args:
            deployment_id: 部署ID
        """
        # TODO: 实际实现应该从配置中心删除
        logger.info(f"删除部署配置：{deployment_id}")
        
        # 实际实现应该从 Redis 删除
        # await redis.delete(f"deployment:{deployment_id}")
    
    async def _cleanup_deployment(self, deployment_id: str) -> None:
        """清理部署资源
        
        Args:
            deployment_id: 部署ID
        """
        try:
            await self._remove_deployment_config(deployment_id)
            if deployment_id in self._active_deployments:
                del self._active_deployments[deployment_id]
        except Exception as e:
            logger.error(f"清理部署资源失败：{e}")
    
    async def _load_patch(self, patch_id: str) -> RulePatch:
        """加载补丁
        
        Args:
            patch_id: 补丁ID
            
        Returns:
            补丁对象
        """
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            query = """
                SELECT patch_id, patch_type, version, description, content,
                       source_pattern_id, status, dependencies,
                       deployed_at, deployment_scope, rolled_back_at,
                       regression_result, created_at
                FROM rule_patches
                WHERE patch_id = $1
            """
            row = await conn.fetchrow(query, patch_id)
            
            if not row:
                raise ValueError(f"补丁 {patch_id} 不存在")
            
            return RulePatch(
                patch_id=str(row["patch_id"]),
                patch_type=row["patch_type"],
                version=row["version"],
                description=row["description"],
                content=row["content"],
                source_pattern_id=row["source_pattern_id"],
                status=row["status"],
                dependencies=row["dependencies"] or [],
                deployed_at=row["deployed_at"],
                deployment_scope=row["deployment_scope"],
                rolled_back_at=row["rolled_back_at"],
                regression_result=row["regression_result"],
                created_at=row["created_at"]
            )
    
    async def _get_current_metrics(self) -> Dict[str, float]:
        """获取当前系统指标
        
        Returns:
            指标字典，包含：
            - error_rate: 误判率
            - miss_rate: 漏判率
            - review_rate: 复核率
        """
        # TODO: 实际实现应该从监控系统获取实时指标
        # 这里返回模拟数据
        return {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15,
            "timestamp": datetime.utcnow().isoformat()
        }


# 全局单例
_patch_deployer: Optional[PatchDeployer] = None


def get_patch_deployer() -> PatchDeployer:
    """获取补丁部署器单例"""
    global _patch_deployer
    if _patch_deployer is None:
        _patch_deployer = PatchDeployer()
    return _patch_deployer
