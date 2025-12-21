"""规则升级定时任务工作流

实现自动规则升级流程：
RuleMiner → PatchGenerator → RegressionTester → PatchDeployer

验证：需求 9.1, 9.2, 9.3, 9.4
"""

import logging
from datetime import timedelta, datetime
from typing import Dict, Any, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from src.services.rule_miner import RuleMiner
from src.services.patch_generator import PatchGenerator
from src.services.regression_tester import RegressionTester
from src.services.patch_deployer import PatchDeployer
from src.services.grading_logger import GradingLogger


logger = logging.getLogger(__name__)


RULE_UPGRADE_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=3
)


@workflow.defn
class RuleUpgradeWorkflow:
    """
    规则升级工作流
    
    定期执行规则升级流程：
    1. 从批改日志中挖掘失败模式（RuleMiner）
    2. 生成候选规则补丁（PatchGenerator）
    3. 在评测集上运行回归测试（RegressionTester）
    4. 灰度发布通过测试的补丁（PatchDeployer）
    
    验证：需求 9.1, 9.2, 9.3, 9.4
    """
    
    def __init__(self):
        self._progress: Dict[str, Any] = {}
        self._patterns_found: int = 0
        self._patches_generated: int = 0
        self._patches_deployed: int = 0
    
    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        """查询升级进度"""
        return self._progress
    
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行规则升级工作流
        
        Args:
            input_data: {
                "min_sample_count": int,      # 最小样本数量（默认 100）
                "time_window_days": int,      # 时间窗口天数（默认 7）
                "eval_set_id": str,           # 评测集 ID
                "canary_traffic": float,      # 灰度流量比例（默认 0.1）
                "auto_promote": bool,         # 是否自动全量发布（默认 False）
            }
            
        Returns:
            dict: {
                "upgrade_id": str,
                "patterns_found": int,
                "patches_generated": int,
                "patches_tested": int,
                "patches_deployed": int,
                "patches_failed": int,
                "completed_at": str
            }
        """
        upgrade_id = f"upgrade_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        min_sample_count = input_data.get("min_sample_count", 100)
        time_window_days = input_data.get("time_window_days", 7)
        eval_set_id = input_data.get("eval_set_id", "default_eval_set")
        canary_traffic = input_data.get("canary_traffic", 0.1)
        auto_promote = input_data.get("auto_promote", False)
        
        logger.info(
            f"启动规则升级工作流: "
            f"upgrade_id={upgrade_id}, "
            f"min_sample_count={min_sample_count}, "
            f"time_window_days={time_window_days}"
        )
        
        self._progress = {
            "stage": "initializing",
            "upgrade_id": upgrade_id,
            "started_at": datetime.now().isoformat()
        }
        
        try:
            # ===== 第一步：规则挖掘 =====
            self._progress["stage"] = "mining"
            logger.info("开始规则挖掘")
            
            mining_result = await workflow.execute_activity(
                "mine_failure_patterns_activity",
                {
                    "min_sample_count": min_sample_count,
                    "time_window_days": time_window_days
                },
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RULE_UPGRADE_RETRY_POLICY
            )
            
            patterns = mining_result.get("patterns", [])
            self._patterns_found = len(patterns)
            self._progress["patterns_found"] = self._patterns_found
            
            logger.info(f"规则挖掘完成: 发现 {self._patterns_found} 个失败模式")
            
            if self._patterns_found == 0:
                logger.info("未发现失败模式，跳过补丁生成")
                return {
                    "upgrade_id": upgrade_id,
                    "patterns_found": 0,
                    "patches_generated": 0,
                    "patches_tested": 0,
                    "patches_deployed": 0,
                    "patches_failed": 0,
                    "completed_at": datetime.now().isoformat()
                }
            
            # ===== 第二步：补丁生成 =====
            self._progress["stage"] = "generating"
            logger.info("开始生成补丁")
            
            patches = []
            for pattern in patterns:
                try:
                    patch_result = await workflow.execute_activity(
                        "generate_patch_activity",
                        {"pattern": pattern},
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RULE_UPGRADE_RETRY_POLICY
                    )
                    
                    if patch_result.get("patch"):
                        patches.append(patch_result["patch"])
                        
                except Exception as e:
                    logger.warning(f"生成补丁失败: {e}")
                    continue
            
            self._patches_generated = len(patches)
            self._progress["patches_generated"] = self._patches_generated
            
            logger.info(f"补丁生成完成: 生成 {self._patches_generated} 个候选补丁")
            
            if self._patches_generated == 0:
                logger.info("未生成补丁，结束流程")
                return {
                    "upgrade_id": upgrade_id,
                    "patterns_found": self._patterns_found,
                    "patches_generated": 0,
                    "patches_tested": 0,
                    "patches_deployed": 0,
                    "patches_failed": 0,
                    "completed_at": datetime.now().isoformat()
                }
            
            # ===== 第三步：回归测试 =====
            self._progress["stage"] = "testing"
            logger.info("开始回归测试")
            
            tested_patches = []
            failed_patches = []
            
            for patch in patches:
                try:
                    test_result = await workflow.execute_activity(
                        "run_regression_test_activity",
                        {
                            "patch": patch,
                            "eval_set_id": eval_set_id
                        },
                        start_to_close_timeout=timedelta(minutes=15),
                        retry_policy=RULE_UPGRADE_RETRY_POLICY
                    )
                    
                    if test_result.get("passed"):
                        tested_patches.append({
                            "patch": patch,
                            "test_result": test_result
                        })
                        logger.info(f"补丁 {patch.get('patch_id')} 通过回归测试")
                    else:
                        failed_patches.append(patch)
                        logger.warning(f"补丁 {patch.get('patch_id')} 未通过回归测试")
                        
                except Exception as e:
                    logger.error(f"回归测试失败: {e}")
                    failed_patches.append(patch)
                    continue
            
            patches_tested = len(tested_patches) + len(failed_patches)
            self._progress["patches_tested"] = patches_tested
            self._progress["patches_failed"] = len(failed_patches)
            
            logger.info(
                f"回归测试完成: "
                f"通过 {len(tested_patches)}, "
                f"失败 {len(failed_patches)}"
            )
            
            if len(tested_patches) == 0:
                logger.info("没有补丁通过测试，结束流程")
                return {
                    "upgrade_id": upgrade_id,
                    "patterns_found": self._patterns_found,
                    "patches_generated": self._patches_generated,
                    "patches_tested": patches_tested,
                    "patches_deployed": 0,
                    "patches_failed": len(failed_patches),
                    "completed_at": datetime.now().isoformat()
                }
            
            # ===== 第四步：灰度发布 =====
            self._progress["stage"] = "deploying"
            logger.info("开始灰度发布")
            
            deployed_patches = []
            
            for item in tested_patches:
                patch = item["patch"]
                test_result = item["test_result"]
                
                try:
                    # 灰度发布
                    deploy_result = await workflow.execute_activity(
                        "deploy_patch_canary_activity",
                        {
                            "patch": patch,
                            "traffic_percentage": canary_traffic
                        },
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RULE_UPGRADE_RETRY_POLICY
                    )
                    
                    deployment_id = deploy_result.get("deployment_id")
                    
                    if deployment_id:
                        logger.info(f"补丁 {patch.get('patch_id')} 已灰度发布: {deployment_id}")
                        
                        # 如果启用自动全量发布
                        if auto_promote:
                            # 等待一段时间监控
                            await workflow.sleep(timedelta(minutes=30))
                            
                            # 检查是否有异常
                            monitor_result = await workflow.execute_activity(
                                "monitor_deployment_activity",
                                {"deployment_id": deployment_id},
                                start_to_close_timeout=timedelta(minutes=2),
                                retry_policy=RULE_UPGRADE_RETRY_POLICY
                            )
                            
                            if monitor_result.get("has_anomaly"):
                                logger.warning(f"检测到异常，回滚部署: {deployment_id}")
                                await workflow.execute_activity(
                                    "rollback_deployment_activity",
                                    {"deployment_id": deployment_id},
                                    start_to_close_timeout=timedelta(minutes=2),
                                    retry_policy=RULE_UPGRADE_RETRY_POLICY
                                )
                            else:
                                # 全量发布
                                logger.info(f"无异常，全量发布: {deployment_id}")
                                await workflow.execute_activity(
                                    "promote_deployment_activity",
                                    {"deployment_id": deployment_id},
                                    start_to_close_timeout=timedelta(minutes=2),
                                    retry_policy=RULE_UPGRADE_RETRY_POLICY
                                )
                        
                        deployed_patches.append(patch)
                        
                except Exception as e:
                    logger.error(f"部署补丁失败: {e}")
                    continue
            
            self._patches_deployed = len(deployed_patches)
            self._progress["patches_deployed"] = self._patches_deployed
            
            logger.info(f"灰度发布完成: 部署 {self._patches_deployed} 个补丁")
            
            # ===== 返回结果 =====
            self._progress["stage"] = "completed"
            
            final_result = {
                "upgrade_id": upgrade_id,
                "patterns_found": self._patterns_found,
                "patches_generated": self._patches_generated,
                "patches_tested": patches_tested,
                "patches_deployed": self._patches_deployed,
                "patches_failed": len(failed_patches),
                "completed_at": datetime.now().isoformat()
            }
            
            logger.info(
                f"规则升级完成: "
                f"upgrade_id={upgrade_id}, "
                f"部署={self._patches_deployed}, "
                f"失败={len(failed_patches)}"
            )
            
            return final_result
            
        except Exception as e:
            logger.error(
                f"规则升级工作流失败: "
                f"upgrade_id={upgrade_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            raise


@workflow.defn
class ScheduledRuleUpgradeWorkflow:
    """
    定时规则升级工作流
    
    定期触发规则升级流程（每日/每周）。
    """
    
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行定时规则升级
        
        Args:
            input_data: {
                "schedule": str,  # "daily" 或 "weekly"
                "config": Dict    # 规则升级配置
            }
            
        Returns:
            执行结果
        """
        schedule = input_data.get("schedule", "weekly")
        config = input_data.get("config", {})
        
        logger.info(f"启动定时规则升级: schedule={schedule}")
        
        # 根据调度类型设置等待时间
        if schedule == "daily":
            wait_duration = timedelta(days=1)
        elif schedule == "weekly":
            wait_duration = timedelta(weeks=1)
        else:
            wait_duration = timedelta(days=1)
        
        execution_count = 0
        
        while True:
            try:
                # 执行规则升级
                logger.info(f"开始第 {execution_count + 1} 次规则升级")
                
                result = await workflow.execute_child_workflow(
                    RuleUpgradeWorkflow,
                    config,
                    id=f"rule_upgrade_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    task_queue="default-queue"
                )
                
                logger.info(f"规则升级完成: {result}")
                execution_count += 1
                
                # 等待下一次执行
                await workflow.sleep(wait_duration)
                
            except Exception as e:
                logger.error(f"定时规则升级失败: {e}")
                # 等待一段时间后重试
                await workflow.sleep(timedelta(hours=1))
