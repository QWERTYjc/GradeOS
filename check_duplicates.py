#!/usr/bin/env python3
"""检查 Python 文件中的重复方法定义"""
import re

with open('GradeOS-Platform/backend/src/services/llm_reasoning.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print(f"文件总行数: {len(lines)}")

# 查找所有方法定义
method_pattern = re.compile(r'^\s*(async\s+)?def\s+(\w+)\s*\(')
methods = {}

for i, line in enumerate(lines, 1):
    match = method_pattern.match(line)
    if match:
        method_name = match.group(2)
        if method_name not in methods:
            methods[method_name] = []
        methods[method_name].append(i)

# 找出重复定义的方法
print("\n重复定义的方法:")
duplicates_found = False
for name, line_nums in sorted(methods.items()):
    if len(line_nums) > 1:
        duplicates_found = True
        print(f"  {name}: 行 {line_nums}")

if not duplicates_found:
    print("  无重复方法")

# 检查文件末尾是否有截断的代码
print(f"\n文件最后 5 行:")
for i, line in enumerate(lines[-5:], len(lines) - 4):
    print(f"  {i}: {line[:80]}")
