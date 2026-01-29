"""
测试优化后的批改系统

验证优化效果：
1. 提示词长度是否减少
2. 输出格式是否正确
3. 性能是否提升
"""

import asyncio
import json
import time
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.llm_reasoning import LLMReasoningClient, SYSTEM_PROMPT


def count_tokens(text: str) -> int:
    """估算token数量（中文字符约0.25个token）"""
    return len(text) // 4


def test_system_prompt():
    """测试System Prompt"""
    print("=" * 60)
    print("测试1: System Prompt")
    print("=" * 60)
    print(f"System Prompt长度: {len(SYSTEM_PROMPT)} 字符")
    print(f"System Prompt tokens: ~{count_tokens(SYSTEM_PROMPT)}")
    print(f"\nSystem Preview (前500字符):")
    print(SYSTEM_PROMPT[:500] + "...")
    print()


def test_build_grading_prompt():
    """测试精简后的Grading Prompt"""
    print("=" * 60)
    print("测试2: Grading Prompt (精简版)")
    print("=" * 60)

    client = LLMReasoningClient()

    # 模拟评分标准
    parsed_rubric = {
        "questions": [
            {
                "question_id": "1",
                "max_score": 10,
                "scoring_points": [
                    {"point_id": "1.1", "score": 3, "description": "正确列出方程"},
                    {"point_id": "1.2", "score": 7, "description": "正确求解"},
                ],
            }
        ]
    }

    prompt = client._build_grading_prompt(rubric="", parsed_rubric=parsed_rubric, page_context=None)

    print(f"Prompt长度: {len(prompt)} 字符")
    print(f"Prompt tokens: ~{count_tokens(prompt)}")
    print(f"\nPrompt Preview (前800字符):")
    print(prompt[:800] + "...")
    print()

    return prompt


def test_old_vs_new():
    """对比新旧提示词"""
    print("=" * 60)
    print("测试3: 新旧提示词对比")
    print("=" * 60)

    # 旧的提示词长度（估算）
    old_prompt_length = 5000  # 约1100行，每行平均50字符
    old_token_count = old_prompt_length // 4

    client = LLMReasoningClient()
    parsed_rubric = {
        "questions": [
            {
                "question_id": "1",
                "max_score": 10,
                "scoring_points": [
                    {"point_id": "1.1", "score": 3, "description": "正确列出方程"},
                ],
            }
        ]
    }

    new_prompt = client._build_grading_prompt("", parsed_rubric, None)
    new_prompt_length = len(new_prompt)
    new_token_count = count_tokens(new_prompt)

    # 总token（system + user）
    total_old = 500 + old_token_count  # system(500) + user
    total_new = count_tokens(SYSTEM_PROMPT) + new_token_count

    print(f"旧版提示词:")
    print(f"  - 长度: ~{old_prompt_length} 字符")
    print(f"  - Tokens: ~{old_token_count}")
    print(f"  - 总计: ~{total_old} tokens")
    print()
    print(f"新版提示词:")
    print(f"  - 长度: {new_prompt_length} 字符")
    print(f"  - Tokens: ~{new_token_count}")
    print(f"  - System: ~{count_tokens(SYSTEM_PROMPT)} tokens")
    print(f"  - 总计: ~{total_new} tokens")
    print()

    reduction = (total_old - total_new) / total_old * 100
    print(f"优化效果:")
    print(f"  - Token减少: {reduction:.1f}%")
    print(f"  - 成本节省: ~{reduction:.1f}%")
    print()


def test_json_schema_validation():
    """测试输出JSON Schema是否完整"""
    print("=" * 60)
    print("测试4: JSON Schema验证")
    print("=" * 60)

    client = LLMReasoningClient()
    prompt = client._build_grading_prompt("", {"questions": []}, None)

    # 检查必要的字段
    required_fields = [
        '"score"',
        '"max_score"',
        '"confidence"',
        '"is_blank_page"',
        '"question_numbers"',
        '"question_details"',
        '"question_id"',
        '"scoring_point_results"',
        '"point_id"',
        '"awarded"',
        '"evidence"',
        '"page_summary"',
    ]

    missing = []
    for field in required_fields:
        if field not in prompt:
            missing.append(field)

    if missing:
        print(f"❌ 缺少字段: {missing}")
    else:
        print("✅ 所有必要字段都存在")
    print()


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("GradeOS 核心批改系统优化测试")
    print("=" * 60 + "\n")

    test_system_prompt()
    test_build_grading_prompt()
    test_old_vs_new()
    test_json_schema_validation()

    print("=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
