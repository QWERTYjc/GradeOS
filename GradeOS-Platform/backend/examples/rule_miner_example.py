"""规则挖掘器使用示例

演示如何使用 RuleMiner 从改判样本中识别失败模式。
"""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from src.services.rule_miner import get_rule_miner
from src.services.grading_logger import get_grading_logger
from src.models.grading_log import GradingLog


async def main():
    """规则挖掘器使用示例"""
    
    print("=" * 80)
    print("规则挖掘器使用示例")
    print("=" * 80)
    
    # 1. 获取批改日志服务和规则挖掘器
    grading_logger = get_grading_logger()
    rule_miner = get_rule_miner()
    
    print("\n1. 模拟创建一些改判样本...")
    
    # 创建一些模拟的改判样本
    override_logs = []
    
    # 提取失败样本（高频）
    for i in range(15):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q1_math",
            extracted_answer="",  # 空答案
            extraction_confidence=0.3,
            evidence_snippets=[],
            score=0.0,
            max_score=10.0,
            confidence=0.5,
            reasoning_trace=["无法提取答案"],
            was_overridden=True,
            override_score=8.0,
            override_reason="答案提取失败，实际答案为 x=5",
            override_teacher_id="teacher_001",
            override_at=datetime.utcnow(),
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        override_logs.append(log)
    
    # 规范化失败样本（中频）
    for i in range(8):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q2_physics",
            extracted_answer="100cm",
            extraction_confidence=0.9,
            normalized_answer="100cm",
            normalization_rules_applied=["unit_conversion"],
            match_result=False,
            match_failure_reason="单位不匹配",
            score=0.0,
            max_score=10.0,
            confidence=0.8,
            reasoning_trace=["单位换算失败"],
            was_overridden=True,
            override_score=10.0,
            override_reason="应该识别 100cm = 1m",
            override_teacher_id="teacher_001",
            override_at=datetime.utcnow(),
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        override_logs.append(log)
    
    # 匹配失败样本（中频）
    for i in range(6):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q3_chinese",
            extracted_answer="正确",
            extraction_confidence=0.95,
            normalized_answer="正确",
            match_result=False,
            match_failure_reason="同义词未识别",
            score=0.0,
            max_score=5.0,
            confidence=0.7,
            reasoning_trace=["匹配失败"],
            was_overridden=True,
            override_score=5.0,
            override_reason="'正确' 应该识别为 '对' 的同义词",
            override_teacher_id="teacher_002",
            override_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        override_logs.append(log)
    
    # 评分偏差样本（低频）
    for i in range(3):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id="q4_essay",
            extracted_answer="这是一篇作文...",
            extraction_confidence=0.95,
            normalized_answer="这是一篇作文...",
            match_result=True,
            score=7.0,
            max_score=10.0,
            confidence=0.85,
            reasoning_trace=["评分完成"],
            was_overridden=True,
            override_score=9.0,
            override_reason="评分偏严格",
            override_teacher_id="teacher_003",
            override_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        override_logs.append(log)
    
    print(f"   创建了 {len(override_logs)} 条改判样本")
    
    # 2. 执行规则挖掘
    print("\n2. 执行规则挖掘...")
    patterns = await rule_miner.analyze_overrides(override_logs)
    
    print(f"   识别出 {len(patterns)} 个失败模式")
    
    # 3. 显示识别出的失败模式
    print("\n3. 失败模式详情：")
    print("-" * 80)
    
    for i, pattern in enumerate(patterns, 1):
        print(f"\n模式 {i}:")
        print(f"  ID: {pattern.pattern_id}")
        print(f"  类型: {pattern.pattern_type.value}")
        print(f"  描述: {pattern.description}")
        print(f"  频率: {pattern.frequency} 次")
        print(f"  置信度: {pattern.confidence:.2f}")
        print(f"  可修复: {'是' if pattern.is_fixable else '否'}")
        
        if pattern.error_signature:
            print(f"  错误特征: {pattern.error_signature}")
        
        if pattern.affected_question_types:
            print(f"  受影响题型: {', '.join(pattern.affected_question_types)}")
        
        if pattern.suggested_fix:
            print(f"  建议修复: {pattern.suggested_fix}")
        
        print(f"  样本日志: {len(pattern.sample_log_ids)} 条")
    
    # 4. 判断哪些模式可以修复
    print("\n4. 可修复模式分析：")
    print("-" * 80)
    
    fixable_patterns = [p for p in patterns if rule_miner.is_pattern_fixable(p)]
    print(f"\n可修复模式数量: {len(fixable_patterns)}/{len(patterns)}")
    
    for pattern in fixable_patterns:
        print(f"\n✓ {pattern.description}")
        print(f"  类型: {pattern.pattern_type.value}")
        print(f"  频率: {pattern.frequency}")
        if pattern.suggested_fix:
            print(f"  建议: {pattern.suggested_fix}")
    
    # 5. 生成汇总报告
    print("\n5. 生成汇总报告：")
    print("-" * 80)
    
    summary = rule_miner.generate_summary(override_logs, patterns)
    
    print(f"\n总改判数量: {summary.total_overrides}")
    print(f"识别模式数量: {summary.total_patterns}")
    print(f"可修复模式数量: {summary.fixable_patterns}")
    print(f"分析时间: {summary.analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 6. 按类型统计
    print("\n6. 按类型统计：")
    print("-" * 80)
    
    from collections import Counter
    type_counts = Counter(p.pattern_type for p in patterns)
    
    for pattern_type, count in type_counts.most_common():
        print(f"  {pattern_type.value}: {count} 个模式")
    
    print("\n" + "=" * 80)
    print("示例完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
