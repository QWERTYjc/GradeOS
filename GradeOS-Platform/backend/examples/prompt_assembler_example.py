"""
提示词拼装器使用示例

演示如何使用 PromptAssembler 动态构建提示词。
"""

import asyncio
from datetime import datetime
from src.services.prompt_assembler import PromptAssembler
from src.models.exemplar import Exemplar
from src.models.prompt import PromptSection


async def main():
    # 创建拼装器实例
    assembler = PromptAssembler()
    
    print("=" * 80)
    print("提示词拼装器示例")
    print("=" * 80)
    
    # 示例 1：基本拼装
    print("\n示例 1：基本拼装（只有系统模板和评分标准）")
    print("-" * 80)
    
    result1 = assembler.assemble(
        question_type="objective",
        rubric="选择题评分标准：正确得 5 分，错误得 0 分"
    )
    
    print(f"区段数量: {len(result1.sections)}")
    print(f"总 tokens: {result1.total_tokens}")
    print(f"截断区段: {result1.truncated_sections}")
    print(f"\n完整提示词（前 200 字符）:\n{result1.get_full_prompt()[:200]}...")
    
    # 示例 2：包含判例
    print("\n\n示例 2：包含判例的拼装")
    print("-" * 80)
    
    exemplars = [
        Exemplar(
            exemplar_id="ex1",
            question_type="objective",
            question_image_hash="hash1",
            student_answer_text="A",
            score=5.0,
            max_score=5.0,
            teacher_feedback="答案正确，选项 A 是标准答案",
            teacher_id="teacher1",
            confirmed_at=datetime.now(),
            usage_count=10,
            embedding=None
        ),
        Exemplar(
            exemplar_id="ex2",
            question_type="objective",
            question_image_hash="hash2",
            student_answer_text="B",
            score=0.0,
            max_score=5.0,
            teacher_feedback="答案错误，正确答案是 A",
            teacher_id="teacher1",
            confirmed_at=datetime.now(),
            usage_count=5,
            embedding=None
        )
    ]
    
    result2 = assembler.assemble(
        question_type="objective",
        rubric="选择题评分标准：正确得 5 分，错误得 0 分",
        exemplars=exemplars
    )
    
    print(f"区段数量: {len(result2.sections)}")
    print(f"总 tokens: {result2.total_tokens}")
    print(f"包含判例区段: {PromptSection.EXEMPLARS in result2.sections}")
    
    # 示例 3：包含错误引导和详细推理
    print("\n\n示例 3：低置信度场景（包含错误引导和详细推理提示）")
    print("-" * 80)
    
    result3 = assembler.assemble(
        question_type="stepwise",
        rubric="解答题评分标准：每步 2 分，共 10 分",
        error_patterns=[
            "学生经常在第二步出现计算错误",
            "注意单位换算",
            "检查符号是否正确"
        ],
        previous_confidence=0.7  # 低置信度，触发详细推理
    )
    
    print(f"区段数量: {len(result3.sections)}")
    print(f"总 tokens: {result3.total_tokens}")
    print(f"包含错误引导: {PromptSection.ERROR_GUIDANCE in result3.sections}")
    print(f"包含详细推理: {PromptSection.DETAILED_REASONING in result3.sections}")
    
    # 示例 4：包含校准配置
    print("\n\n示例 4：包含个性化校准配置")
    print("-" * 80)
    
    calibration = {
        "deduction_rules": {
            "计算错误": 2.0,
            "单位错误": 1.0,
            "格式错误": 0.5
        },
        "tolerance_rules": [
            {"rule_type": "numeric", "description": "数值容差 ±0.1"},
            {"rule_type": "unit", "description": "单位自动换算"}
        ],
        "strictness_level": 0.6
    }
    
    result4 = assembler.assemble(
        question_type="essay",
        rubric="论述题评分标准：内容 6 分，逻辑 2 分，表达 2 分",
        calibration=calibration
    )
    
    print(f"区段数量: {len(result4.sections)}")
    print(f"总 tokens: {result4.total_tokens}")
    print(f"包含校准配置: {PromptSection.CALIBRATION in result4.sections}")
    
    # 示例 5：测试截断功能
    print("\n\n示例 5：测试截断功能（限制 500 tokens）")
    print("-" * 80)
    
    long_rubric = "评分标准：" + "这是一个很长的评分标准。" * 100
    
    result5 = assembler.assemble(
        question_type="objective",
        rubric=long_rubric,
        exemplars=exemplars,
        error_patterns=["错误1", "错误2"] * 10,
        previous_confidence=0.7,
        calibration=calibration,
        max_tokens=500  # 限制 token 数
    )
    
    print(f"区段数量: {len(result5.sections)}")
    print(f"总 tokens: {result5.total_tokens}")
    print(f"截断区段: {result5.truncated_sections}")
    print(f"保留的区段: {list(result5.sections.keys())}")
    
    # 验证优先级
    print("\n优先级验证:")
    print(f"- SYSTEM 保留: {PromptSection.SYSTEM in result5.sections}")
    print(f"- RUBRIC 保留: {PromptSection.RUBRIC in result5.sections}")
    
    print("\n" + "=" * 80)
    print("示例完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
