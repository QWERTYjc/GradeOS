import requests
import json

# 获取第一个批处理任务的完整结果
batch_id = "d48df4d3-e3f8-4e25-9792-77a62ee50a6f"
url = f"https://gradeos-production.up.railway.app/api/batch/full-results/{batch_id}"

print(f"正在获取批处理结果: {batch_id}\n")

r = requests.get(url, timeout=30)
print(f"HTTP Status: {r.status_code}\n")

if r.status_code == 200:
    data = r.json()
    
    # 关键指标
    print("=" * 60)
    print("关键指标汇总")
    print("=" * 60)
    print(f"总学生数 (total_students): {data.get('total_students', 'N/A')}")
    print(f"题目数量: {len(data.get('questions', []))}")
    print(f"学生列表长度: {len(data.get('students', []))}")
    print(f"状态: {data.get('status', 'N/A')}")
    print()
    
    # 题目列表
    questions = data.get('questions', [])
    if questions:
        print("=" * 60)
        print(f"题目列表 (共 {len(questions)} 题)")
        print("=" * 60)
        for i, q in enumerate(questions):
            print(f"题目 {i+1}:")
            print(f"  - 题号: {q.get('question_number', 'N/A')}")
            print(f"  - 标题: {q.get('question_title', 'N/A')}")
            print(f"  - 总分: {q.get('max_score', 'N/A')}")
            print()
    
    # 学生列表
    students = data.get('students', [])
    if students:
        print("=" * 60)
        print(f"学生列表 (共 {len(students)} 人)")
        print("=" * 60)
        for i, student in enumerate(students[:3]):  # 只显示前3个学生
            print(f"学生 {i+1}:")
            print(f"  - ID: {student.get('student_id', 'N/A')}")
            print(f"  - 总分: {student.get('total_score', 'N/A')}")
            grades = student.get('grades', [])
            print(f"  - 已批改题目数: {len(grades)}")
            print()
        if len(students) > 3:
            print(f"... 还有 {len(students) - 3} 个学生\n")
    
    # 保存完整数据
    with open('d:/project/GradeOS/temp/batch_results_full.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("完整结果已保存到: temp/batch_results_full.json")
    
else:
    print(f"错误: {r.text}")
