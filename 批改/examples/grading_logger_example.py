"""批改日志服务使用示例

演示如何使用 GradingLogger 记录批改日志、改判信息和查询改判样本。
"""

import asyncio
from datetime import datetime
from uuid import uuid4

from src.models.grading_log import GradingLog
from src.services.grading_logger import get_grading_logger


async def example_log_grading():
    """示例：记录批改日志"""
    print("=" * 60)
    print("示例 1: 记录批改日志")
    print("=" * 60)
    
    logger = get_grading_logger()
    
    # 创建批改日志
    log = GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id="q1",
        
        # 提取阶段
        extracted_answer="x = 5",
        extraction_confidence=0.95,
        evidence_snippets=["在第3行找到答案", "计算过程清晰"],
        
        # 规范化阶段
        normalized_answer="x=5",
        normalization_rules_applied=["remove_spaces", "lowercase"],
        
        # 匹配阶段
        match_result=True,
        match_failure_reason=None,
        
        # 评分阶段
        score=8.5,
        max_score=10.0,
        confidence=0.92,
        reasoning_trace=[
            "步骤1：识别公式",
            "步骤2：验证计算",
            "步骤3：检查单位"
        ],
        
        created_at=datetime.now()
    )
    
    # 记录日志（注意：这会尝试写入数据库，如果失败会暂存到本地）
    try:
        log_id = await logger.log_grading(log)
        print(f"✓ 批改日志已记录: {log_id}")
        print(f"  - 提取答案: {log.extracted_answer}")
        print(f"  - 提取置信度: {log.extraction_confidence}")
        print(f"  - 评分: {log.score}/{log.max_score}")
        print(f"  - 评分置信度: {log.confidence}")
    except Exception as e:
        print(f"✗ 记录失败（已暂存到本地）: {e}")
        print(f"  - 暂存队列大小: {logger.get_pending_count()}")


async def example_log_override():
    """示例：记录改判信息"""
    print("\n" + "=" * 60)
    print("示例 2: 记录改判信息")
    print("=" * 60)
    
    logger = get_grading_logger()
    
    # 假设这是一个已存在的日志 ID
    log_id = str(uuid4())
    
    # 记录改判
    try:
        success = await logger.log_override(
            log_id=log_id,
            override_score=9.0,
            override_reason="学生答案实际上是正确的，只是表达方式不同",
            teacher_id=str(uuid4())
        )
        
        if success:
            print(f"✓ 改判日志已记录: {log_id}")
            print(f"  - 改判分数: 9.0")
            print(f"  - 改判原因: 学生答案实际上是正确的")
        else:
            print(f"✗ 未找到日志记录: {log_id}")
    except Exception as e:
        print(f"✗ 记录改判失败: {e}")


async def example_get_override_samples():
    """示例：查询改判样本"""
    print("\n" + "=" * 60)
    print("示例 3: 查询改判样本")
    print("=" * 60)
    
    logger = get_grading_logger()
    
    # 查询最近 7 天内的 100 条改判样本
    try:
        samples = await logger.get_override_samples(
            min_count=100,
            days=7
        )
        
        print(f"✓ 查询到 {len(samples)} 条改判样本")
        
        if samples:
            print("\n前 3 条样本:")
            for i, sample in enumerate(samples[:3], 1):
                print(f"\n  样本 {i}:")
                print(f"    - 题目ID: {sample.question_id}")
                print(f"    - 原始分数: {sample.score}")
                print(f"    - 改判分数: {sample.override_score}")
                print(f"    - 改判原因: {sample.override_reason}")
                print(f"    - 改判时间: {sample.override_at}")
    except Exception as e:
        print(f"✗ 查询改判样本失败: {e}")


async def example_fault_tolerance():
    """示例：日志写入容错"""
    print("\n" + "=" * 60)
    print("示例 4: 日志写入容错")
    print("=" * 60)
    
    logger = get_grading_logger()
    
    # 模拟多个日志写入失败（实际场景中是数据库连接失败）
    print("模拟 5 条日志写入失败...")
    for i in range(5):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id=f"q{i}",
            extracted_answer=f"answer_{i}",
            extraction_confidence=0.9,
            score=8.0,
            confidence=0.85,
            reasoning_trace=["step1"],
            created_at=datetime.now()
        )
        # 直接添加到暂存队列（模拟写入失败）
        logger._pending_logs.append(log)
    
    print(f"✓ 暂存队列大小: {logger.get_pending_count()}")
    
    # 尝试刷新暂存日志
    print("\n尝试刷新暂存日志...")
    try:
        success_count = await logger.flush_pending()
        print(f"✓ 成功写入 {success_count} 条日志")
        print(f"  - 剩余暂存: {logger.get_pending_count()}")
    except Exception as e:
        print(f"✗ 刷新失败: {e}")


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("批改日志服务使用示例")
    print("=" * 60)
    
    await example_log_grading()
    await example_log_override()
    await example_get_override_samples()
    await example_fault_tolerance()
    
    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
