"""
学生边界检测器使用示例

展示如何使用 StudentBoundaryDetector 从批改结果中检测学生边界
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.student_boundary_detector import StudentBoundaryDetector


async def main():
    """主函数：演示学生边界检测"""
    
    # 创建检测器
    detector = StudentBoundaryDetector(confidence_threshold=0.8)
    
    # 示例1：基于学生标识的检测
    print("=" * 60)
    print("示例1：基于学生标识的检测")
    print("=" * 60)
    
    grading_results_with_info = [
        {
            "page_index": 0,
            "question_id": "1",
            "student_info": {
                "name": "张三",
                "student_id": "2024001",
                "confidence": 0.95
            }
        },
        {
            "page_index": 1,
            "question_id": "2",
            "student_info": {
                "name": "张三",
                "student_id": "2024001",
                "confidence": 0.95
            }
        },
        {
            "page_index": 2,
            "question_id": "1",
            "student_info": {
                "name": "李四",
                "student_id": "2024002",
                "confidence": 0.90
            }
        },
        {
            "page_index": 3,
            "question_id": "2",
            "student_info": {
                "name": "李四",
                "student_id": "2024002",
                "confidence": 0.90
            }
        }
    ]
    
    result1 = await detector.detect_boundaries(grading_results_with_info)
    
    print(f"\n检测结果：")
    print(f"  总页数: {result1.total_pages}")
    print(f"  学生数: {result1.total_students}")
    print(f"  未分配页面: {result1.unassigned_pages}")
    print(f"\n学生边界：")
    for i, boundary in enumerate(result1.boundaries, 1):
        print(f"  学生 {i}:")
        print(f"    标识: {boundary.student_key}")
        print(f"    页面范围: {boundary.start_page} - {boundary.end_page}")
        print(f"    置信度: {boundary.confidence:.2f}")
        print(f"    需要确认: {boundary.needs_confirmation}")
        print(f"    检测方法: {boundary.detection_method}")
        if boundary.student_info:
            print(f"    姓名: {boundary.student_info.name}")
            print(f"    学号: {boundary.student_info.student_id}")
    
    # 示例2：基于题目循环的检测
    print("\n" + "=" * 60)
    print("示例2：基于题目循环的检测（无学生标识）")
    print("=" * 60)
    
    grading_results_with_questions = [
        {"page_index": 0, "question_id": "1", "question_numbers": ["1"]},
        {"page_index": 1, "question_id": "2", "question_numbers": ["2"]},
        {"page_index": 2, "question_id": "3", "question_numbers": ["3"]},
        {"page_index": 3, "question_id": "1", "question_numbers": ["1"]},  # 循环开始
        {"page_index": 4, "question_id": "2", "question_numbers": ["2"]},
        {"page_index": 5, "question_id": "3", "question_numbers": ["3"]},
    ]
    
    result2 = await detector.detect_boundaries(grading_results_with_questions)
    
    print(f"\n检测结果：")
    print(f"  总页数: {result2.total_pages}")
    print(f"  学生数: {result2.total_students}")
    print(f"  未分配页面: {result2.unassigned_pages}")
    print(f"\n学生边界：")
    for i, boundary in enumerate(result2.boundaries, 1):
        print(f"  学生 {i}:")
        print(f"    标识: {boundary.student_key}")
        print(f"    页面范围: {boundary.start_page} - {boundary.end_page}")
        print(f"    置信度: {boundary.confidence:.2f}")
        print(f"    需要确认: {boundary.needs_confirmation}")
        print(f"    检测方法: {boundary.detection_method}")
    
    # 示例3：低置信度边界
    print("\n" + "=" * 60)
    print("示例3：低置信度边界（需要人工确认）")
    print("=" * 60)
    
    grading_results_low_confidence = [
        {
            "page_index": 0,
            "question_id": "1",
            "student_info": {
                "name": "王五",
                "student_id": "2024003",
                "confidence": 0.65  # 中等置信度
            }
        },
        {
            "page_index": 1,
            "question_id": "2",
            "student_info": {
                "name": "王五",
                "student_id": "2024003",
                "confidence": 0.65
            }
        }
    ]
    
    result3 = await detector.detect_boundaries(grading_results_low_confidence)
    
    print(f"\n检测结果：")
    print(f"  总页数: {result3.total_pages}")
    print(f"  学生数: {result3.total_students}")
    print(f"\n学生边界：")
    for i, boundary in enumerate(result3.boundaries, 1):
        print(f"  学生 {i}:")
        print(f"    标识: {boundary.student_key}")
        print(f"    页面范围: {boundary.start_page} - {boundary.end_page}")
        print(f"    置信度: {boundary.confidence:.2f}")
        print(f"    需要确认: {'是' if boundary.needs_confirmation else '否'}")
        if boundary.needs_confirmation:
            print(f"    ⚠️  此边界置信度较低，建议人工确认")


if __name__ == "__main__":
    asyncio.run(main())
