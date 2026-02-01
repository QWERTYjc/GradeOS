#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test student boundary detection fix
"""
import requests
import json
import time
from datetime import datetime
import sys
import io

# Set UTF-8 output for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "https://gradeos-production.up.railway.app"

def print_section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

def submit_batch():
    """提交新的批改任务"""
    print_section("步骤 1: 提交批改任务")
    
    url = f"{BASE_URL}/api/batch/submit"
    
    # 打开 PDF 文件
    with open("d:/project/GradeOS/temp/gradeos_test_batch_30.pdf", "rb") as f:
        files = {"files": f}
        data = {
            "exam_id": f"test_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "teacher_id": "teacher_test_001"
        }
        
        print(f"正在提交批改任务...")
        print(f"URL: {url}")
        print(f"文件: gradeos_test_batch_30.pdf")
        
        try:
            response = requests.post(url, files=files, data=data, timeout=60)
            print(f"\nHTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                batch_id = result.get("batch_id")
                print(f"✅ 批改任务提交成功！")
                print(f"Batch ID: {batch_id}")
                return batch_id
            else:
                print(f"❌ 提交失败: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return None

def monitor_progress(batch_id):
    """监控批改进度"""
    print_section("步骤 2: 监控批改进度")
    
    url = f"{BASE_URL}/api/batch/status/{batch_id}"
    
    print(f"监控 URL: {url}")
    print(f"开始监控...\n")
    
    start_time = time.time()
    max_wait = 300  # 最多等待 5 分钟
    
    last_stage = None
    last_progress = None
    
    while True:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                status = response.json()
                
                current_stage = status.get("current_stage", "unknown")
                progress = status.get("progress", 0)
                batch_status = status.get("status", "unknown")
                total_students = status.get("total_students", 0)
                
                # 只在状态变化时打印
                if current_stage != last_stage or progress != last_progress:
                    elapsed = time.time() - start_time
                    print(f"[{elapsed:.1f}s] 状态: {batch_status} | 阶段: {current_stage} | 进度: {progress*100:.1f}% | 学生数: {total_students}")
                    last_stage = current_stage
                    last_progress = progress
                
                # 检查是否完成
                if batch_status == "completed":
                    print(f"\n✅ 批改任务完成！")
                    print(f"总耗时: {elapsed:.1f} 秒")
                    print(f"总学生数: {total_students}")
                    return True
                
                # 检查是否失败
                if batch_status == "failed":
                    print(f"\n❌ 批改任务失败！")
                    error = status.get("error", "未知错误")
                    print(f"错误信息: {error}")
                    return False
                
                # 检查超时
                if time.time() - start_time > max_wait:
                    print(f"\n⏱️ 超时！已等待 {max_wait} 秒")
                    return False
                
            else:
                print(f"❌ 状态查询失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return False
        
        time.sleep(10)  # 每 10 秒查询一次

def verify_results(batch_id):
    """验证批改结果"""
    print_section("步骤 3: 验证批改结果")
    
    url = f"{BASE_URL}/api/batch/full-results/{batch_id}"
    
    print(f"获取结果 URL: {url}\n")
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            result = response.json()
            
            # 保存完整结果
            output_file = f"d:/project/GradeOS/temp/batch_results_{batch_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"完整结果已保存到: {output_file}\n")
            
            # 关键指标
            total_students = result.get("total_students", 0)
            results = result.get("results", [])
            students = result.get("students", [])
            parsed_rubric = result.get("parsed_rubric", {})
            total_questions = parsed_rubric.get("total_questions", 0)
            
            print("🎯 关键指标验证")
            print("-" * 60)
            print(f"总学生数 (total_students): {total_students}")
            print(f"结果数量 (results): {len(results)}")
            print(f"学生列表长度 (students): {len(students)}")
            print(f"题目数量 (questions): {total_questions}")
            print()
            
            # 修复前后对比
            print("📊 修复前后对比")
            print("-" * 60)
            print("修复前:")
            print("  ❌ total_students = 0")
            print("  ❌ results = []")
            print("  ❌ students = []")
            print()
            print("修复后:")
            if total_students > 0:
                print(f"  ✅ total_students = {total_students} (> 0)")
            else:
                print(f"  ❌ total_students = {total_students} (仍为 0)")
            
            if len(results) > 0:
                print(f"  ✅ results = {len(results)} 条记录")
            else:
                print(f"  ❌ results = [] (仍为空)")
            
            if len(students) > 0:
                print(f"  ✅ students = {len(students)} 个学生")
            else:
                print(f"  ❌ students = [] (仍为空)")
            print()
            
            # 最终判断
            print("🏁 修复效果判断")
            print("-" * 60)
            if total_students > 0 and len(results) > 0 and len(students) > 0:
                print("✅ ✅ ✅ 修复成功！学生边界检测功能已恢复正常！")
                
                # 显示学生详情
                print(f"\n学生列表 (前 3 个):")
                for i, student in enumerate(students[:3]):
                    print(f"  学生 {i+1}:")
                    print(f"    - ID: {student.get('student_id', 'N/A')}")
                    print(f"    - 总分: {student.get('total_score', 'N/A')}")
                    grades = student.get('grades', [])
                    print(f"    - 已批改题目: {len(grades)} 题")
                
                return True
            else:
                print("❌ ❌ ❌ 修复失败！学生边界检测仍然存在问题！")
                return False
        else:
            print(f"❌ 获取结果失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

def main():
    print_section("[TEST] Student Boundary Detection Fix Verification")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend URL: {BASE_URL}")
    
    # Step 1: Submit batch task
    batch_id = submit_batch()
    if not batch_id:
        print("\n[FAILED] Cannot submit batch task")
        return
    
    # Step 2: Monitor progress
    success = monitor_progress(batch_id)
    if not success:
        print("\n[FAILED] Batch task did not complete successfully")
        return
    
    # Step 3: Verify results
    verify_results(batch_id)
    
    print_section("[COMPLETE] Test Finished")

if __name__ == "__main__":
    main()
