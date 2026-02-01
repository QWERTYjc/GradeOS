#!/usr/bin/env python3
"""
测试批改标准复核修复
验证 rubric_data 和 rubric_images 能否正确从数据库和文件存储读取
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.db.postgres_grading import get_grading_history
from src.services.file_storage import get_file_storage_service


async def test_rubric_review_context(batch_id: str):
    """测试获取 rubric review 上下文"""
    print(f"\n{'='*60}")
    print(f"测试批次: {batch_id}")
    print(f"{'='*60}\n")
    
    # 1. 测试从数据库读取 grading history
    print("1. 从数据库读取 grading history...")
    history = await get_grading_history(batch_id)
    
    if not history:
        print(f"❌ 批次不存在: {batch_id}")
        return False
    
    print(f"✅ 找到批改历史:")
    print(f"   - ID: {history.id}")
    print(f"   - Status: {history.status}")
    print(f"   - Current Stage: {history.current_stage}")
    print(f"   - Total Students: {history.total_students}")
    
    # 2. 检查 rubric_data
    print("\n2. 检查 rubric_data...")
    if history.rubric_data:
        print(f"✅ rubric_data 存在")
        if isinstance(history.rubric_data, dict):
            total_questions = history.rubric_data.get("totalQuestions") or history.rubric_data.get("total_questions", 0)
            total_score = history.rubric_data.get("totalScore") or history.rubric_data.get("total_score", 0)
            questions = history.rubric_data.get("questions", [])
            print(f"   - 总题数: {total_questions}")
            print(f"   - 总分: {total_score}")
            print(f"   - 题目列表长度: {len(questions)}")
        else:
            print(f"⚠️  rubric_data 类型错误: {type(history.rubric_data)}")
    else:
        print(f"❌ rubric_data 为空")
    
    # 3. 测试从文件存储读取 rubric 图片
    print("\n3. 从文件存储读取 rubric 图片...")
    try:
        file_storage = get_file_storage_service()
        stored_files = await file_storage.list_batch_files(batch_id)
        
        if not stored_files:
            print(f"⚠️  文件存储中没有找到文件")
        else:
            rubric_files = [
                item for item in stored_files
                if item.metadata.get("type") == "rubric" or item.filename.startswith("rubric_page")
            ]
            
            if rubric_files:
                print(f"✅ 找到 {len(rubric_files)} 个 rubric 文件:")
                for idx, file in enumerate(rubric_files[:3]):  # 只显示前3个
                    print(f"   - {file.filename} ({file.file_id})")
                if len(rubric_files) > 3:
                    print(f"   ... 还有 {len(rubric_files) - 3} 个文件")
            else:
                print(f"⚠️  没有找到 rubric 类型的文件")
                print(f"   所有文件类型: {[f.metadata.get('type') for f in stored_files[:5]]}")
    except Exception as exc:
        print(f"❌ 读取文件存储失败: {exc}")
    
    print(f"\n{'='*60}")
    print("测试完成")
    print(f"{'='*60}\n")
    
    return True


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python test_rubric_review_fix.py <batch_id>")
        print("示例: python test_rubric_review_fix.py abc123-def456")
        sys.exit(1)
    
    batch_id = sys.argv[1]
    
    try:
        await test_rubric_review_context(batch_id)
    except Exception as exc:
        print(f"\n❌ 测试失败: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
