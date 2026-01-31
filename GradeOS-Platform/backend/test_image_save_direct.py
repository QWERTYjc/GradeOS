"""直接测试图片保存功能

不依赖完整的批改流程，直接测试图片保存到数据库
"""

import asyncio
import logging
import uuid
from datetime import datetime
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_direct_image_save():
    """直接测试图片保存"""
    
    from src.db.postgres_grading import (
        GradingHistory,
        GradingPageImage,
        save_grading_history,
        save_page_image,
        get_page_images,
    )
    
    # 1. 创建测试批改历史
    history_id = str(uuid.uuid4())
    batch_id = f"test-{uuid.uuid4()}"
    
    history = GradingHistory(
        id=history_id,
        batch_id=batch_id,
        status="completed",
        created_at=datetime.now().isoformat(),
        completed_at=datetime.now().isoformat(),
        total_students=1,
        average_score=85.0,
        result_data={"test": True},
    )
    
    logger.info(f"📝 创建测试批改历史: {batch_id}")
    await save_grading_history(history)
    logger.info("✅ 批改历史保存成功")
    
    # 2. 创建测试图片（100x100 红色方块）
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    image_data = img_bytes.getvalue()
    
    logger.info(f"🖼️  创建测试图片: {len(image_data)} bytes")
    
    # 3. 保存图片到数据库
    page_image = GradingPageImage(
        id=str(uuid.uuid4()),
        grading_history_id=history_id,
        student_key="测试学生",
        page_index=0,
        image_data=image_data,
        image_format="png",
        created_at=datetime.now().isoformat(),
    )
    
    logger.info("💾 保存图片到数据库...")
    await save_page_image(page_image)
    logger.info("✅ 图片保存成功")
    
    # 4. 验证图片是否保存成功
    logger.info("🔍 验证图片...")
    images = await get_page_images(history_id)
    
    if not images:
        logger.error("❌ 验证失败：没有找到保存的图片")
        return False
    
    if len(images) != 1:
        logger.error(f"❌ 验证失败：期望 1 张图片，实际 {len(images)} 张")
        return False
    
    saved_image = images[0]
    if len(saved_image.image_data) != len(image_data):
        logger.error(f"❌ 验证失败：图片大小不匹配")
        logger.error(f"   期望: {len(image_data)} bytes")
        logger.error(f"   实际: {len(saved_image.image_data)} bytes")
        return False
    
    logger.info("✅ 验证成功：图片数据完整")
    logger.info(f"   - 学生: {saved_image.student_key}")
    logger.info(f"   - 页码: {saved_image.page_index}")
    logger.info(f"   - 格式: {saved_image.image_format}")
    logger.info(f"   - 大小: {len(saved_image.image_data)} bytes")
    
    return True


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("直接测试图片保存功能")
    logger.info("=" * 60)
    logger.info("")
    
    try:
        success = await test_direct_image_save()
        
        logger.info("")
        logger.info("=" * 60)
        if success:
            logger.info("🎉 测试通过！图片保存功能正常工作")
            logger.info("")
            logger.info("这说明：")
            logger.info("  1. ✅ 数据库连接正常")
            logger.info("  2. ✅ 表结构正确")
            logger.info("  3. ✅ 图片保存逻辑正常")
            logger.info("")
            logger.info("如果批改任务仍然没有图片，问题可能在于：")
            logger.info("  - 后端服务没有重启（修复未生效）")
            logger.info("  - page_results 中仍然没有 image 字段")
        else:
            logger.error("❌ 测试失败！请检查错误信息")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
