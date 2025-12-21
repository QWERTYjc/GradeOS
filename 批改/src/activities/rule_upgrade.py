"""规则升级相关 Activities

提供规则挖掘、补丁生成、回归测试和部署的 Activity 实现。
"""

import logging
from typing import Dict, Any, List

from temporalio import activity

from src.services.rule_miner import RuleMiner
from src.services.patch_generator import PatchGenerator
from src.services.regression_tester import RegressionTester
from src.services.patch_deployer import PatchDeployer
from src.services.grading_logger import GradingLogger
from src.utils.pool_manager import UnifiedPoolManager


logger = logging.getLogger(__name__)


@activity.defn
async def mine_failure_patterns_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    挖掘失败模式 Activity
    
    Args:
        input_data: {
            "min_sample_count": int,
            "time_window_days": int
        }
        
    Returns:
        {
            "patterns": List[Dict],
            "total_samples": int
        }
    """
    min_sample_count = input_data["min_sample_count"]
    time_window_days = input_data["time_window_days"]
    
    try:
        # 初始化服务
        grading_logger = GradingLogger()
        rule_miner = RuleMiner()
        
        # 获取改判样本
        override_samples = await grading_logger.get_override_samples(
            min_count=min_sample_count,
            days=time_window_days
        )
        
        if len(override_samples) < min_sample_count:
            logger.warning(
                f"改判样本不足: {len(override_samples)} < {min_sample_count}"
            )
            return {
                "patterns": [],
                "total_samples": len(override_samples)
            }
        
        # 分析失败模式
        patterns = await rule_miner.analyze_overrides(override_samples)
        
        # 转换为字典格式
        patterns_dict = [
            {
                "pattern_id": p.pattern_id,
                "pattern_type": p.pattern_type,
                "description": p.description,
                "frequency": p.frequency,
                "sample_logs": p.sample_logs
            }
            for p in patterns
        ]
        
        logger.info(f"挖掘到 {len(patterns_dict)} 个失败模式")
        
        return {
            "patterns": patterns_dict,
            "total_samples": len(override_samples)
        }
        
    except Exception as e:
        logger.error(f"挖掘失败模式失败: {e}")
        return {
            "patterns": [],
            "total_samples": 0
        }


@activity.defn
async def generate_patch_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成补丁 Activity
    
    Args:
        input_data: {
            "pattern": Dict
        }
        
    Returns:
        {
            "patch": Dict or None
        }
    """
    pattern_dict = input_data["pattern"]
    
    try:
        # 初始化服务
        patch_generator = PatchGenerator()
        
        # 重建 FailurePattern 对象
        from src.services.rule_miner import FailurePattern
        pattern = FailurePattern(
            pattern_id=pattern_dict["pattern_id"],
            pattern_type=pattern_dict["pattern_type"],
            description=pattern_dict["description"],
            frequency=pattern_dict["frequency"],
            sample_logs=pattern_dict["sample_logs"]
        )
        
        # 生成补丁
        patch = await patch_generator.generate_patch(pattern)
        
        if patch:
            logger.info(f"成功生成补丁: {patch.patch_id}")
            return {
                "patch": patch.model_dump()
            }
        else:
            logger.warning(f"无法为模式 {pattern.pattern_id} 生成补丁")
            return {
                "patch": None
            }
        
    except Exception as e:
        logger.error(f"生成补丁失败: {e}")
        return {
            "patch": None
        }


