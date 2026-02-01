"""
诊断批次数据问题
检查批次 1dc62437-ecee-4203-bd59-d38b7882e91a 的数据库状态
"""
import asyncio
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../GradeOS-Platform/backend"))

from src.db.postgres_grading import (
    get_grading_history,
    get_student_results,
    get_page_images,
)


async def diagnose_batch(batch_id: str):
    """诊断批次数据"""
    print(f"\n{'='*60}")
    print(f"诊断批次: {batch_id}")
    print(f"{'='*60}\n")
    
    # 1. 检查批改历史
    print("📋 1. 检查批改历史记录...")
    try:
        history = await get_grading_history(batch_id)
        if history:
            print(f"   ✅ 找到批改历史")
            print(f"   - ID: {history.id}")
            print(f"   - 状态: {history.status}")
            print(f"   - 教师ID: {history.teacher_id}")
            print(f"   - 创建时间: {history.created_at}")
            print(f"   - 完成时间: {history.completed_at}")
            
            # 2. 检查学生结果
            print(f"\n📊 2. 检查学生批改结果...")
            results = await get_student_results(history.id)
            print(f"   找到 {len(results)} 条学生结果")
            
            if results:
                for idx, result in enumerate(results, 1):
                    print(f"\n   学生 {idx}:")
                    print(f"   - 学生标识: {result.student_key}")
                    print(f"   - 分数: {result.score}/{result.max_score}")
                    print(f"   - 有结果数据: {'是' if result.result_data else '否'}")
            else:
                print(f"   ⚠️  没有找到任何学生结果！")
            
            # 3. 检查页面图片
            print(f"\n🖼️  3. 检查页面图片...")
            images = await get_page_images(history.id)
            print(f"   找到 {len(images)} 张图片")
            
            if images:
                for idx, img in enumerate(images, 1):
                    print(f"\n   图片 {idx}:")
                    print(f"   - 页码: {img.page_index}")
                    print(f"   - 类型: {img.image_type}")
                    print(f"   - URL: {img.file_url[:80] if img.file_url else 'None'}...")
            else:
                print(f"   ⚠️  没有找到任何图片记录！")
                
        else:
            print(f"   ❌ 未找到批改历史记录")
            
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    batch_id = "1dc62437-ecee-4203-bd59-d38b7882e91a"
    asyncio.run(diagnose_batch(batch_id))
