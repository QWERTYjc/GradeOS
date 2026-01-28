"""完整测试 Railway 部署的批改功能 - 使用正确的 API 格式"""
import requests
import json
import time
from pathlib import Path

BACKEND_URL = "https://gradeos-production.up.railway.app"

def test_batch_submit():
    """测试批量批改提交 - 使用 multipart/form-data"""
    print("=" * 80)
    print("测试批量批改功能")
    print("=" * 80)
    
    # 1. 准备测试数据
    print("\n[1/4] 准备测试数据...")
    pdf_path = Path("temp/gradeos_test_batch_30.pdf")
    
    if not pdf_path.exists():
        print(f"[ERROR] PDF 文件不存在: {pdf_path}")
        return None
    
    print(f"[OK] PDF 文件找到: {pdf_path}")
    print(f"[OK] 文件大小: {pdf_path.stat().st_size} 字节")
    
    # 2. 提交批改任务（使用 multipart/form-data）
    print("\n[2/4] 提交批改任务...")
    submit_url = f"{BACKEND_URL}/api/batch/submit"
    
    # 准备文件和表单数据
    files = {
        'files': ('gradeos_test_batch_30.pdf', open(pdf_path, 'rb'), 'application/pdf')
    }
    
    data = {
        'exam_id': 'test_exam_001',
        'teacher_id': 'test_teacher_001'
    }
    
    try:
        response = requests.post(submit_url, files=files, data=data, timeout=60)
        print(f"状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[ERROR] 提交失败")
            print(f"响应: {response.text}")
            return None
        
        result = response.json()
        batch_id = result.get('batch_id')
        print(f"[OK] 批改任务提交成功")
        print(f"批次 ID: {batch_id}")
        print(f"响应数据:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return batch_id
    
    except Exception as e:
        print(f"[ERROR] 请求失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_batch_status(batch_id):
    """测试批改状态查询"""
    print(f"\n[3/4] 查询批改状态...")
    status_url = f"{BACKEND_URL}/api/batch/status/{batch_id}"
    
    max_retries = 60  # 最多等待 60 次，每次 5 秒 = 5 分钟
    retry_interval = 5
    
    for i in range(max_retries):
        try:
            response = requests.get(status_url, timeout=10)
            
            if response.status_code != 200:
                print(f"[ERROR] 状态查询失败: {response.text}")
                return None
            
            status_data = response.json()
            current_status = status_data.get('status', 'unknown')
            progress = status_data.get('progress', {})
            
            print(f"\n[轮询 {i+1}/{max_retries}] 当前状态: {current_status}")
            print(f"  - 阶段: {progress.get('stage', 'N/A')}")
            print(f"  - 进度: {progress.get('percentage', 0)}%")
            print(f"  - 消息: {progress.get('message', 'N/A')}")
            
            # 检查是否完成
            if current_status in ['completed', 'success']:
                print("\n[OK] 批改任务完成!")
                return status_data
            elif current_status in ['failed', 'error']:
                print(f"\n[ERROR] 批改任务失败")
                print(f"错误信息: {status_data.get('error', 'N/A')}")
                print(f"完整状态数据:")
                print(json.dumps(status_data, indent=2, ensure_ascii=False))
                return status_data
            
            # 等待下一次轮询
            time.sleep(retry_interval)
        
        except Exception as e:
            print(f"[ERROR] 状态查询异常: {str(e)}")
            time.sleep(retry_interval)
    
    print(f"\n[TIMEOUT] 批改任务超时（等待了 {max_retries * retry_interval} 秒）")
    return None

def test_batch_results(batch_id):
    """测试批改结果获取"""
    print(f"\n[4/4] 获取批改结果...")
    results_url = f"{BACKEND_URL}/api/batch/results/{batch_id}"
    
    try:
        response = requests.get(results_url, timeout=10)
        
        if response.status_code != 200:
            print(f"[ERROR] 结果获取失败")
            print(f"响应: {response.text}")
            return None
        
        results_data = response.json()
        print(f"[OK] 结果获取成功")
        
        # 分析结果
        print("\n" + "=" * 80)
        print("批改结果分析")
        print("=" * 80)
        
        total_students = results_data.get('total_students', 0)
        print(f"\n学生总数: {total_students}")
        
        if total_students == 0:
            print("[WARNING] total_students = 0! 这可能是一个已知 bug。")
        
        results = results_data.get('results', [])
        print(f"结果数量: {len(results)}")
        
        if len(results) == 0:
            print("[WARNING] 结果为空! 这可能是一个已知 bug。")
        else:
            # 显示第一个学生的结果
            print(f"\n第一个学生的结果示例:")
            first_result = results[0]
            print(json.dumps(first_result, indent=2, ensure_ascii=False))
        
        # 检查题目信息
        questions = results_data.get('questions', [])
        print(f"\n题目数量: {len(questions)}")
        if questions:
            print("题目列表:")
            for q in questions:
                print(f"  - {q.get('question_id', 'N/A')}: {q.get('max_score', 0)} 分")
        
        # 显示部分完整响应
        print(f"\n完整响应数据（前 2000 字符）:")
        response_str = json.dumps(results_data, indent=2, ensure_ascii=False)
        print(response_str[:2000])
        if len(response_str) > 2000:
            print(f"\n... (剩余 {len(response_str) - 2000} 字符被截断)")
        
        return results_data
    
    except Exception as e:
        print(f"[ERROR] 请求失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主测试流程"""
    print("\n\n")
    print("*" * 80)
    print("Railway 部署 - AI 批改功能完整测试")
    print("测试时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("*" * 80)
    
    # 1. 提交批改任务
    batch_id = test_batch_submit()
    
    if not batch_id:
        print("\n[FAILED] 批改任务提交失败，测试终止。")
        return
    
    # 2. 监控批改状态
    status_data = test_batch_status(batch_id)
    
    if not status_data:
        print("\n[FAILED] 批改状态查询失败或超时。")
        # 即使超时，也尝试获取结果
        print("\n[INFO] 尝试获取结果...")
    
    # 3. 获取批改结果
    results_data = test_batch_results(batch_id)
    
    if not results_data:
        print("\n[FAILED] 批改结果获取失败。")
        return
    
    # 4. 总结
    print("\n\n")
    print("=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"批次 ID: {batch_id}")
    if status_data:
        print(f"最终状态: {status_data.get('status', 'unknown')}")
    print(f"学生总数: {results_data.get('total_students', 0)}")
    print(f"结果数量: {len(results_data.get('results', []))}")
    print(f"题目数量: {len(results_data.get('questions', []))}")
    
    # 检查已知问题
    print("\n已知问题检查:")
    issues_found = []
    
    if results_data.get('total_students', 0) == 0:
        issues_found.append("total_students = 0")
        print("[X] total_students = 0 (已知 bug)")
    else:
        print("[OK] total_students > 0")
    
    if len(results_data.get('results', [])) == 0:
        issues_found.append("results 为空")
        print("[X] results 为空 (已知 bug)")
    else:
        print("[OK] results 包含数据")
    
    if len(results_data.get('questions', [])) == 0:
        issues_found.append("questions 为空")
        print("[X] questions 为空 (可能缺少 rubric)")
    else:
        print("[OK] questions 包含数据")
    
    if issues_found:
        print(f"\n[WARNING] 发现 {len(issues_found)} 个问题:")
        for issue in issues_found:
            print(f"  - {issue}")
    else:
        print("\n[OK] 没有发现已知问题，批改功能正常!")
    
    print("\n[DONE] 测试完成!")

if __name__ == "__main__":
    main()
