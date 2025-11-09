#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行测试并保存所有 Agent 输出
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置环境变量
os.environ['OPENROUTER_API_KEY'] = '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'
os.environ['LLM_PROVIDER'] = 'openrouter'
os.environ['LLM_MODEL'] = 'google/gemini-2.0-flash-exp:free'
os.environ['DATABASE_TYPE'] = 'json'

# 输出文件
output_file = Path('agent_outputs.md')
json_file = Path('agent_outputs.json')

class OutputCollector:
    """收集所有输出"""
    
    def __init__(self):
        self.outputs = []
        self.start_time = time.time()
    
    def log(self, message):
        """记录日志"""
        elapsed = time.time() - self.start_time
        timestamp = datetime.now().strftime('%H:%M:%S')
        entry = {
            'timestamp': timestamp,
            'elapsed': f"{elapsed:.2f}s",
            'message': message
        }
        self.outputs.append(entry)
        print(f"[{timestamp}] {message}")
    
    def save_to_markdown(self, filepath):
        """保存为 Markdown"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# AI 批改系统 - Agent 输出汇总\n\n")
            f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**配置信息**:\n")
            f.write(f"- LLM Provider: {os.getenv('LLM_PROVIDER')}\n")
            f.write(f"- LLM Model: {os.getenv('LLM_MODEL')}\n")
            f.write(f"- Database: {os.getenv('DATABASE_TYPE')}\n\n")
            f.write("---\n\n")
            
            for entry in self.outputs:
                f.write(f"**[{entry['timestamp']}]** ({entry['elapsed']}) {entry['message']}\n\n")
    
    def save_to_json(self, filepath):
        """保存为 JSON"""
        data = {
            'test_time': datetime.now().isoformat(),
            'config': {
                'llm_provider': os.getenv('LLM_PROVIDER'),
                'llm_model': os.getenv('LLM_MODEL'),
                'database': os.getenv('DATABASE_TYPE')
            },
            'outputs': self.outputs
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def create_test_files():
    """创建测试文件"""
    test_dir = Path('test_data')
    test_dir.mkdir(exist_ok=True)
    
    # 创建题目文件
    question_file = test_dir / 'questions.txt'
    with open(question_file, 'w', encoding='utf-8') as f:
        f.write("""1. 计算 2 + 3 = ?
A. 4
B. 5
C. 6
D. 7

2. 填空：中国的首都是_____。

3. 简答题：请简述Python的主要特点。（至少3点）

4. 计算题：求解方程 x + 5 = 10，并写出解题步骤。
""")
    
    # 创建答案文件
    answer_file = test_dir / '001_张三_answers.txt'
    with open(answer_file, 'w', encoding='utf-8') as f:
        f.write("""1. B

2. 北京

3. Python是一种高级编程语言，具有以下特点：
   - 语法简洁易读
   - 支持多种编程范式
   - 拥有丰富的标准库和第三方库

4. 解：
   x + 5 = 10
   x = 10 - 5
   x = 5
""")
    
    # 创建评分标准文件
    marking_file = test_dir / 'marking_scheme.txt'
    with open(marking_file, 'w', encoding='utf-8') as f:
        f.write("""评分标准：

1. 选择题 (2分)
   - 选对得2分
   - 选错得0分

2. 填空题 (2分)
   - 答案正确得2分
   - 答案错误得0分

3. 简答题 (3分)
   - 提到"高级语言"得1分
   - 提到"语法简洁"得1分
   - 提到"丰富的库"得1分

4. 计算题 (3分)
   - 列出方程得1分
   - 计算过程正确得1分
   - 答案正确得1分
