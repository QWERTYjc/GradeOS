"""
无数据库模式使用示例

演示如何在无数据库模式下使用 GradeOS 批改系统。

验证：需求 11.1, 11.3, 11.4, 11.8
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 设置为无数据库模式
os.environ["DATABASE_URL"] = ""
os.environ["GEMINI_API_KEY"] = "your-api-key-here"

from src.config.deployment_mode import get_deployment_mode
from src.services.rubric_registry import RubricRegistry, get_global_registry
from src.models.grading_models import QuestionRubric, ScoringPoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_check_deployment_mode():
    """示例 1：检查部署模式"""
    logger.info("=" * 60)
    logger.info("示例 1：检查部署模式")
    logger.info("=" * 60)
    
    config = get_deployment_mode()
    
    logger.info(f"部署模式: {config.mode.value}")
    logger.info(f"是否为无数据库模式: {config.is_no_database_mode}")
    logger.info(f"是否为数据库模式: {config.is_database_mode}")
    
    features = config.get_feature_availability()
    logger.info("功能可用性:")
    for feature, available in features.items():
        status = "✅" if available else "❌"
        logger.info(f"  {status} {feature}: {available}")


def example_2_use_rubric_registry():
    """示例 2：使用评分标准注册中心"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 2：使用评分标准注册中心（内存缓存）")
    logger.info("=" * 60)
    
    # 获取全局注册中心
    registry = get_global_registry()
    
    # 创建评分标准
    rubric1 = QuestionRubric(
        question_id="1",
        max_score=10.0,
        question_text="计算 2 + 2 的值",
        standard_answer="4",
        scoring_points=[
            ScoringPoint(description="计算过程", score=6.0, is_required=True),
            ScoringPoint(description="最终答案", score=4.0, is_required=True),
        ],
        alternative_solutions=[],
        grading_notes="注意计算步骤"
    )
    
    rubric2 = QuestionRubric(
        question_id="2",
        max_score=15.0,
        question_text="解释牛顿第一定律",
        standard_answer="物体在不受外力或受平衡力作用时，保持静止或匀速直线运动状态。",
        scoring_points=[
            ScoringPoint(description="概念理解", score=8.0, is_required=True),
            ScoringPoint(description="举例说明", score=7.0, is_required=False),
        ],
        alternative_solutions=[],
        grading_notes=""
    )
    
    # 注册评分标准
    registry.register_rubrics([rubric1, rubric2])
    logger.info(f"已注册 {registry.get_rubric_count()} 个评分标准")
    
    # 查询评分标准
    result = registry.get_rubric_for_question("1")
    logger.info(f"\n查询题目 1 的评分标准:")
    logger.info(f"  题目: {result.rubric.question_text}")
    logger.info(f"  满分: {result.rubric.max_score}")
    logger.info(f"  得分点数量: {len(result.rubric.scoring_points)}")
    logger.info(f"  是否默认规则: {result.is_default}")
    logger.info(f"  置信度: {result.confidence}")
    
    # 查询不存在的题目（返回默认规则）
    result = registry.get_rubric_for_question("999")
    logger.info(f"\n查询不存在的题目 999:")
    logger.info(f"  是否默认规则: {result.is_default}")
    logger.info(f"  置信度: {result.confidence}")
    logger.info(f"  消息: {result.message}")


def example_3_save_and_load_rubrics():
    """示例 3：保存和加载评分标准"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 3：保存和加载评分标准到文件")
    logger.info("=" * 60)
    
    # 获取注册中心
    registry = get_global_registry()
    
    # 保存到文件
    output_file = "rubrics_example.json"
    registry.save_to_file(output_file)
    logger.info(f"评分标准已保存到: {output_file}")
    
    # 从文件加载
    loaded_registry = RubricRegistry.load_from_file(output_file)
    logger.info(f"从文件加载了 {loaded_registry.get_rubric_count()} 个评分标准")
    
    # 验证数据一致性
    for qid in registry.get_question_ids():
        original = registry.get_rubric_for_question(qid)
        loaded = loaded_registry.get_rubric_for_question(qid)
        assert original.rubric.question_id == loaded.rubric.question_id
        assert original.rubric.max_score == loaded.rubric.max_score
    
    logger.info("✅ 数据一致性验证通过")
    
    # 清理
    Path(output_file).unlink()
    logger.info(f"已删除示例文件: {output_file}")


def example_4_parse_rubric_from_text():
    """示例 4：从文本解析评分标准"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 4：从文本解析评分标准")
    logger.info("=" * 60)
    
    rubric_text = """
    第1题（10分）：计算题
    计算 2 + 2 的值
    得分点：
    - 计算过程（6分）
    - 最终答案（4分）
    
    第2题（15分）：简答题
    解释牛顿第一定律
    得分点：
    - 概念理解（8分）
    - 举例说明（7分）
    
    第3题（20分）：综合题
    分析某个物理现象
    """
    
    registry = RubricRegistry()
    count = registry.parse_from_text(rubric_text)
    
    logger.info(f"从文本解析了 {count} 个评分标准")
    
    for qid in registry.get_question_ids():
        result = registry.get_rubric_for_question(qid)
        logger.info(f"\n题目 {qid}:")
        logger.info(f"  满分: {result.rubric.max_score}")
        logger.info(f"  得分点数量: {len(result.rubric.scoring_points)}")


async def example_5_database_degradation():
    """示例 5：数据库降级演示"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 5：数据库降级演示")
    logger.info("=" * 60)
    
    from src.utils.database import Database, DatabaseConfig
    
    # 使用无效的连接字符串
    config = DatabaseConfig()
    config._connection_string = "postgresql://invalid:invalid@invalid:9999/invalid"
    
    db = Database(config)
    
    logger.info("尝试连接到无效的数据库...")
    await db.connect(use_unified_pool=False)
    
    logger.info(f"数据库是否可用: {db.is_available}")
    logger.info(f"是否处于降级模式: {db.is_degraded}")
    
    if db.is_degraded:
        logger.info("✅ 数据库降级成功，系统继续运行")
    
    # 尝试获取连接（应该抛出异常）
    try:
        async with db.connection() as conn:
            pass
    except RuntimeError as e:
        logger.info(f"✅ 降级模式下正确抛出异常: {e}")


def main():
    """运行所有示例"""
    logger.info("\n" + "=" * 60)
    logger.info("GradeOS 无数据库模式使用示例")
    logger.info("=" * 60)
    
    # 示例 1：检查部署模式
    example_1_check_deployment_mode()
    
    # 示例 2：使用评分标准注册中心
    example_2_use_rubric_registry()
    
    # 示例 3：保存和加载评分标准
    example_3_save_and_load_rubrics()
    
    # 示例 4：从文本解析评分标准
    example_4_parse_rubric_from_text()
    
    # 示例 5：数据库降级演示（异步）
    asyncio.run(example_5_database_degradation())
    
    logger.info("\n" + "=" * 60)
    logger.info("所有示例运行完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
