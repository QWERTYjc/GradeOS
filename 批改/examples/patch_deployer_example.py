"""补丁部署器使用示例

演示如何使用 PatchDeployer 进行规则补丁的灰度发布、监控和回滚。
"""

import asyncio
import logging
from datetime import datetime

from src.services.patch_deployer import get_patch_deployer
from src.services.regression_tester import get_regression_tester
from src.models.rule_patch import RulePatch, PatchType


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_safe_deployment():
    """示例：安全地部署补丁"""
    logger.info("=" * 80)
    logger.info("示例 1：安全地部署补丁")
    logger.info("=" * 80)
    
    # 创建一个示例补丁
    patch = RulePatch(
        patch_id="patch_example_001",
        patch_type=PatchType.RULE,
        version="v1.0.1",
        description="添加单位换算规则：cm -> m",
        content={
            "rule_type": "unit_conversion",
            "from_unit": "cm",
            "to_unit": "m",
            "conversion_factor": 0.01
        },
        source_pattern_id="pattern_001"
    )
    
    deployer = get_patch_deployer()
    tester = get_regression_tester()
    
    # 步骤 1：运行回归测试
    logger.info("\n步骤 1：运行回归测试...")
    result = await tester.run_regression(patch, eval_set_id="eval_001")
    
    logger.info(f"回归测试结果：{'通过' if result.passed else '未通过'}")
    logger.info(f"  误判率：{result.old_error_rate:.2%} -> {result.new_error_rate:.2%}")
    logger.info(f"  漏判率：{result.old_miss_rate:.2%} -> {result.new_miss_rate:.2%}")
    logger.info(f"  复核率：{result.old_review_rate:.2%} -> {result.new_review_rate:.2%}")
    
    if not result.passed:
        logger.warning("回归测试未通过，取消部署")
        return False
    
    # 步骤 2：灰度发布
    logger.info("\n步骤 2：开始灰度发布（10% 流量）...")
    deployment_id = await deployer.deploy_canary(
        patch=patch,
        traffic_percentage=0.1
    )
    logger.info(f"灰度发布成功，部署ID：{deployment_id}")
    
    # 步骤 3：监控灰度发布
    logger.info("\n步骤 3：监控灰度发布（模拟30分钟）...")
    
    # 模拟监控6次（每5分钟一次）
    for i in range(6):
        logger.info(f"\n第 {i+1} 次监控（{(i+1)*5} 分钟）...")
        
        # 实际使用时应该等待5分钟
        # await asyncio.sleep(300)
        
        monitor_result = await deployer.monitor_deployment(deployment_id)
        
        logger.info(f"  状态：{monitor_result['status']}")
        logger.info(f"  异常数：{len(monitor_result.get('anomalies', []))}")
        
        if monitor_result.get('anomalies'):
            for anomaly in monitor_result['anomalies']:
                logger.warning(f"  - {anomaly['type']}: {anomaly['message']}")
        
        if monitor_result['status'] == 'critical':
            logger.error("检测到严重异常，已自动回滚")
            return False
        
        if monitor_result['status'] == 'warning':
            logger.warning("检测到警告，继续监控...")
    
    # 步骤 4：全量发布
    logger.info("\n步骤 4：灰度发布正常，开始全量发布...")
    success = await deployer.promote_to_full(deployment_id)
    
    if success:
        logger.info("✓ 部署成功！")
    else:
        logger.error("✗ 全量发布失败")
    
    return success


async def example_manual_rollback():
    """示例：手动回滚部署"""
    logger.info("\n" + "=" * 80)
    logger.info("示例 2：手动回滚部署")
    logger.info("=" * 80)
    
    # 创建一个示例补丁
    patch = RulePatch(
        patch_id="patch_example_002",
        patch_type=PatchType.PROMPT,
        version="v1.0.2",
        description="优化提取提示词",
        content={
            "patch_target": "extraction_prompt",
            "enhancement": "增强答案区域识别能力"
        },
        source_pattern_id="pattern_002"
    )
    
    deployer = get_patch_deployer()
    
    # 灰度发布
    logger.info("\n灰度发布补丁...")
    deployment_id = await deployer.deploy_canary(patch, traffic_percentage=0.1)
    logger.info(f"部署ID：{deployment_id}")
    
    # 模拟发现问题，需要手动回滚
    logger.info("\n发现问题，执行手动回滚...")
    success = await deployer.rollback(deployment_id)
    
    if success:
        logger.info("✓ 回滚成功")
    else:
        logger.error("✗ 回滚失败")
    
    return success


