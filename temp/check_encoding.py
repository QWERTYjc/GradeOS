#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查数据库中的编码问题"""

import asyncio
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'GradeOS-Platform', 'backend'))

from src.utils.database import db


async def check_encoding():
    """检查数据库中的编码"""
    try:
        async with db.connection() as conn:
            # 获取最新的批改历史
            query = """
                SELECT id, batch_id, result_data 
                FROM grading_history 
                ORDER BY created_at DESC 
                LIMIT 1
            """
            cursor = await conn.execute(query)
            history = await cursor.fetchone()
            
            if not history:
                print("没有找到批改历史记录")
                return
            
            print(f"批改历史 ID: {history['id']}")
            print(f"Batch ID: {history['batch_id']}")
            print(f"Result Data 类型: {type(history['result_data'])}")
            
            # 获取学生结果
            query2 = """
                SELECT student_key, summary, result_data
                FROM student_grading_results
                WHERE grading_history_id = %s
                LIMIT 1
            """
            cursor2 = await conn.execute(query2, (history['id'],))
            result = await cursor2.fetchone()
            
            if not result:
                print("没有找到学生结果")
                return
            
            print(f"\n学生: {result['student_key']}")
            print(f"Summary 类型: {type(result['summary'])}")
            print(f"Summary 内容: {result['summary'][:100] if result['summary'] else 'None'}")
            
            # 检查 result_data
            result_data = result['result_data']
            print(f"\nResult Data 类型: {type(result_data)}")
            
            if isinstance(result_data, str):
                # 如果是字符串，尝试解析
                try:
                    parsed = json.loads(result_data)
                    print("Result Data 是 JSON 字符串，已解析")
                    result_data = parsed
                except:
                    print("Result Data 是字符串但无法解析为 JSON")
            
            if isinstance(result_data, dict):
                # 检查 selfAudit
                self_audit = result_data.get('selfAudit') or result_data.get('self_audit')
                if self_audit and isinstance(self_audit, dict):
                    issues = self_audit.get('issues', [])
                    if issues:
                        first_issue = issues[0]
                        message = first_issue.get('message', '')
                        print(f"\n第一个 issue 的 message:")
                        print(f"  原始: {repr(message)}")
                        print(f"  显示: {message}")
                        print(f"  编码: {message.encode('utf-8') if message else 'None'}")
                
                # 保存完整数据到文件（使用正确的编码）
                output_file = 'temp/db_result_utf8.json'
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                print(f"\n完整数据已保存到: {output_file}")
    
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(check_encoding())
