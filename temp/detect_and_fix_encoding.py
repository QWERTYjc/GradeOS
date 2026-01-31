#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检测并修复编码问题"""

import json
import chardet

# 读取原始字节
file_path = 'temp/latest_grading_result.json'
with open(file_path, 'rb') as f:
    raw_bytes = f.read()

# 检测编码
detected = chardet.detect(raw_bytes)
print(f"检测到的编码: {detected}")

# 尝试不同的编码方式读取
encodings_to_try = [
    detected['encoding'],
    'utf-8',
    'utf-8-sig',  # UTF-8 with BOM
    'gbk',
    'gb2312',
    'latin1',
    'cp1252'
]

content = None
used_encoding = None

for encoding in encodings_to_try:
    if not encoding:
        continue
    try:
        content = raw_bytes.decode(encoding)
        used_encoding = encoding
        print(f"✓ 成功使用 {encoding} 解码")
        break
    except Exception as e:
        print(f"✗ {encoding} 解码失败: {e}")

if not content:
    print("无法解码文件")
    exit(1)

# 解析 JSON
try:
    data = json.loads(content)
    print(f"✓ JSON 解析成功，使用编码: {used_encoding}")
    
    # 检查是否需要修复编码
    sample_text = None
    if 'selfAudit' in data and 'issues' in data['selfAudit']:
        issues = data['selfAudit']['issues']
        if issues and 'message' in issues[0]:
            sample_text = issues[0]['message']
    
    if sample_text:
        print(f"\n原始文本示例: {sample_text[:50]}")
        
        # 如果看起来像乱码，尝试修复
        if '棰' in sample_text or '鐩' in sample_text:
            print("检测到乱码，尝试修复...")
            
            def fix_mojibake(text):
                """修复乱码"""
                try:
                    # UTF-8 被错误解释为 GBK/GB2312
                    return text.encode('gbk').decode('utf-8')
                except:
                    try:
                        return text.encode('latin1').decode('utf-8')
                    except:
                        return text
            
            def fix_json_encoding(obj):
                """递归修复"""
                if isinstance(obj, str):
                    return fix_mojibake(obj)
                elif isinstance(obj, dict):
                    return {key: fix_json_encoding(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [fix_json_encoding(item) for item in obj]
                else:
                    return obj
            
            fixed_data = fix_json_encoding(data)
            
            # 验证修复
            if 'selfAudit' in fixed_data and 'issues' in fixed_data['selfAudit']:
                issues = fixed_data['selfAudit']['issues']
                if issues and 'message' in issues[0]:
                    fixed_sample = issues[0]['message']
                    print(f"修复后文本示例: {fixed_sample[:50]}")
            
            data = fixed_data
    
    # 保存修复后的文件
    output_file = 'temp/latest_grading_result_fixed.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 修复后的文件已保存到: {output_file}")
    
    # 显示一些关键信息
    print(f"\n=== 批改结果摘要 ===")
    print(f"学生: {data.get('studentKey', 'N/A')}")
    print(f"得分: {data.get('score', 0)}/{data.get('maxScore', 0)}")
    
    if 'selfAudit' in data and 'issues' in data['selfAudit']:
        issues = data['selfAudit']['issues']
        print(f"\n发现 {len(issues)} 个问题，前3条：")
        for i, issue in enumerate(issues[:3]):
            print(f"  {i+1}. {issue.get('message', '')}")

except Exception as e:
    print(f"✗ 处理失败: {e}")
    import traceback
    traceback.print_exc()
