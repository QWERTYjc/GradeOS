"""完整测试 Railway 部署的批改功能"""
import requests
import json
import base64
import time
from pathlib import Path

BACKEND_URL = "https://gradeos-production.up.railway.app"

def encode_pdf_to_base64(pdf_path):
    """将 PDF 转换为 Base64"""
    with open(pdf_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def test_batch_submit():
    """测试批量批改提交"""
    print("=" * 80)
    print("测试批量批改功能")
    print("=" * 80)
    
    # 1. 准备测试数据
    print("\n[1/4] 准备测试数据...")
    pdf_path = Path("temp/gradeos_test_batch_30.pdf")
    rubric_path = Path("temp/test_rubric.json")
    
    if not pdf_path.exists():
        print(f"[ERROR] PDF 文件不存在: {pdf_path}")
        return None
    
    if not rubric_path.exists():
        print(f"[ERROR] Rubric 文件不存在: {rubric_path}")
        return None
    
    # 读取 PDF 并转换为 Base64
    pdf_base64 = encode_pdf_to_base64(pdf_path)
    print(f"[OK] PDF 文件读取成功，大小: {len(pdf_base64)} 字节（Base64）")
    
    # 读取 Rubric
    with open(rubric_path, 'r', encoding='utf-8') as f:
        rubric_data = json.load(f)
    print(f"[OK] Rubric 读取成功，题目数量: {len(rubric_data['questions'])}")
    
    # 2. 提交批改任务
    print("\n[2/4] 提交批改任务...")
    submit_url = f"{BACKEND_URL}/api/batch/submit"
    
    payload = {
        "pdf_base64": pdf_base64,
        "rubric": rubric_data,
        "user_id": "test_user_001",
        "homework_id": "test_homework_001"
    }
    
    try:
        response = requests.post(submit_url, json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[ERROR] 提交失败: {response.text}")
            return None
        
        result = response.json()
        batch_id = result.get('batch_id')
        print(f"[OK] 批改任务提交成功")
        print(f"批次 ID: {batch_id}")
        print(f"响应数据: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        return batch_id
    
    except Exception as e:
        print(f"[ERROR] 请求失败: {str(e)}")
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
                print(f"\n[ERROR] 批改任务失败: {status_data.get('error')}")
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
            print(f"[ERROR] 结果获取失败: {response.text}")
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
        
        # 显示完整响应（截断）
        print(f"\n完整响应数据（前 2000 字符）:")
        response_str = json.dumps(results_data, indent=2, ensure_ascii=False)
        print(response_str[:2000])
        if len(response_str) > 2000:
            print(f"\n... (剩余 {len(response_str) - 2000} 字符被截断)")
        
        return results_data
    
    except Exception as e:
        print(f"[ERROR] 请求失败: {str(e)}")
        return None

def main():
    """主测试流程"""
    print("\n\n")
    print("*" * 80)
    print("Railway 部署 - AI 批改功能完整测试")
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
        return
    
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
    print(f"最终状态: {status_data.get('status', 'unknown')}")
    print(f"学生总数: {results_data.get('total_students', 0)}")
    print(f"结果数量: {len(results_data.get('results', []))}")
    
    # 检查已知问题
    print("\n已知问题检查:")
    if results_data.get('total_students', 0) == 0:
        print("[X] total_students = 0 (已知 bug)")
    else:
        print("[OK] total_students > 0")
    
    if len(results_data.get('results', [])) == 0:
        print("[X] results 为空 (已知 bug)")
    else:
        print("[OK] results 包含数据")
    
    print("\n[DONE] 测试完成!")

if __name__ == "__main__":
    main()
