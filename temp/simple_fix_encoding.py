#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单的编码修复脚本"""

import json

file_path = 'temp/latest_grading_result.json'

# 尝试不同的编码读取
encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'latin1', 'cp1252']

data = None
for enc in encodings:
    try:
        with open(file_path, 'r', encoding=enc) as f:
            content = f.read()
        data = json.loads(content)
        print(f"✓ 成功使用 {enc} 读取文件")
        break
    except Exception as e:
        print(f"✗ {enc} 失败: {str(e)[:50]}")

if not data:
    print("无法读取文件")
    exit(1)

# 检查是否有乱码
sample = data.get('studentKey', '')
print(f"\n学生姓名（原始）: {sample}")

if '瀛' in sample or '棰' in sample:
    print("检测到乱码，尝试修复...")
    
    def fix_text(text):
        """修复乱码文本"""
        if not isinstance(text, str):
            return text
        try:
            # 尝试 GBK -> UTF-8 修复
            return text.encode('gbk').decode('utf-8')
        except:
            try:
                # 尝试 Latin1 -> UTF-8 修复
                return text.encode('latin1').decode('utf-8')
            except:
                return text
    
    def fix_obj(obj):
        """递归修复对象"""
        if isinstance(obj, str):
            return fix_text(obj)
        elif isinstance(obj, dict):
            return {k: fix_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [fix_obj(item) for item in obj]
        else:
            return obj
    
    fixed_data = fix_obj(data)
    print(f"学生姓名（修复后）: {fixed_data.get('studentKey', '')}")
    data = fixed_data

# 保存修复后的文件
output = 'temp/latest_grading_result_fixed.json'
with open(output, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✓ 已保存到: {output}")

# 显示摘要
print(f"\n=== 批改结果 ===")
print(f"学生: {data.get('studentName', data.get('studentKey', 'N/A'))}")
print(f"得分: {data.get('score', 0)}/{data.get('maxScore', 0)}")

if 'selfAudit' in data:
    audit = data['selfAudit']
    if 'summary' in audit:
        print(f"\n审核摘要: {audit['summary'][:100]}...")
    if 'issues' in audit:
        print(f"\n发现 {len(audit['issues'])} 个问题（前3条）：")
        for i, issue in enumerate(audit['issues'][:3]):
            print(f"  {i+1}. {issue.get('message', '')}")
