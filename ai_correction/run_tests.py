#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行多次测试并汇总结果
"""

import asyncio
import sys
import os
from pathlib import Path

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from functions.langgraph.agents.rubric_interpreter_agent import RubricInterpreterAgent
from functions.file_processor import process_multimodal_file


async def run_single_test(test_num):
    """运行单次测试"""
    
    print(f"\n{'='*80}")
    print(f"测试 {test_num}/5")
    print(f"{'='*80}")
    
    # 1. 加载批改标准 PDF
    pdf_path = "批改标准.pdf"
    if not os.path.exists(pdf_path):
        print(f"错误：找不到文件 {pdf_path}")
        return None
    
    # 2. 转换 PDF 为图片
    multimodal_file = process_multimodal_file(pdf_path, prefer_vision=True)
    
    if multimodal_file['modality_type'] != 'pdf_image':
        print(f"错误：PDF 文件未转换为图片格式")
        return None
    
    pages = multimodal_file['content_representation'].get('pages', [])
    
    if not pages:
        print(f"错误：PDF 转换后没有页面数据")
        return None
    
    # 3. 调用 RubricInterpreterAgent 解析
    agent = RubricInterpreterAgent()
    rubric_understanding = await agent._extract_and_parse_rubric_from_images(pages)
    
    # 4. 提取关键信息
    total_points = rubric_understanding['total_points']
    num_criteria = len(rubric_understanding['criteria'])
    
    print(f"\n总分: {total_points} 分")
    print(f"评分点数量: {num_criteria} 个")
    
    return {
        'total_points': total_points,
        'num_criteria': num_criteria
    }


async def main():
    """运行多次测试"""
    
    print("="*80)
    print("开始运行 5 次测试，验证分值识别的稳定性")
    print("="*80)
    
    results = []
    
    for i in range(1, 6):
        result = await run_single_test(i)
        if result:
            results.append(result)
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    if not results:
        print("所有测试都失败了")
        return
    
    total_points_list = [r['total_points'] for r in results]
    num_criteria_list = [r['num_criteria'] for r in results]
    
    print(f"\n总分结果: {total_points_list}")
    print(f"评分点数量结果: {num_criteria_list}")
    
    # 检查一致性
    if len(set(total_points_list)) == 1:
        print(f"\n✅ 总分稳定一致: {total_points_list[0]} 分")
    else:
        print(f"\n❌ 总分不一致: {set(total_points_list)}")
    
    if len(set(num_criteria_list)) == 1:
        print(f"✅ 评分点数量稳定一致: {num_criteria_list[0]} 个")
    else:
        print(f"❌ 评分点数量不一致: {set(num_criteria_list)}")
    
    # 检查是否都是 105 分
    if all(p == 105.0 for p in total_points_list):
        print(f"\n🎉 完美！所有 {len(results)} 次测试都稳定输出 105 分！")
    else:
        print(f"\n⚠️  警告：总分不是 105 分")


if __name__ == "__main__":
    asyncio.run(main())

