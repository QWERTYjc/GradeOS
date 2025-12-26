"""简化的缓存测试 - 只测试缓存创建和管理功能"""

import asyncio
from pathlib import Path
from typing import List

import fitz
from PIL import Image
from io import BytesIO

from src.services.rubric_parser import RubricParserService, ParsedRubric, QuestionRubric, ScoringPoint
from src.services.cached_grading import CachedGradingService


API_KEY = "AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE"


def create_mock_rubric() -> ParsedRubric:
    """创建模拟的评分标准（足够大以满足缓存要求）"""
    questions = []
    for i in range(1, 20):  # 创建 19 道题（真实场景）
        # 每道题有多个得分点
        scoring_points = [
            ScoringPoint(
                description=f"第{i}题得分点1：正确理解题意，能够准确识别问题的关键信息和要求",
                score=1.0,
                is_required=True
            ),
            ScoringPoint(
                description=f"第{i}题得分点2：运用正确的方法和公式进行计算或推理",
                score=2.0,
                is_required=True
            ),
            ScoringPoint(
                description=f"第{i}题得分点3：计算过程完整，步骤清晰，逻辑严密",
                score=1.0,
                is_required=True
            ),
            ScoringPoint(
                description=f"第{i}题得分点4：最终答案正确，单位标注准确",
                score=1.0,
                is_required=True
            )
        ]
        
        questions.append(
            QuestionRubric(
                question_id=str(i),
                max_score=5.0,
                question_text=f"这是第{i}题的题目内容，要求学生根据给定条件进行分析和计算",
                standard_answer=f"第{i}题的标准答案：首先分析题意，然后列出相关公式，代入数值计算，最后得出结论",
                scoring_points=scoring_points,
                alternative_solutions=[],
                grading_notes=f"批改第{i}题时需要注意：检查学生是否理解题意，计算过程是否完整，答案是否准确"
            )
        )
    
    return ParsedRubric(
        total_questions=19,
        total_score=95.0,
        questions=questions,
        general_notes="本次考试共19道题，总分95分。批改时请严格按照评分标准，逐个得分点评分。",
        rubric_format="standard"
    )


def create_mock_rubric_context(rubric: ParsedRubric) -> str:
    """创建模拟的评分标准上下文"""
    context = f"# 评分标准\n\n总分: {rubric.total_score}分，共 {rubric.total_questions} 题\n\n"
    
    for q in rubric.questions:
        context += f"## 第 {q.question_id} 题 ({q.max_score}分)\n\n"
        for sp in q.scoring_points:
            required = "必须" if sp.is_required else "可选"
            context += f"- [{sp.score}分/{required}] {sp.description}\n"
        context += "\n"
    
    return context


async def test_cache_creation():
    """测试缓存创建"""
    print("\n" + "=" * 70)
    print("测试 1: 缓存创建")
    print("=" * 70)
    
    # 创建模拟数据
    rubric = create_mock_rubric()
    rubric_context = create_mock_rubric_context(rubric)
    
    print(f"\n📋 评分标准:")
    print(f"   题目数: {rubric.total_questions}")
    print(f"   总分: {rubric.total_score}")
    print(f"   上下文长度: {len(rubric_context)} 字符")
    
    # 创建缓存服务
    print("\n💾 创建缓存服务...")
    service = CachedGradingService(api_key=API_KEY, cache_ttl_hours=1)
    
    # 创建缓存
    print("   正在创建评分标准缓存...")
    try:
        await service.create_rubric_cache(rubric, rubric_context)
        print("   ✅ 缓存创建成功！")
        
        # 获取缓存信息
        cache_info = service.get_cache_info()
        print(f"\n📊 缓存信息:")
        print(f"   状态: {cache_info['status']}")
        print(f"   缓存名称: {cache_info['cache_name']}")
        print(f"   有效期: {cache_info['ttl_hours']} 小时")
        print(f"   剩余时间: {cache_info['remaining_hours']:.2f} 小时")
        print(f"   题目数: {cache_info['total_questions']}")
        
        # 删除缓存
        print("\n🗑️  删除缓存...")
        service.delete_cache()
        print("   ✅ 缓存已删除")
        
        # 验证缓存已删除
        cache_info = service.get_cache_info()
        print(f"\n📊 删除后状态: {cache_info['status']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 缓存创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_cache_validation():
    """测试缓存验证"""
    print("\n" + "=" * 70)
    print("测试 2: 缓存验证")
    print("=" * 70)
    
    rubric = create_mock_rubric()
    rubric_context = create_mock_rubric_context(rubric)
    
    service = CachedGradingService(api_key=API_KEY, cache_ttl_hours=1)
    
    # 测试未创建缓存时的验证
    print("\n🔍 测试 1: 未创建缓存")
    is_valid = service._is_cache_valid()
    print(f"   缓存有效: {is_valid}")
    assert not is_valid, "未创建缓存时应该返回 False"
    print("   ✅ 通过")
    
    # 创建缓存
    print("\n🔍 测试 2: 创建缓存后")
    await service.create_rubric_cache(rubric, rubric_context)
    is_valid = service._is_cache_valid()
    print(f"   缓存有效: {is_valid}")
    assert is_valid, "创建缓存后应该返回 True"
    print("   ✅ 通过")
    
    # 删除缓存
    print("\n🔍 测试 3: 删除缓存后")
    service.delete_cache()
    is_valid = service._is_cache_valid()
    print(f"   缓存有效: {is_valid}")
    assert not is_valid, "删除缓存后应该返回 False"
    print("   ✅ 通过")
    
    return True


async def test_cache_info():
    """测试缓存信息获取"""
    print("\n" + "=" * 70)
    print("测试 3: 缓存信息获取")
    print("=" * 70)
    
    rubric = create_mock_rubric()
    rubric_context = create_mock_rubric_context(rubric)
    
    service = CachedGradingService(api_key=API_KEY, cache_ttl_hours=2)
    
    # 未创建缓存时
    print("\n📊 未创建缓存时:")
    info = service.get_cache_info()
    print(f"   状态: {info['status']}")
    assert info['status'] == 'no_cache', "应该返回 no_cache"
    print("   ✅ 通过")
    
    # 创建缓存后
    print("\n📊 创建缓存后:")
    await service.create_rubric_cache(rubric, rubric_context)
    info = service.get_cache_info()
    print(f"   状态: {info['status']}")
    print(f"   缓存名称: {info['cache_name']}")
    print(f"   有效期: {info['ttl_hours']} 小时")
    print(f"   剩余时间: {info['remaining_hours']:.2f} 小时")
    print(f"   题目数: {info['total_questions']}")
    
    assert info['status'] == 'active', "应该返回 active"
    assert info['ttl_hours'] == 2, "有效期应该是 2 小时"
    assert info['total_questions'] == 19, "题目数应该是 19"
    print("   ✅ 通过")
    
    # 清理
    service.delete_cache()
    
    return True


async def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("缓存功能测试套件")
    print("=" * 70)
    
    results = []
    
    # 测试 1: 缓存创建
    try:
        result = await test_cache_creation()
        results.append(("缓存创建", result))
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        results.append(("缓存创建", False))
    
    # 测试 2: 缓存验证
    try:
        result = await test_cache_validation()
        results.append(("缓存验证", result))
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        results.append(("缓存验证", False))
    
    # 测试 3: 缓存信息
    try:
        result = await test_cache_info()
        results.append(("缓存信息", result))
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        results.append(("缓存信息", False))
    
    # 输出结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
