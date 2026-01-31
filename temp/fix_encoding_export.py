#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复编码问题并重新导出 JSON"""

import json

# 读取乱码的 JSON 文件
with open('temp/latest_grading_result.json', 'r', encoding='utf-8') as f:
    content = f.read()

# 尝试修复编码：将错误解释的字符串转回正确的 UTF-8
def fix_mojibake(text):
    """修复乱码文本"""
    try:
        # 常见的乱码模式：UTF-8 被错误解释为 Latin-1/ISO-8859-1
        # 然后再被当作 UTF-8 读取
        return text.encode('latin1').decode('utf-8')
    except:
        return text

# 递归修复 JSON 对象中的所有字符串
def fix_json_encoding(obj):
    """递归修复 JSON 对象中的编码问题"""
    if isinstance(obj, str):
        return fix_mojibake(obj)
    elif isinstance(obj, dict):
        return {key: fix_json_encoding(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [fix_json_encoding(item) for item in obj]
    else:
        return obj

# 解析 JSON
try:
    data = json.loads(content)
    print("✓ JSON 解析成功")
    
    # 修复编码
    fixed_data = fix_json_encoding(data)
    
    # 保存修复后的文件
    output_file = 'temp/latest_grading_result_fixed.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(fixed_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 修复后的文件已保存到: {output_file}")
    
    # 显示一些示例
    if 'selfAudit' in fixed_data and 'issues' in fixed_data['selfAudit']:
        issues = fixed_data['selfAudit']['issues']
        if issues:
            print(f"\n示例修复结果（前3条）：")
            for i, issue in enumerate(issues[:3]):
                print(f"  {i+1}. {issue.get('message', '')}")
    
    if 'studentKey' in fixed_data:
        print(f"\n学生姓名: {fixed_data['studentKey']}")
    
    if 'studentSummary' in fixed_data and 'overall' in fixed_data['studentSummary']:
        print(f"\n总体评价: {fixed_data['studentSummary']['overall'][:100]}...")

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
