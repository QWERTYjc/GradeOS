"""测试真实的批量批改（使用真实PDF）"""
import requests
import time
import json

print("=" * 80)
print("测试真实批量批改")
print("=" * 80)

# 提交批量批改
print("\n1. 提交批量批改请求...")
files = {
    'rubrics': ('批改标准.pdf', open('批改标准.pdf', 'rb'), 'application/pdf'),
    'files': ('学生作答.pdf', open('学生作答.pdf', 'rb'), 'application/pdf')
}
data = {'auto_identify': 'true'}

response = requests.post(
    'http://localhost:8001/batch/submit',
    files=files,
    data=data,
    timeout=30
)

print(f"响应状态码: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    batch_id = result['batch_id']
    print(f"✓ 批次ID: {batch_id}")
    print(f"✓ 总页数: {result['total_pages']}")
    
    # 等待几秒让工作流程启动
    print("\n2. 等待5秒让工作流程启动...")
    time.sleep(5)
    
    # 查询状态
    print("\n3. 查询批次状态...")
    for i in range(5):
        status_response = requests.get(f'http://localhost:8001/batch/status/{batch_id}')
        if status_response.status_code == 200:
            status = status_response.json()
            print(f"\n迭代 {i+1}:")
            print(json.dumps(status, ensure_ascii=False, indent=2))
        time.sleep(3)
    
    # 检查后端日志
    print("\n4. 检查后端是否有错误...")
    print("请查看后端进程输出")
    
else:
    print(f"✗ 提交失败: {response.text}")

# 关闭文件
for f in files.values():
    if hasattr(f[1], 'close'):
        f[1].close()
