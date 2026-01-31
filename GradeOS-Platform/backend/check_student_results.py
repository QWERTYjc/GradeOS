"""
检查最近一次批改的学生结果
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.database import db


async def check_recent_grading():
    """检查最近一次批改的学生结果"""
    
    # 获取最近的批改历史
    query = """
    SELECT 
        gh.id as history_id,
        gh.batch_id,
        gh.total_students,
        gh.created_at,
        COUNT(sgr.id) as actual_student_count
    FROM grading_history gh
    LEFT JOIN student_grading_results sgr ON gh.id = sgr.grading_history_id
    GROUP BY gh.id, gh.batch_id, gh.total_students, gh.created_at
    ORDER BY gh.created_at DESC
    LIMIT 1
    """
    
    async with db.pool.acquire() as conn:
        result = await conn.fetchrow(query)
    
    if not result:
        print("❌ 没有找到批改历史")
        return
    
    print(f"\n📊 最近一次批改:")
    print(f"  History ID: {result['history_id']}")
    print(f"  Batch ID: {result['batch_id']}")
    print(f"  记录的学生数: {result['total_students']}")
    print(f"  实际保存的学生数: {result['actual_student_count']}")
    print(f"  创建时间: {result['created_at']}")
    
    # 获取所有学生的详细信息
    students_query = """
    SELECT 
        student_key,
        student_id,
        score,
        max_score,
        COUNT(*) OVER (PARTITION BY student_key) as duplicate_count
    FROM student_grading_results
    WHERE grading_history_id = $1
    ORDER BY student_key
    """
    
    students = await db.fetch_all(students_query, result['history_id'])
    
    print(f"\n👥 学生列表 (共 {len(students)} 条记录):")
    for idx, student in enumerate(students, 1):
        duplicate_flag = " ⚠️ 重复" if student['duplicate_count'] > 1 else ""
        print(
            f"  {idx}. {student['student_key']} "
            f"(ID: {student['student_id'] or 'N/A'}) - "
            f"{student['score']}/{student['max_score']}{duplicate_flag}"
        )
    
    # 检查是否有重复的 student_key
    duplicate_check_query = """
    SELECT 
        student_key,
        COUNT(*) as count
    FROM student_grading_results
    WHERE grading_history_id = $1
    GROUP BY student_key
    HAVING COUNT(*) > 1
    """
    
    duplicates = await db.fetch_all(duplicate_check_query, result['history_id'])
    
    if duplicates:
        print(f"\n⚠️ 发现重复的学生记录:")
        for dup in duplicates:
            print(f"  - {dup['student_key']}: {dup['count']} 条记录")
    else:
        print(f"\n✅ 没有重复的学生记录")
    
    # 检查页面图像数量
    images_query = """
    SELECT 
        COUNT(*) as total_images,
        COUNT(DISTINCT student_key) as unique_students,
        COUNT(DISTINCT page_index) as unique_pages
    FROM grading_page_images
    WHERE grading_history_id = $1
    """
    
    images_result = await db.fetch_one(images_query, result['history_id'])
    
    print(f"\n🖼️ 页面图像统计:")
    print(f"  总图像数: {images_result['total_images']}")
    print(f"  不同学生数: {images_result['unique_students']}")
    print(f"  不同页码数: {images_result['unique_pages']}")
    
    if images_result['total_images'] > 0:
        avg_pages = images_result['total_images'] / images_result['unique_students']
        print(f"  平均每学生页数: {avg_pages:.1f}")


async def main():
    try:
        await db.connect()
        await check_recent_grading()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
