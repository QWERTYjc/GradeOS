#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取 UTF-16 编码的 JSON 文件"""

import json

file_path = 'temp/latest_grading_result.json'

# 尝试 UTF-16 编码
try:
    with open(file_path, 'r', encoding='utf-16') as f:
        content = f.read()
    
    data = json.loads(content)
    print("✓ 成功使用 UTF-16 读取文件")
    
    # 保存为标准 UTF-8 格式
    output = 'temp/latest_grading_result_utf8.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 已转换为 UTF-8 并保存到: {output}")
    
    # 显示关键信息
    print(f"\n=== 批改结果摘要 ===")
    print(f"学生: {data.get('studentName', data.get('studentKey', 'N/A'))}")
    print(f"得分: {data.get('score', 0)}/{data.get('maxScore', 0)}")
    print(f"页面范围: {data.get('pageRange', 'N/A')}")
    
    # 显示自审问题
    if 'selfAudit' in data:
        audit = data['selfAudit']
        if 'summary' in audit:
            print(f"\n自审摘要: {audit['summary'][:150]}...")
        if 'issues' in audit:
            issues = audit['issues']
            print(f"\n发现 {len(issues)} 个问题（前5条）：")
            for i, issue in enumerate(issues[:5]):
                msg = issue.get('message', '')
                issue_type = issue.get('issue_type', '')
                q_id = issue.get('question_id', '')
                print(f"  {i+1}. [题目{q_id}] {msg} ({issue_type})")
    
    # 显示学生总结
    if 'studentSummary' in data:
        summary = data['studentSummary']
        if 'overall' in summary:
            print(f"\n学生总体评价: {summary['overall'][:150]}...")
        
        # 显示知识点掌握情况统计
        if 'knowledge_points' in summary:
            kps = summary['knowledge_points']
            mastered = sum(1 for kp in kps if kp.get('mastery_level') == 'mastered')
            weak = sum(1 for kp in kps if kp.get('mastery_level') == 'weak')
            print(f"\n知识点统计: 共 {len(kps)} 个，掌握 {mastered} 个，薄弱 {weak} 个")

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
