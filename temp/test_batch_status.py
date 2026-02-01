import requests
import json
import sys

# Set UTF-8 output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

batch_id = "d48df4d3-e3f8-4e25-9792-77a62ee50a6f"
url = f"https://gradeos-production.up.railway.app/api/batch/status/{batch_id}"

print(f"获取批处理状态: {batch_id}\n")

r = requests.get(url, timeout=30)
print(f"HTTP Status: {r.status_code}\n")

if r.status_code == 200:
    data = r.json()
    
    print("=" * 60)
    print("批处理状态详情")
    print("=" * 60)
    print(f"状态: {data.get('status', 'N/A')}")
    print(f"当前阶段: {data.get('current_stage', 'N/A')}")
    print(f"进度: {data.get('progress', 0) * 100}%")
    print(f"总页数: {data.get('total_pages', 'N/A')}")
    print()
    
    # 检查是否有错误
    if 'error' in data:
        print("[ERROR] 错误信息:")
        print(f"  {data['error']}")
        print()
    
    # 检查阶段详情
    if 'stages' in data:
        print("=" * 60)
        print("阶段详情")
        print("=" * 60)
        for stage_name, stage_info in data.get('stages', {}).items():
            print(f"\n{stage_name}:")
            print(f"  状态: {stage_info.get('status', 'N/A')}")
            if 'progress' in stage_info:
                print(f"  进度: {stage_info['progress'] * 100}%")
            if 'message' in stage_info:
                print(f"  消息: {stage_info['message']}")
    
    # 保存完整状态
    with open('d:/project/GradeOS/temp/batch_status_full.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("\n完整状态已保存到: temp/batch_status_full.json")
else:
    print(f"错误: {r.text}")
