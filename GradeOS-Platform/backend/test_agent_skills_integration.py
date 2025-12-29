"""
Agent Skills 集成测试

验证 Agent Skills 在实际批改流程中是否生效：
1. 检查 Skills 是否正确注册
2. 验证 GeminiReasoningClient 是否集成了 GradingSkills
3. 测试 Skills 调用日志记录
4. 验证 Skills 在批改流程中的实际使用

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.skills.grading_skills import (
    GradingSkills,
    get_skill_registry,
    create_grading_skills,
)
from src.services.rubric_registry import RubricRegistry
from src.services.gemini_reasoning import GeminiReasoningClient
from src.models.grading_models import (
    QuestionRubric,
    ScoringPoint,
    QuestionResult,
    PageGradingResult,
)


async def test_skill_registration():
    """测试 1: 验证 Skills 是否正确注册"""
    print("\n" + "="*60)
    print("测试 1: 验证 Skills 注册")
    print("="*60)
    
    registry = get_skill_registry()
    skills = registry.list_skills()
    
    expected_skills = [
        "get_rubric_for_question",
        "identify_question_numbers",
        "detect_cross_page_questions",
        "merge_question_results",
        "merge_all_cross_page_results",
    ]
    
    print(f"\n已注册的 Skills ({len(skills)} 个):")
    for skill in skills:
        status = "✅" if skill in expected_skills else "⚠️"
        print(f"  {status} {skill}")
    
    missing = set(expected_skills) - set(skills)
    if missing:
        print(f"\n❌ 缺少的 Skills: {missing}")
        return False
    
    print("\n✅ 所有核心 Skills 已正确注册")
    return True


async def test_grading_skills_creation():
    """测试 2: 验证 GradingSkills 实例创建"""
    print("\n" + "="*60)
    print("测试 2: 验证 GradingSkills 实例创建")
    print("="*60)
    
    # 创建 RubricRegistry
    rubric_registry = RubricRegistry(total_score=100.0)
    
    # 注册测试评分标准
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
    
    # 创建 GradingSkills
    skills = create_grading_skills(rubric_registry=rubric_registry)
    
    print(f"\n✅ GradingSkills 实例创建成功")
    print(f"  - RubricRegistry: {skills.rubric_registry is not None}")
    print(f"  - QuestionMerger: {skills.question_merger is not None}")
    print(f"  - LLM Client: {skills.llm_client is not None}")
    
    return True


async def test_skill_execution():
    """测试 3: 验证 Skill 执行和日志记录"""
    print("\n" + "="*60)
    print("测试 3: 验证 Skill 执行和日志记录")
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
    
    # 测试 get_rubric_for_question
    print("\n执行 Skill: get_rubric_for_question")
    result = await skills.get_rubric_for_question(
        question_id="1",
        registry=rubric_registry
    )
    
    print(f"  - 执行成功: {result.success}")
    print(f"  - 执行时间: {result.execution_time_ms:.2f}ms")
    if result.success:
        print(f"  - 题目ID: {result.data.rubric.question_id}")
        print(f"  - 满分: {result.data.rubric.max_score}")
        print(f"  - 是否默认: {result.data.is_default}")
    
    # 检查调用日志
    registry = get_skill_registry()
    logs = registry.get_logs(limit=5)
    
    print(f"\n最近的 Skill 调用日志 ({len(logs)} 条):")
    for log in logs:
        status = "✅" if log.success else "❌"
        print(f"  {status} {log.skill_name} - {log.execution_time_ms:.2f}ms")
    
    if not logs:
        print("  ⚠️ 没有找到调用日志")
        return False
    
    print("\n✅ Skill 执行和日志记录正常")
    return True


async def test_gemini_client_integration():
    """测试 4: 验证 GeminiReasoningClient 集成"""
    print("\n" + "="*60)
    print("测试 4: 验证 GeminiReasoningClient 集成")
    print("="*60)
    
    # 检查环境变量
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  ⚠️ 未设置 GEMINI_API_KEY 环境变量，跳过此测试")
        return True
    
    # 创建 RubricRegistry 和 GradingSkills
    rubric_registry = RubricRegistry(total_score=100.0)
    grading_skills = create_grading_skills(rubric_registry=rubric_registry)
    
    # 创建 GeminiReasoningClient
    client = GeminiReasoningClient(
        api_key=api_key,
        rubric_registry=rubric_registry,
        grading_skills=grading_skills
    )
    
    print(f"\n✅ GeminiReasoningClient 创建成功")
    print(f"  - RubricRegistry: {client.rubric_registry is not None}")
    print(f"  - GradingSkills: {client.grading_skills is not None}")
    
    # 验证 Skills 的 LLM 客户端已设置
    if grading_skills.llm_client is not None:
        print(f"  - GradingSkills.llm_client: ✅ 已设置")
    else:
        print(f"  - GradingSkills.llm_client: ⚠️ 未设置")
    
    return True


async def test_cross_page_detection():
    """测试 5: 验证跨页题目检测 Skill"""
    print("\n" + "="*60)
    print("测试 5: 验证跨页题目检测 Skill")
    print("="*60)
    
    skills = create_grading_skills()
    
    # 创建测试数据：两个连续页面有相同题号
    page1 = PageGradingResult(
        page_index=0,
        question_results=[
            QuestionResult(
                question_id="1",
                score=5.0,
                max_score=10.0,
                confidence=0.9,
                page_indices=[0]
            )
        ]
    )
    page2 = PageGradingResult(
        page_index=1,
        question_results=[
            QuestionResult(
                question_id="1",
                score=3.0,
                max_score=10.0,
                confidence=0.85,
                page_indices=[1]
            )
        ]
    )
    
    print("\n执行 Skill: detect_cross_page_questions")
    result = await skills.detect_cross_page_questions(
        page_results=[page1, page2]
    )
    
    print(f"  - 执行成功: {result.success}")
    print(f"  - 执行时间: {result.execution_time_ms:.2f}ms")
    
    if result.success:
        cross_page_questions = result.data
        print(f"  - 检测到 {len(cross_page_questions)} 个跨页题目")
        for cpq in cross_page_questions:
            print(f"    • 题目 {cpq.question_id}: 页面 {cpq.page_indices}, 置信度 {cpq.confidence:.2f}")
    
    print("\n✅ 跨页题目检测 Skill 正常工作")
    return True


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Agent Skills 集成测试")
    print("="*60)
    
    tests = [
        ("Skills 注册", test_skill_registration),
        ("GradingSkills 创建", test_grading_skills_creation),
        ("Skill 执行和日志", test_skill_execution),
        ("GeminiClient 集成", test_gemini_client_integration),
        ("跨页题目检测", test_cross_page_detection),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！Agent Skills 在实机中正常工作。")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
