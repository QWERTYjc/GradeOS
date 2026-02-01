"""
数据库迁移脚本：添加批改页面图像表

运行方式：
    python scripts/migrate_add_images.py
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import db


async def migrate():
    """执行数据库迁移"""
    print("开始数据库迁移：添加批改页面图像索引表...")
    
    try:
        # 检查环境变量
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("⚠️  未设置 DATABASE_URL 环境变量")
            print("请设置数据库连接字符串，例如：")
            print("  export DATABASE_URL='postgresql://user:password@localhost:5432/dbname'")
            return
        
        print(f"数据库连接: {db_url[:30]}...")
        
        # 连接数据库（不使用统一连接池）
        await db.connect(use_unified_pool=False)
        
        if not db.is_available:
            print("❌ 数据库连接失败")
            return
        
        print("✅ 数据库连接成功")
        
        # 读取 SQL 文件
        sql_file = os.path.join(os.path.dirname(__file__), "create_image_table.sql")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql = f.read()
        
        print("执行 SQL 迁移...")
        
        # 执行 SQL
        async with db.connection() as conn:
            # 分割 SQL 语句并逐个执行
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for i, statement in enumerate(statements, 1):
                if statement:
                    print(f"  执行语句 {i}/{len(statements)}...")
                    await conn.execute(statement)
            await conn.commit()
        
        print("\n✅ 数据库迁移成功！")
        print("   - 已创建 grading_page_images 表（文件索引）")
        print("   - 已创建相关索引")
        print("   - 已添加外键约束")
        
    except FileNotFoundError as e:
        print(f"❌ SQL 文件未找到: {e}")
    except Exception as e:
        print(f"❌ 数据库迁移失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(migrate())
