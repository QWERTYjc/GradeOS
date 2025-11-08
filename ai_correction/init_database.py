#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from functions.database import DatabaseManager, Base
from config import DATABASE_TYPE, DATABASE_URL


def init_database():
    """初始化数据库"""
    print("🚀 开始初始化数据库...")
    print(f"数据库类型: {DATABASE_TYPE}")
    print(f"连接字符串: {DATABASE_URL}")
    
    try:
        # 创建数据库管理器
        db = DatabaseManager(db_type=DATABASE_TYPE, connection_string=DATABASE_URL)
        
        if db.engine:
            # 创建所有表
            Base.metadata.create_all(db.engine)
            print("✅ 数据库表创建成功！")
            
            # 显示创建的表
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"\n📋 已创建 {len(tables)} 张表:")
            for table in tables:
                print(f"  - {table}")
        else:
            print("⚠️ 使用 JSON 文件存储，无需创建数据库表")
            
            # 创建数据目录
            data_dir = Path('data')
            data_dir.mkdir(exist_ok=True)
            print(f"✅ 数据目录已创建: {data_dir.absolute()}")
        
        print("\n✨ 数据库初始化完成！")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_database():
    """测试数据库连接"""
    print("\n🧪 测试数据库连接...")
    
    try:
        db = DatabaseManager(db_type=DATABASE_TYPE, connection_string=DATABASE_URL)
        
        # 测试保存学生
        student_data = {
            'id': 'test_001',
            'name': '测试学生',
            'class': '测试班级'
        }
        
        student_id = db.save_student(student_data)
        print(f"✅ 保存学生成功，ID: {student_id}")
        
        # 测试保存任务
        task_data = {
            'student_id': 'test_001',
            'subject': '数学',
            'total_questions': 10
        }
        
        task_id = db.save_grading_task(task_data)
        print(f"✅ 保存任务成功，ID: {task_id}")
        
        # 测试查询历史
        history = db.get_student_history('test_001')
        print(f"✅ 查询历史成功，找到 {len(history)} 条记录")
        
        print("\n✨ 数据库测试通过！")
        
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库初始化工具')
    parser.add_argument('--test', action='store_true', help='运行测试')
    
    args = parser.parse_args()
    
    # 初始化数据库
    init_database()
    
    # 运行测试
    if args.test:
        test_database()