""")
    
    return str(question_file), str(answer_file), str(marking_file)


def main():
    """主函数"""
    collector = OutputCollector()
    
    collector.log("=" * 80)
    collector.log("🚀 AI 批改系统测试开始")
    collector.log("=" * 80)
    
    # 测试 LLM 连接
    collector.log("\n📡 步骤 1: 测试 LLM 连接")
    collector.log("-" * 80)
    
    try:
        from functions.llm_client import get_llm_client
        
        client = get_llm_client()
        collector.log(f"✅ LLM Client 创建成功")
        collector.log(f"   Provider: {client.provider}")
        collector.log(f"   Model: {client.model}")
        collector.log(f"   Base URL: {client.base_url}")
        
        # 测试调用
        collector.log("\n📡 测试 API 调用...")
        messages = [{"role": "user", "content": "请用一句话介绍 Python。"}]
        
        start_time = time.time()
        response = client.chat(messages)
        elapsed = time.time() - start_time
        
        collector.log(f"✅ API 调用成功！")
        collector.log(f"   耗时: {elapsed:.2f}秒")
        collector.log(f"   响应: {response[:100]}...")
        
    except Exception as e:
        collector.log(f"❌ LLM 连接失败: {e}")
        import traceback
        collector.log(traceback.format_exc())
    
    # 创建测试文件
    collector.log("\n📁 步骤 2: 创建测试文件")
    collector.log("-" * 80)
    
    question_file, answer_file, marking_file = create_test_files()
    collector.log(f"✅ 测试文件已创建")
    collector.log(f"   题目文件: {question_file}")
    collector.log(f"   答案文件: {answer_file}")
    collector.log(f"   评分标准: {marking_file}")
    
    # 运行工作流
    collector.log("\n🚀 步骤 3: 运行批改工作流")
    collector.log("=" * 80)
    
    try:
        from functions.langgraph.workflow_production import run_grading_workflow
        
        node_count = 0
        final_state = None
        
        for output in run_grading_workflow(
            question_files=[question_file],
            answer_files=[answer_file],
            marking_files=[marking_file],
            stream=True
        ):
            for node_name, node_state in output.items():
                node_count += 1
                
                collector.log(f"\n⚡ Agent #{node_count}: {node_name}")
                collector.log("-" * 80)
                
                # 详细记录每个节点的状态
                if node_name == 'parse_input':
                    status = node_state.get('parse_status', 'unknown')
                    questions = node_state.get('questions', [])
                    answers = node_state.get('answers', [])
                    
                    collector.log(f"📊 状态: {status}")
                    collector.log(f"📝 解析结果:")
                    collector.log(f"   - 题目数量: {len(questions)}")
                    collector.log(f"   - 答案数量: {len(answers)}")
                    
                    for q in questions:
                        collector.log(f"   - 题目 {q['id']}: {q.get('text', '')[:50]}...")
                    
                elif node_name == 'analyze_questions':
                    status = node_state.get('analysis_status', 'unknown')
                    questions = node_state.get('questions', [])
                    
                    collector.log(f"📊 状态: {status}")
                    collector.log(f"🔍 分析结果:")
                    
                    for q in questions:
                        analysis = q.get('analysis', {})
                        collector.log(f"   - 题目 {q['id']}:")
                        collector.log(f"     类型: {q.get('type')}")
                        collector.log(f"     难度: {analysis.get('difficulty')}")
                        collector.log(f"     策略: {analysis.get('strategy')}")
                        collector.log(f"     关键词: {analysis.get('keywords', [])}")
                
                elif node_name == 'interpret_rubric':
                    status = node_state.get('rubric_status', 'unknown')
                    rubric = node_state.get('rubric_interpretation', {})
                    
                    collector.log(f"📊 状态: {status}")
                    collector.log(f"📋 评分标准解析:")
                    
                    for qid, criteria in rubric.items():
                        collector.log(f"   - 题目 {qid}:")
                        for criterion in criteria:
                            collector.log(f"     * {criterion.get('description')}: {criterion.get('points')}分")
                
                elif node_name == 'grade_questions':
                    status = node_state.get('grading_status', 'unknown')
                    results = node_state.get('grading_results', [])
                    
                    collector.log(f"📊 状态: {status}")
                    collector.log(f"✍️  批改结果:")
                    collector.log(f"   - 已批改题目数: {len(results)}")
                    
                    for r in results:
                        collector.log(f"   - 题目 {r['question_id']}:")
                        collector.log(f"     得分: {r['score']}/{r['max_score']}")
                        collector.log(f"     策略: {r.get('strategy')}")
                        collector.log(f"     反馈: {r.get('feedback', 'N/A')}")
                        if 'errors' in r and r['errors']:
                            collector.log(f"     错误: {r['errors']}")
                        if 'suggestions' in r and r['suggestions']:
                            collector.log(f"     建议: {r['suggestions']}")
                
                elif node_name == 'aggregate_results':
                    status = node_state.get('aggregation_status', 'unknown')
                    aggregated = node_state.get('aggregated_results', {})
                    
                    collector.log(f"📊 状态: {status}")
                    collector.log(f"📈 汇总结果:")
                    collector.log(f"   - 总分: {aggregated.get('total_score')}/{aggregated.get('max_score')}")
                    collector.log(f"   - 得分率: {aggregated.get('percentage', 0):.1f}%")
                    collector.log(f"   - 等级: {aggregated.get('grade')}")
                    
                    errors = aggregated.get('error_analysis', [])
                    if errors:
                        collector.log(f"   - 错误分析:")
                        for err in errors:
                            collector.log(f"     * {err.get('description')}")
                    
                    knowledge = aggregated.get('knowledge_points', {})
                    if knowledge:
                        collector.log(f"   - 知识点掌握:")
                        for kp, mastery in knowledge.items():
                            collector.log(f"     * {kp}: {mastery:.1f}%")
                
                elif node_name == 'persist_data':
                    status = node_state.get('persistence_status', 'unknown')
                    
                    collector.log(f"📊 状态: {status}")
                    collector.log(f"💾 数据已持久化")
                
                final_state = node_state
        
        total_time = time.time() - collector.start_time
        
        collector.log("\n" + "=" * 80)
        collector.log(f"✅ 批改完成！")
        collector.log(f"⏱️  总耗时: {total_time:.2f}秒")
        collector.log(f"📊 处理节点数: {node_count}")
        collector.log(f"⚡ 平均每节点: {total_time/node_count:.2f}秒")
        collector.log("=" * 80)
        
    except Exception as e:
        collector.log(f"\n❌ 工作流测试失败: {e}")
        import traceback
        collector.log(traceback.format_exc())
    
    # 保存输出
    collector.log("\n💾 保存输出到文件...")
    collector.save_to_markdown(output_file)
    collector.save_to_json(json_file)
    
    collector.log(f"✅ Markdown 输出已保存: {output_file.absolute()}")
    collector.log(f"✅ JSON 输出已保存: {json_file.absolute()}")
    
    print("\n" + "=" * 80)
    print("🎉 测试完成！请查看以下文件：")
    print(f"   - {output_file.absolute()}")
    print(f"   - {json_file.absolute()}")
    print("=" * 80)


if __name__ == '__main__':
    main()

