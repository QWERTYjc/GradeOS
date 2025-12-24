"""最终完整测试 - 提交批改并持续监控"""
import requests
import time
import json
from datetime import datetime

print("=" * 80)
print("批量批改系统 - 最终测试")
print("=" * 80)

# 1. 检查服务器健康状态
print("\n[1] 检查服务器状态...")
try:
    health = requests.get("http://localhost:8001/health", timeout=5)
    if health.status_code == 200:
        print(f"✓ 服务器正常: {health.json()}")
    else:
        print(f"✗ 服务器异常: {health.status_code}")
        exit(1)
except Exception as e:
    print(f"✗ 无法连接服务器: {e}")
    exit(1)

# 2. 提交批量批改
print("\n[2] 提交批量批改请求...")
files = {
    'rubrics': ('批改标准.pdf', open('批改标准.pdf', 'rb'), 'application/pdf'),
    'files': ('学生作答.pdf', open('学生作答.pdf', 'rb'), 'application/pdf')
}
data = {'auto_identify': 'true'}

try:
    response = requests.post(
        'http://localhost:8001/batch/submit',
        files=files,
        data=data,
        timeout=300  # 5分钟超时（PDF转换可能需要时间）
    )
    
    if response.status_code == 200:
        result = response.json()
        batch_id = result['batch_id']
        print(f"✓ 批次提交成功!")
        print(f"  批次ID: {batch_id}")
        print(f"  总页数: {result['total_pages']}")
        print(f"  预计完成时间: {result['estimated_completion_time']}秒")
    else:
        print(f"✗ 提交失败: {response.status_code}")
        print(response.text)
        exit(1)
except Exception as e:
    print(f"✗ 提交异常: {e}")
    exit(1)
finally:
    for f in files.values():
        if hasattr(f[1], 'close'):
            f[1].close()

# 3. 持续监控批改进度
print(f"\n[3] 监控批改进度 (批次ID: {batch_id})...")
print("=" * 80)

last_status_str = None
iteration = 0
start_time = time.time()

while True:
    iteration += 1
    elapsed = time.time() - start_time
    
    try:
        status_response = requests.get(
            f'http://localhost:8001/batch/status/{batch_id}',
            timeout=10
        )
        
        if status_response.status_code == 200:
            status = status_response.json()
            current_status_str = json.dumps(status, ensure_ascii=False, sort_keys=True)
            
            # 只在状态变化时打印完整信息
            if current_status_str != last_status_str:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 状态更新 (迭代 {iteration}, 耗时 {elapsed:.1f}秒):")
                print(json.dumps(status, ensure_ascii=False, indent=2))
                last_status_str = current_status_str
            else:
                # 状态未变化，只打印简短信息
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 迭代 {iteration}: {status.get('status')} (无变化)", end='\r')
            
            # 检查是否完成
            current_status = status.get('status')
            if current_status in ['completed', 'failed', 'cancelled']:
                print(f"\n\n{'='*80}")
                print(f"批改流程已结束!")
                print(f"最终状态: {current_status}")
                print(f"总耗时: {elapsed:.1f}秒")
                
                if status.get('results'):
                    print(f"\n结果摘要:")
                    results = status['results']
                    print(f"  学生数: {status.get('total_students', 0)}")
                    print(f"  已完成: {status.get('completed_students', 0)}")
                    print(f"  未识别页: {status.get('unidentified_pages', 0)}")
                
                break
        else:
            print(f"\n✗ 查询失败: HTTP {status_response.status_code}")
            print(status_response.text)
            break
            
    except requests.exceptions.RequestException as e:
        print(f"\n✗ 请求异常: {e}")
        break
    except KeyboardInterrupt:
        print("\n\n用户中断监控")
        break
    
    # 超时保护（30分钟）
    if elapsed > 1800:
        print(f"\n\n✗ 监控超时（{elapsed:.1f}秒），停止监控")
        break
    
    # 等待3秒后再次查询
    time.sleep(3)

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
