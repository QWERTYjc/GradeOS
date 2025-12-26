"""规则升级定时任务

自动执行自我成长流程：
1. 从批改日志中获取改判样本
2. 分析失败模式（RuleMiner）
3. 生成候选补丁（PatchGenerator）
4. 运行回归测试（RegressionTester）
5. 灰度发布（PatchDeployer）

可通过 cron 或 APScheduler 设置定时执行。
"""

import logging
import asyncio
from typing import List, Optional

from src.services.grading_logger import get_grading_logger
from src.services.rule_miner import RuleMiner
from src.services.patch_generator import PatchGenerator
from src.services.regression_tester import RegressionTester
from src.services.patch_deployer import get_patch_deployer


logger = logging.getLogger(__name__)


async def run_rule_upgrade(
    min_samples: int = 100,
    days: int = 7,
    auto_deploy: bool = False
) -> dict:
    """
    执行一次规则升级流程
    
    Args:
        min_samples: 触发规则挖掘的最小改判样本数
        days: 改判样本的时间窗口（天）
        auto_deploy: 是否自动灰度发布通过测试的补丁
        
    Returns:
        升级结果，包含：
        - samples_count: 样本数量
        - patterns_found: 发现的失败模式数
        - patches_generated: 生成的补丁数
        - patches_passed: 通过回归测试的补丁数
        - patches_deployed: 已部署的补丁数
    """
    logger.info(f"开始规则升级流程: min_samples={min_samples}, days={days}")
    
    result = {
        "samples_count": 0,
        "patterns_found": 0,
        "patches_generated": 0,
        "patches_passed": 0,
        "patches_deployed": 0,
        "errors": []
    }
    
    try:
        # Step 1: 获取改判样本
        logger.info("Step 1: 获取改判样本...")
        grading_logger = get_grading_logger()
        override_samples = await grading_logger.get_override_samples(
            min_count=min_samples,
            days=days
        )
        result["samples_count"] = len(override_samples)
        
        if len(override_samples) < min_samples:
            logger.info(f"改判样本不足（{len(override_samples)} < {min_samples}），跳过升级")
            return result
        
        # Step 2: 分析失败模式
        logger.info("Step 2: 分析失败模式...")
        miner = RuleMiner()
        patterns = await miner.analyze_overrides(override_samples)
        result["patterns_found"] = len(patterns)
        
        if not patterns:
            logger.info("未发现可修复的失败模式")
            return result
        
        # Step 3: 生成候选补丁
        logger.info(f"Step 3: 为 {len(patterns)} 个模式生成补丁...")
        generator = PatchGenerator()
        patches = []
        for pattern in patterns:
            try:
                patch = await generator.generate_patch(pattern)
                if patch:
                    patches.append(patch)
            except Exception as e:
                logger.warning(f"补丁生成失败: {e}")
                result["errors"].append(f"补丁生成: {e}")
        
        result["patches_generated"] = len(patches)
        
        if not patches:
            logger.info("未生成任何补丁")
            return result
        
        # Step 4: 运行回归测试
        logger.info(f"Step 4: 对 {len(patches)} 个补丁运行回归测试...")
        tester = RegressionTester()
        passed_patches = []
        for patch in patches:
            try:
                test_result = await tester.run_regression(patch)
                if test_result.passed:
                    passed_patches.append(patch)
                    logger.info(f"补丁 {patch.patch_id} 通过回归测试")
                else:
                    logger.info(f"补丁 {patch.patch_id} 未通过回归测试")
            except Exception as e:
                logger.warning(f"回归测试失败: {e}")
                result["errors"].append(f"回归测试: {e}")
        
        result["patches_passed"] = len(passed_patches)
        
        if not passed_patches:
            logger.info("没有补丁通过回归测试")
            return result
        
        # Step 5: 灰度发布
        if auto_deploy:
            logger.info(f"Step 5: 灰度发布 {len(passed_patches)} 个补丁...")
            deployer = get_patch_deployer()
            for patch in passed_patches:
                try:
                    deployment_id = await deployer.deploy_canary(patch)
                    result["patches_deployed"] += 1
                    logger.info(f"补丁 {patch.patch_id} 已灰度发布: {deployment_id}")
                except Exception as e:
                    logger.warning(f"灰度发布失败: {e}")
                    result["errors"].append(f"灰度发布: {e}")
        else:
            logger.info("自动部署已禁用，跳过灰度发布")
        
        logger.info(f"规则升级完成: {result}")
        return result
        
    except Exception as e:
        logger.error(f"规则升级流程失败: {e}", exc_info=True)
        result["errors"].append(str(e))
        return result


async def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="运行规则升级任务")
    parser.add_argument("--min-samples", type=int, default=100, help="最小改判样本数")
    parser.add_argument("--days", type=int, default=7, help="时间窗口（天）")
    parser.add_argument("--auto-deploy", action="store_true", help="自动灰度发布")
    
    args = parser.parse_args()
    
    result = await run_rule_upgrade(
        min_samples=args.min_samples,
        days=args.days,
        auto_deploy=args.auto_deploy
    )
    
    print(f"升级结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())
