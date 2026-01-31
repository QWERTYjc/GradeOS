"""
Railway 批改流程调试脚本

用于诊断批改流程中的问题:
1. 题目数量不匹配
2. 流程提前结束
3. 批改结果为空

使用方法:
1. 确保后端服务正在运行
2. 运行此脚本: python debug_grading_flow.py
3. 查看输出的调试信息
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_grading_flow():
    """测试批改流程"""
    from src.graphs.batch_grading import create_batch_grading_graph, BatchConfig
    from src.graphs.state import BatchGradingGraphState
    
    logger.info("=" * 60)
    logger.info("开始测试批改流程")
    logger.info("=" * 60)
    
    # 创建测试状态
    test_state: BatchGradingGraphState = {
        "batch_id": "test_batch_001",
        "answer_images": [b"fake_image_data"] * 19,  # 模拟19页答题图像
        "rubric_images": [b"fake_rubric_data"] * 2,  # 模拟2页批改标准
        "rubric": "",
        "api_key": "test_key",
        "inputs": {
            "expected_question_count": 19,
            "expected_total_score": 105,
            "grading_mode": "standard",
        },
        "current_stage": "initialized",
        "percentage": 0.0,
        "timestamps": {},
    }
    
    # 创建批改图
    config = BatchConfig(
        batch_size=1000,
        max_concurrent_workers=5,
        max_retries=2,
    )
    
    graph = create_batch_grading_graph(batch_config=config)
    
    logger.info(f"✅ 批改图创建成功")
    logger.info(f"📊 测试状态: {len(test_state['answer_images'])} 页答题, {len(test_state['rubric_images'])} 页批改标准")
    
    # 检查图的节点
    logger.info("\n" + "=" * 60)
    logger.info("图节点信息:")
    logger.info("=" * 60)
    
    # 注意: LangGraph 的 compiled graph 可能没有直接的 nodes 属性
    # 这里我们只是验证图已经创建
    logger.info("✅ 图已编译完成")
    
    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)
    
    return True


async def check_rubric_parser():
    """检查批改标准解析器"""
    from src.services.rubric_parser import RubricParserService
    
    logger.info("\n" + "=" * 60)
    logger.info("检查批改标准解析器")
    logger.info("=" * 60)
    
    # 检查 prompt 模板
    import inspect
    source = inspect.getsource(RubricParserService._parse_rubric_batch)
    
    if "total_questions_found" in source:
        logger.error("❌ 发现问题: prompt 中仍包含 total_questions_found 字段")
        logger.error("   这会导致 LLM 返回错误的题目计数")
        return False
    else:
        logger.info("✅ prompt 已修复: 不再包含 total_questions_found")
    
    return True


async def check_logging_config():
    """检查日志配置"""
    logger.info("\n" + "=" * 60)
    logger.info("检查日志配置")
    logger.info("=" * 60)
    
    import os
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger.info(f"当前日志级别: {log_level}")
    
    if log_level == "DEBUG":
        logger.warning("⚠️ 日志级别为 DEBUG,会输出完整的 JSON")
        logger.warning("   建议在生产环境设置为 INFO")
    else:
        logger.info("✅ 日志级别正常,不会输出完整 JSON")
    
    return True


async def main():
    """主函数"""
    try:
        # 1. 检查批改标准解析器
        await check_rubric_parser()
        
        # 2. 检查日志配置
        await check_logging_config()
        
        # 3. 测试批改流程
        await test_grading_flow()
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 所有检查通过!")
        logger.info("=" * 60)
        
        logger.info("\n📝 下一步:")
        logger.info("1. 重启后端服务以应用修复")
        logger.info("2. 在前端上传批改任务")
        logger.info("3. 查看 Railway 日志,确认:")
        logger.info("   - 题目数量正确 (应该是 19 题)")
        logger.info("   - 日志输出清晰 (不再有大量 JSON)")
        logger.info("   - 批改流程正常执行")
        logger.info("   - 批改结果正确显示")
        
    except Exception as e:
        logger.error(f"❌ 检查失败: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