async def example_anomaly_detection():
    """示例：异常检测"""
    logger.info("\n" + "=" * 80)
    logger.info("示例 3：异常检测")
    logger.info("=" * 80)
    
    deployer = get_patch_deployer()
    
    # 场景 1：误判率增加
    logger.info("\n场景 1：误判率增加超过阈值")
    baseline = {
        "error_rate": 0.10,
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    current = {
        "error_rate": 0.25,  # 增加15%
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    
    anomalies = deployer._detect_anomalies(baseline, current)
    logger.info(f"检测到 {len(anomalies)} 个异常：")
    for anomaly in anomalies:
        logger.info(f"  - [{anomaly['severity']}] {anomaly['type']}: {anomaly['message']}")
    
    # 场景 2：指标正常
    logger.info("\n场景 2：指标正常")
    baseline = {
        "error_rate": 0.10,
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    current = {
        "error_rate": 0.12,  # 仅增加2%
        "miss_rate": 0.06,
        "review_rate": 0.16
    }
    
    anomalies = deployer._detect_anomalies(baseline, current)
    if anomalies:
        logger.info(f"检测到 {len(anomalies)} 个异常")
    else:
        logger.info("✓ 未检测到异常，指标正常")
    
    # 场景 3：指标改善
    logger.info("\n场景 3：指标改善")
    baseline = {
        "error_rate": 0.15,
        "miss_rate": 0.10,
        "review_rate": 0.20
    }
    current = {
        "error_rate": 0.08,  # 下降7%
        "miss_rate": 0.05,   # 下降5%
        "review_rate": 0.12  # 下降8%
    }
    
    anomalies = deployer._detect_anomalies(baseline, current)
    if anomalies:
        logger.info(f"检测到 {len(anomalies)} 个异常")
    else:
        logger.info("✓ 未检测到异常，指标改善")


async def example_deployment_lifecycle():
    """示例：完整的部署生命周期"""
    logger.info("\n" + "=" * 80)
    logger.info("示例 4：完整的部署生命周期")
    logger.info("=" * 80)
    
    # 创建补丁
    patch = RulePatch(
        patch_id="patch_example_003",
        patch_type=PatchType.RULE,
        version="v1.0.3",
        description="扩展同义词规则",
        content={
            "rule_type": "synonym_expansion",
            "synonyms": ["正确", "对", "是", "√"]
        },
        source_pattern_id="pattern_003"
    )
    
    deployer = get_patch_deployer()
    
    # 1. 灰度发布
    logger.info("\n1. 灰度发布（10% 流量）")
    deployment_id = await deployer.deploy_canary(patch, traffic_percentage=0.1)
    logger.info(f"   部署ID：{deployment_id}")
    
    # 2. 第一次监控
    logger.info("\n2. 第一次监控（5分钟后）")
    result = await deployer.monitor_deployment(deployment_id)
    logger.info(f"   状态：{result['status']}")
    
    # 3. 第二次监控
    logger.info("\n3. 第二次监控（10分钟后）")
    result = await deployer.monitor_deployment(deployment_id)
    logger.info(f"   状态：{result['status']}")
    
    # 4. 全量发布
    if result['status'] in ['healthy', 'warning']:
        logger.info("\n4. 全量发布（100% 流量）")
        success = await deployer.promote_to_full(deployment_id)
        logger.info(f"   {'✓ 成功' if success else '✗ 失败'}")
    else:
        logger.warning("\n4. 状态异常，取消全量发布")


async def main():
    """运行所有示例"""
    try:
        # 示例 1：安全部署
        await example_safe_deployment()
        
        # 示例 2：手动回滚
        await example_manual_rollback()
        
        # 示例 3：异常检测
        await example_anomaly_detection()
        
        # 示例 4：完整生命周期
        await example_deployment_lifecycle()
        
        logger.info("\n" + "=" * 80)
        logger.info("所有示例运行完成")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"运行示例时出错：{e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
