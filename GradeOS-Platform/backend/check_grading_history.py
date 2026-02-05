"""检查批改历史数据"""
import os
import sys
import json

# 添加 src 到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db.postgres_store import get_connection

def check_grading_history():
    """检查批改历史数据"""
    with get_connection() as conn:
        # 1. 检查 grading_history 表
        print("\n=== grading_history 表 ===")
        rows = conn.execute("""
            SELECT id, batch_id, status, class_ids, total_students, 
                   result_data,
                   created_at
            FROM grading_history 
            ORDER BY created_at DESC 
            LIMIT 10
        """).fetchall()
        for row in rows:
            result_data = row['result_data']
            if isinstance(result_data, str):
                try:
                    result_data = json.loads(result_data)
                except:
                    pass
            homework_id = result_data.get('homework_id') if isinstance(result_data, dict) else None
            assignment_id = result_data.get('assignment_id') if isinstance(result_data, dict) else None
            print(f"ID: {row['id']}")
            print(f"  batch_id: {row['batch_id']}")
            print(f"  status: {row['status']}")
            print(f"  class_ids: {row['class_ids']}")
            print(f"  homework_id: {homework_id}")
            print(f"  assignment_id: {assignment_id}")
            print(f"  total_students: {row['total_students']}")
            print(f"  created_at: {row['created_at']}")
            print()
        
        # 2. 检查 homeworks 表（注意是复数）
        print("\n=== homeworks 表 ===")
        try:
            homeworks = conn.execute("""
                SELECT id, title, class_id, created_at
                FROM homeworks
                ORDER BY created_at DESC
                LIMIT 10
            """).fetchall()
            for hw in homeworks:
                print(f"id: {hw['id']}, title: {hw['title']}, class_id: {hw['class_id']}")
        except Exception as e:
            print(f"Error: {e}")
            # 尝试其他可能的表名
            print("\n尝试查找所有表...")
            tables = conn.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """).fetchall()
            for t in tables:
                print(f"  - {t['table_name']}")
        
        # 3. 检查 runs 表（批改任务）- 先检查表结构
        print("\n=== runs 表结构 ===")
        try:
            cols = conn.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'runs'
            """).fetchall()
            print("列: " + ", ".join([c['column_name'] for c in cols]))
            
            runs = conn.execute("""
                SELECT * FROM runs ORDER BY created_at DESC LIMIT 5
            """).fetchall()
            for run in runs:
                print(f"Run: {dict(run)}")
        except Exception as e:
            print(f"Error: {e}")

        # 4. 检查 grading_history_items 表
        print("\n=== grading_history_items 表 ===")
        try:
            items = conn.execute("""
                SELECT id, history_id, student_id, student_name, score, max_score, status
                FROM grading_history_items
                ORDER BY created_at DESC
                LIMIT 10
            """).fetchall()
            for item in items:
                print(f"ID: {item['id']}, history_id: {item['history_id']}, student: {item['student_name']}, score: {item['score']}/{item['max_score']}")
        except Exception as e:
            print(f"Error: {e}")
        
        # 5. 检查 batch_results 表（可能存储批改结果）
        print("\n=== 检查其他可能的结果表 ===")
        tables = conn.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name LIKE '%result%'
        """).fetchall()
        for t in tables:
            print(f"  - {t['table_name']}")

if __name__ == "__main__":
    check_grading_history()
