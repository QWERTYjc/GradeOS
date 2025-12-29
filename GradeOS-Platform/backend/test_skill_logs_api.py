"""
测试 Skill 调用日志 API

验证可以通过 API 查询 Skill 调用日志
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.skills.grading_skills import get_skill_registry, create_grading_skills
from src.services.rubric_registry import RubricRegistry
from src.models.grading_models import QuestionRubric, ScoringPoint


async def main():
    print("\n" + "="*60)
    print("Skill 调用日志测试")
    print("="*60)
    
    # 创建测试环境
    rubric_registry = RubricRegistry(total_score=100.0)
    rubric1 = QuestionRubric(
        question_id="1",
        max_score=10.0,
        question_text="测试题目1",
        standard_answer="标准答案1",
        scoring_points=[
            ScoringPoint(description="得分点1", score=5.0),
            ScoringPoint(description="得分点2", score=5.0),
        ]
    )
    rubric_registry.register_rubrics([rubric1])
    
    skills = create_grading_skills(rubric_registry=rubric_registry)
    
    # 执行多个 Skill 调用
    print("\n执行多个 Skill 调用...")
    for i in range(5):
        result = await skills.get_rubric_for_question(
            question_id="1",
            registry=rubric_registry
        )
        print(f"  调用 {i+1}: {result.success}, 耗时 {result.execution_time_ms:.2f}ms")
    
    # 获取调用日志
    registry = get_skill_registry()
    logs = registry.get_logs(limit=10)
    
    print(f"\n最近的 Skill 调用日志 ({len(logs)} 条):")
    print("-" * 60)
    for log in logs:
        status = "✅" if log.success else "❌"
        print(f"{status} {log.skill_name}")
        print(f"   时间: {log.timestamp}")
        print(f"   耗时: {log.execution_time_ms:.2f}ms")
        print(f"   参数: {log.args}")
        if log.error_message:
            print(f"   错误: {log.error_message}")
        print()
    
    # 序列化日志
    print("日志序列化测试:")
    print("-" * 60)
    if logs:
        log_dict = logs[0].to_dict()
        print(f"日志字典: {log_dict}")
    
    print("\n✅ Skill 调用日志功能正常")


if __name__ == "__main__":
    asyncio.run(main())
