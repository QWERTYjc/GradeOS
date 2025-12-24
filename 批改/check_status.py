"""快速检查批次状态"""
import requests

batch_id = "160b764e-5247-4569-a706-ffb5c53137e3"

try:
    response = requests.get(f'http://localhost:8001/batch/status/{batch_id}')
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text}")
    
    if response.status_code == 200:
        import json
        data = response.json()
        print(f"\n解析后的数据:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"错误: {e}")
