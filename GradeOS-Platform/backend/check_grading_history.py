"""检查 PostgreSQL 中的批改历史记录"""
import asyncio
import os
from dotenv import load_dotenv
from src.utils.pool_manager import UnifiedPoolManager

load_dotenv()


async def check_history():
    """检查批改历史表"""
    pool_manager = await UnifiedPoolManager.get_instance()
    await pool_manager.initialize()
    
    try:
        async with pool_manager.get_postgres_connection() as conn:
            # 检查表是否存在
            cursor = await conn.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'grading_history'
                )
                """
            )
            table_exists = (await cursor.fetchone())[0]
            print(f"grading_history 表存在: {table_exists}")
            
            if not table_exists:
                print("\n❌ grading_history 表不存在！")
                return
            
            # 查询记录数
            cursor = await conn.execute("SELECT COUNT(*) FROM grading_history")
            count = (await cursor.fetchone())[0]
            print(f"\n批改历史记录总数: {count}")
            
            # 查询最近的记录
            cursor = await conn.execute(
                """
                SELECT id, batch_id, class_ids, total_students, status, created_at 
                FROM grading_history 
                ORDER BY created_at DESC 
                LIMIT 10
                """
            )
            rows = await cursor.fetchall()
            
            if rows:
                print("\n最近的 10 条记录:")
                for row in rows:
                    print(f"  - ID: {row['id']}")
                    print(f"    batch_id: {row['batch_id']}")
                    print(f"    class_ids: {row['class_ids']}")
                    print(f"    total_students: {row['total_students']}")
                    print(f"    status: {row['status']}")
                    print(f"    created_at: {row['created_at']}")
                    print()
            else:
                print("\n❌ 没有找到任何批改历史记录！")
                print("\n可能的原因:")
                print("1. 批改任务还没有完成")
                print("2. 批改完成后没有保存到 grading_history 表")
                print("3. 数据保存逻辑有问题")
    
    finally:
        await pool_manager.close()


if __name__ == "__main__":
    asyncio.run(check_history())
