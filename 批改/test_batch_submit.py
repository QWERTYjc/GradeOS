"""测试批量批改提交"""
import requests
import os

# 检查文件
rubric_path = "批改标准.pdf"
student_path = "学生作答.pdf"

if not os.path.exists(rubric_path):
    print(f"错误: 找不到文件 {rubric_path}")
    exit(1)
    
if not os.path.exists(student_path):
    print(f"错误: 找不到文件 {student_path}")
    exit(1)

print(f"✓ 评分标准文件: {rubric_path} ({os.path.getsize(rubric_path)} bytes)")
print(f"✓ 学生作答文件: {student_path} ({os.path.getsize(student_path)} bytes)")
print("\n正在提交批量批改请求...")

# 准备文件
files = {
    'rubrics': ('批改标准.pdf', open(rubric_path, 'rb'), 'application/pdf'),
    'files': ('学生作答.pdf', open(student_path, 'rb'), 'application/pdf')
}

# 准备表单数据
data = {
    'auto_identify': 'true'
}

# 提交请求
try:
    response = requests.post(
        'http://localhost:8001/batch/submit',
        files=files,
        data=data,
        timeout=30
    )
    
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应内容:\n{response.text}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ 批次提交成功!")
        print(f"  批次ID: {result.get('batch_id')}")
        print(f"  状态: {result.get('status')}")
        print(f"  总页数: {result.get('total_pages')}")
        print(f"  预计完成时间: {result.get('estimated_completion_time')}秒")
    else:
        print(f"\n✗ 提交失败: {response.text}")
        
except Exception as e:
    print(f"\n✗ 请求异常: {e}")
finally:
    # 关闭文件
    for f in files.values():
        if hasattr(f[1], 'close'):
            f[1].close()
