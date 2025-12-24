"""快速测试 - 提交并立即查看状态"""
import requests
import json
import time

print("提交批改请求...")
files = {
    'rubrics': ('批改标准.pdf', open('批改标准.pdf', 'rb'), 'application/pdf'),
    'files': ('学生作答.pdf', open('学生作答.pdf', 'rb'), 'application/pdf')
}
data = {'auto_identify': 'true'}

response = requests.post('http://localhost:8002/batch/submit', files=files, data=data, timeout=300)

if response.status_code == 200:
    result = response.json()
    batch_id = result['batch_id']
    print(f"✓ 批次ID: {batch_id}")
    
    # 等待完成
    print("\n等待批改完成...")
    for i in range(100):
        time.sleep(5)
        status = requests.get(f'http://localhost:8002/batch/status/{batch_id}').json()
        print(f"[{i+1}] 状态: {status['status']}")
        
        if status['status'] == 'completed':
            print(f"\n✓ 批改完成!")
            print(f"\n最终状态:")
            print(json.dumps(status, ensure_ascii=False, indent=2))
            
            # 尝试获取详细结果
            print(f"\n尝试获取详细结果...")
            try:
                results = requests.get(f'http://localhost:8002/batch/results/{batch_id}')
                if results.status_code == 200:
                    print(f"✓ 结果数据:")
                    result_data = results.json()
                    print(f"  Keys: {list(result_data.keys())}")
                    if 'final_state' in result_data:
                        print(f"  final_state keys: {list(result_data['final_state'].keys())}")
                else:
                    print(f"✗ 获取结果失败: {results.status_code}")
                    print(results.text)
            except Exception as e:
                print(f"✗ 异常: {e}")
            
            break
else:
    print(f"✗ 提交失败: {response.status_code}")
    print(response.text)

for f in files.values():
    if hasattr(f[1], 'close'):
        f[1].close()