@activity.defn
async def run_regression_test_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    运行回归测试 Activity
    
    Args:
        input_data: {
            "patch": Dict,
            "eval_set_id": str
        }
        
    Returns:
        {
            "passed": bool,
            "result": Dict
        }
    """
    patch_dict = input_data["patch"]
    eval_set_id = input_data["eval_set_id"]
    
    try:
        # 初始化服务
        regression_tester = RegressionTester()
        
        # 重建 RulePatch 对象
        from src.models.rule_patch import RulePatch, PatchType
        patch = RulePatch(
            patch_id=patch_dict["patch_id"],
            patch_type=PatchType(patch_dict["patch_type"]),
            version=patch_dict["version"],
            description=patch_dict["description"],
            content=patch_dict["content"],
            source_pattern_id=patch_dict["source_pattern_id"],
            status=patch_dict["status"]
        )
        
        # 运行回归测试
        result = await regression_tester.run_regression(patch, eval_set_id)
        
        # 判断是否通过
        passed = regression_tester.is_improvement(result)
        
        logger.info(
            f"回归测试完成: patch_id={patch.patch_id}, "
            f"passed={passed}"
        )
        
        return {
            "passed": passed,
            "result": {
                "patch_id": result.patch_id,
                "old_error_rate": result.old_error_rate,
                "new_error_rate": result.new_error_rate,
                "improved_samples": result.improved_samples,
                "degraded_samples": result.degraded_samples
            }
        }
        
    except Exception as e:
        logger.error(f"运行回归测试失败: {e}")
        return {
            "passed": False,
            "result": {}
        }


@activity.defn
async def deploy_patch_canary_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    灰度发布补丁 Activity
    
    Args:
        input_data: {
            "patch": Dict,
            "traffic_percentage": float
        }
        
    Returns:
        {
            "deployment_id": str or None
        }
    """
    patch_dict = input_data["patch"]
    traffic_percentage = input_data["traffic_percentage"]
    
    try:
        # 初始化服务
        patch_deployer = PatchDeployer()
        
        # 重建 RulePatch 对象
        from src.models.rule_patch import RulePatch, PatchType
        patch = RulePatch(
            patch_id=patch_dict["patch_id"],
            patch_type=PatchType(patch_dict["patch_type"]),
            version=patch_dict["version"],
            description=patch_dict["description"],
            content=patch_dict["content"],
            source_pattern_id=patch_dict["source_pattern_id"],
            status=patch_dict["status"]
        )
        
        # 灰度发布
        deployment_id = await patch_deployer.deploy_canary(
            patch,
            traffic_percentage=traffic_percentage
        )
        
        logger.info(f"灰度发布成功: deployment_id={deployment_id}")
        
        return {
            "deployment_id": deployment_id
        }
        
    except Exception as e:
        logger.error(f"灰度发布失败: {e}")
        return {
            "deployment_id": None
        }


@activity.defn
async def monitor_deployment_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    监控部署 Activity
    
    Args:
        input_data: {
            "deployment_id": str
        }
        
    Returns:
        {
            "has_anomaly": bool,
            "metrics": Dict
        }
    """
    deployment_id = input_data["deployment_id"]
    
    try:
        # 初始化服务
        patch_deployer = PatchDeployer()
        
        # 监控部署
        metrics = await patch_deployer.monitor_deployment(deployment_id)
        
        # 检查是否有异常
        has_anomaly = metrics.get("has_anomaly", False)
        
        logger.info(
            f"部署监控完成: deployment_id={deployment_id}, "
            f"has_anomaly={has_anomaly}"
        )
        
        return {
            "has_anomaly": has_anomaly,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"监控部署失败: {e}")
        return {
            "has_anomaly": True,  # 出错时保守处理
            "metrics": {}
        }


@activity.defn
async def rollback_deployment_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    回滚部署 Activity
    
    Args:
        input_data: {
            "deployment_id": str
        }
        
    Returns:
        {
            "success": bool
        }
    """
    deployment_id = input_data["deployment_id"]
    
    try:
        # 初始化服务
        patch_deployer = PatchDeployer()
        
        # 回滚
        success = await patch_deployer.rollback(deployment_id)
        
        logger.info(f"回滚部署: deployment_id={deployment_id}, success={success}")
        
        return {
            "success": success
        }
        
    except Exception as e:
        logger.error(f"回滚部署失败: {e}")
        return {
            "success": False
        }


@activity.defn
async def promote_deployment_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    全量发布 Activity
    
    Args:
        input_data: {
            "deployment_id": str
        }
        
    Returns:
        {
            "success": bool
        }
    """
    deployment_id = input_data["deployment_id"]
    
    try:
        # 初始化服务
        patch_deployer = PatchDeployer()
        
        # 全量发布
        success = await patch_deployer.promote_to_full(deployment_id)
        
        logger.info(f"全量发布: deployment_id={deployment_id}, success={success}")
        
        return {
            "success": success
        }
        
    except Exception as e:
        logger.error(f"全量发布失败: {e}")
        return {
            "success": False
        }
