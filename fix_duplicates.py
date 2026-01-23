#!/usr/bin/env python3
"""修复 llm_reasoning.py 中的重复方法定义"""
import re

filepath = 'GradeOS-Platform/backend/src/services/llm_reasoning.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print(f"原始文件行数: {len(lines)}")

# 找到第一个重复区域的开始位置
# 根据检查结果，重复从大约 1736 行开始
# 我们需要找到 assist_from_evidence 方法的第一个定义结束位置

# 查找 assist_from_evidence 的所有定义位置
assist_positions = []
for i, line in enumerate(lines):
    if re.match(r'\s*async def assist_from_evidence\s*\(', line):
        assist_positions.append(i)

print(f"assist_from_evidence 定义位置: {assist_positions}")

if len(assist_positions) >= 2:
    # 找到第一个 assist_from_evidence 方法的结束位置
    # 它应该在第二个定义之前
    first_assist_end = assist_positions[1]
    
    # 向前查找，找到第一个 assist_from_evidence 方法体的结束
    # 我们需要保留到 _safe_float 方法之前的所有内容
    
    # 查找 _safe_float 的位置
    safe_float_positions = []
    for i, line in enumerate(lines):
        if re.match(r'\s*def _safe_float\s*\(', line):
            safe_float_positions.append(i)
    
    print(f"_safe_float 定义位置: {safe_float_positions}")
    
    if safe_float_positions:
        # 保留从开始到第一个 _safe_float 之前的内容
        # 然后从 _safe_float 开始到文件结束
        
        # 找到第一个重复块的开始（第二个 _call_text_api 定义之前）
        call_text_api_positions = []
        for i, line in enumerate(lines):
            if re.match(r'\s*async def _call_text_api\s*\(', line):
                call_text_api_positions.append(i)
        
        print(f"_call_text_api 定义位置: {call_text_api_positions}")
        
        if len(call_text_api_positions) >= 2:
            # 第一个重复块从第二个 _call_text_api 开始
            # 我们需要删除从第二个 _call_text_api 到 _safe_float 之前的内容
            
            # 策略：保留 0 到 call_text_api_positions[1]-1
            # 然后保留 safe_float_positions[0] 到结束
            
            first_part = lines[:call_text_api_positions[1]]
            second_part = lines[safe_float_positions[0]:]
            
            new_lines = first_part + second_part
            print(f"新文件行数: {len(new_lines)}")
            
            # 写入修复后的文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            
            print("文件已修复！")
        else:
            print("未找到足够的 _call_text_api 定义")
    else:
        print("未找到 _safe_float 定义")
else:
    print("未找到重复的 assist_from_evidence 定义")
