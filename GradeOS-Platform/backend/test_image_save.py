"""测试图片保存功能

验证批改结果中的图片是否能正确保存到数据库
"""

import asyncio
import logging
from src.db.postgres_grading import get_page_images, get_grading_history

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_image_retrieval():
    """测试从数据库中检索图片"""
    
    # 1. 获取最新的批改历史
    from src.db.postgres_grading import list_grading_history
    
    histories = await list_grading_history(limit=1)
    if not histories:
        logger.error("❌ 没有找到批改历史记录")
        return
    
    latest_history = histories[0]
    logger.info(f"✅ 找到最新批改历史: {latest_history.batch_id}")
    logger.info(f"   - 创建时间: {latest_history.created_at}")
    logger.info(f"   - 学生数量: {latest_history.total_students}")
    
    # 2. 获取该批改历史的所有图片
    images = await get_page_images(latest_history.id)
    
    if not images:
        logger.error("❌ 没有找到保存的图片！")
        logger.info("   这说明图片保存功能仍然有问题")
        return
    
    logger.info(f"✅ 找到 {len(images)} 张保存的图片")
    
    # 3. 显示图片详情
    for img in images[:5]:  # 只显示前5张
        logger.info(f"   - 学生: {img.student_key}, 页码: {img.page_index}, "
                   f"格式: {img.image_format}, 大小: {len(img.image_data)} bytes")
    
    # 4. 验证图片数据完整性
    valid_images = [img for img in images if img.image_data and len(img.image_data) > 0]
    logger.info(f"✅ 有效图片数量: {len(valid_images)}/{len(images)}")
    
    if len(valid_images) == len(images):
        logger.info("🎉 所有图片数据完整！修复成功！")
    else:
        logger.warning(f"⚠️  有 {len(images) - len(valid_images)} 张图片数据为空")


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始测试图片保存功能")
    logger.info("=" * 60)
    
    try:
        await test_image_retrieval()
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
    
    logger.info("=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
