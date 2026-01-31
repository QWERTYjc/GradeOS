"""简单检查数据库"""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def check_history():
    """检查批改历史"""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # 检查表是否存在
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'grading_history'
                )
            """)
            table_exists = cur.fetchone()[0]
            print(f"grading_history 表存在: {table_exists}")
            
            if not table_exists:
                print("\n❌ grading_history 表不存在！")
                return
            
            # 查询记录数
            cur.execute("SELECT COUNT(*) FROM grading_history")
            count = cur.fetchone()[0]
            print(f"\n批改历史记录总数: {count}")
            
            # 查询最近的记录
            cur.execute("""
                SELECT id, batch_id, class_ids, total_students, status, created_at 
                FROM grading_history 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            rows = cur.fetchall()
            
            if rows:
                print("\n最近的 10 条记录:")
                for row in rows:
                    print(f"  - ID: {row[0]}")
                    print(f"    batch_id: {row[1]}")
                    print(f"    class_ids: {row[2]}")
                    print(f"    total_students: {row[3]}")
                    print(f"    status: {row[4]}")
                    print(f"    created_at: {row[5]}")
                    print()
            else:
                print("\n❌ 没有找到任何批改历史记录！")
                print("\n可能的原因:")
                print("1. 批改任务还没有完成")
                print("2. 批改完成后没有保存到 grading_history 表")
                print("3. 数据保存逻辑有问题")


if __name__ == "__main__":
    check_history()
