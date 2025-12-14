#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查批改结果文件"""

import json
from pathlib import Path

result_dir = Path('correction_results')
if result_dir.exists():
    files = sorted([f for f in result_dir.glob('*.json')], key=lambda x: x.stat().st_mtime, reverse=True)
    if files:
        latest = files[0]
        print(f"最新结果文件: {latest.name}")
        with open(latest, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n评分点数量: {len(data.get('criteria_evaluations', []))}")
        print(f"总分: {data.get('total_score', 0)}")
        
        # 统计题目
        questions = set()
        for e in data.get('criteria_evaluations', []):
            criterion_id = e.get('criterion_id', '')
            if '_' in criterion_id:
                qid = criterion_id.split('_')[0]
                questions.add(qid)
        
        print(f"题目数量: {len(questions)}")
        if questions:
            print(f"题目列表: {sorted(questions)}")
        
        # 检查评分标准解析结果
        if 'rubric_parsing_result' in data:
            rubric = data['rubric_parsing_result']
            print(f"\n评分标准解析:")
            print(f"  评分点数量: {rubric.get('criteria_count', 0)}")
            print(f"  总分: {rubric.get('total_points', 0)}")
            
            criteria = rubric.get('criteria', [])
            if criteria:
                rubric_questions = set()
                for c in criteria:
                    qid = c.get('question_id', '')
                    if qid:
                        rubric_questions.add(qid)
                print(f"  题目数量: {len(rubric_questions)}")
                if rubric_questions:
                    print(f"  题目列表: {sorted(rubric_questions)}")
    else:
        print("未找到结果文件")
else:
    print("结果目录不存在")








