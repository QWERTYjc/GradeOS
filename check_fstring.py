#!/usr/bin/env python3
"""检查 Python 3.11 不兼容的 f-string 语法"""
import re

with open('GradeOS-Platform/backend/src/services/llm_reasoning.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# 查找 f-string 中包含反斜杠的模式
# Python 3.11 不允许 f-string 表达式部分包含反斜杠
issues = []
for i, line in enumerate(lines, 1):
    # 检查 f"...{...\\n...}..." 这种模式
    if 'f"' in line or "f'" in line:
        # 检查是否有 {xxx\n} 这种在花括号内的反斜杠
        if re.search(r'\{[^}]*\\[nrt][^}]*\}', line):
            issues.append((i, line.strip()[:100]))

if issues:
    print(f"发现 {len(issues)} 个潜在问题:")
    for line_num, content in issues:
        print(f"  Line {line_num}: {content}")
else:
    print("未发现 f-string 反斜杠问题")

# 额外检查：尝试用 compile 验证语法
print("\n尝试编译文件...")
try:
    compile(content, 'llm_reasoning.py', 'exec')
    print("✅ 语法检查通过")
except SyntaxError as e:
    print(f"❌ 语法错误: {e}")
    print(f"   行号: {e.lineno}")
    print(f"   内容: {lines[e.lineno-1] if e.lineno else 'N/A'}")
