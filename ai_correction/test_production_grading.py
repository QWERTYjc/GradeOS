#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产级批改系统测试脚本
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


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

3. 简答题：请简述Python的主要特点。

4. 计算题：求解方程 x + 5 = 10
""")
    
    # 创建答案文件
    answer_file = test_dir / '001_张三_answers.txt'
    with open(answer_file, 'w', encoding='utf-8') as f:
        f.write("""1. B

2. 北京

3. Python是一种高级编程语言，具有简洁易读的语法，支持多种编程范式，拥有丰富的标准库和第三方库。

4. x = 5
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
    
    print(f"✅ 测试文件已创建在 {test_dir.absolute()}")
    
    return str(question_file), str(answer_file), str(marking_file)


def test_input_parser():
    """测试输入解析"""
    print("\n🧪 测试 InputParser Agent...")
    
    from functions.langgraph.agents.input_parser import InputParserAgent
    
    question_file, answer_file, marking_file = create_test_files()
    
    parser = InputParserAgent()
    
    state = {
        'question_files': [question_file],
        'answer_files': [answer_file],
        'marking_files': [marking_file]
    }
    
    result = parser.parse(state)
    
    print(f"解析状态: {result.get('parse_status')}")
    print(f"题目数量: {len(result.get('questions', []))}")
    print(f"答案数量: {len(result.get('answers', []))}")
    print(f"学生信息: {result.get('student_info')}")
    
    if result.get('parse_status') == 'success':
        print("✅ InputParser 测试通过")
        return result
    else:
        print(f"❌ InputParser 测试失败: {result.get('parse_errors')}")
        return None


def test_question_analyzer(state):
    """测试题目分析"""
    print("\n🧪 测试 QuestionAnalyzer Agent...")
    
    from functions.langgraph.agents.question_analyzer import QuestionAnalyzerAgent
    
    analyzer = QuestionAnalyzerAgent()
    result = analyzer.analyze(state)
    
    print(f"分析状态: {result.get('analysis_status')}")
    
    for q in result.get('questions', []):
        analysis = q.get('analysis', {})
        print(f"题目 {q['id']}: 类型={q['type']}, 难度={analysis.get('difficulty')}, 策略={analysis.get('strategy')}")
    
    if result.get('analysis_status') == 'success':
        print("✅ QuestionAnalyzer 测试通过")
        return result
    else:
        print(f"❌ QuestionAnalyzer 测试失败")
        return None


def test_question_grader(state):
    """测试题目批改"""
    print("\n🧪 测试 QuestionGrader Agent...")
    
    from functions.langgraph.agents.question_analyzer import QuestionGraderAgent
    
    grader = QuestionGraderAgent()
    result = grader.grade(state)
    
    print(f"批改状态: {result.get('grading_status')}")
    
    for gr in result.get('grading_results', []):
        print(f"题目 {gr['question_id']}: {gr['score']}/{gr['max_score']} 分 - {gr.get('feedback', '')}")
    
    if result.get('grading_status') == 'success':
        print("✅ QuestionGrader 测试通过")
        return result
    else:
        print(f"❌ QuestionGrader 测试失败")
        return None


def test_result_aggregator(state):
    """测试结果聚合"""
    print("\n🧪 测试 ResultAggregator Agent...")
    
    from functions.langgraph.agents.result_aggregator import ResultAggregatorAgent
    
    aggregator = ResultAggregatorAgent()
    result = aggregator.aggregate(state)
    
    print(f"聚合状态: {result.get('aggregation_status')}")
    
    aggregated = result.get('aggregated_results', {})
    print(f"总分: {aggregated.get('total_score')}/{aggregated.get('max_score')}")
    print(f"得分率: {aggregated.get('percentage'):.1f}%")
    print(f"等级: {aggregated.get('grade')}")
    
    if result.get('aggregation_status') == 'success':
        print("✅ ResultAggregator 测试通过")
        return result
    else:
        print(f"❌ ResultAggregator 测试失败")
        return None


def test_workflow():
    """测试完整工作流"""
    print("\n🧪 测试完整工作流...")
    
    from functions.langgraph.workflow_production import run_grading_workflow, format_grading_result
    
    question_file, answer_file, marking_file = create_test_files()
    
    print("开始运行工作流...")
    
    final_state = None
    
    for output in run_grading_workflow(
        question_files=[question_file],
        answer_files=[answer_file],
        marking_files=[marking_file],
        stream=True
    ):
        for node_name, node_state in output.items():
            print(f"  节点: {node_name}")
            final_state = node_state
    
    if final_state:
        print("\n📋 批改结果:")
        result_md = format_grading_result(final_state)
        print(result_md)
        
        print("\n✅ 工作流测试通过")
    else:
        print("❌ 工作流测试失败")


def test_database():
    """测试数据库"""
    print("\n🧪 测试数据库...")
    
    from functions.database import DatabaseManager
    
    db = DatabaseManager()
    
    # 测试保存
    student_data = {'id': 'test_001', 'name': '测试学生', 'class': '测试班级'}
    student_id = db.save_student(student_data)
    print(f"保存学生: ID={student_id}")
    
    task_data = {'student_id': 'test_001', 'subject': '数学', 'total_questions': 4}
    task_id = db.save_grading_task(task_data)
    print(f"保存任务: ID={task_id}")
    
    # 测试查询
    history = db.get_student_history('test_001')
    print(f"查询历史: {len(history)} 条记录")
    
    print("✅ 数据库测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🚀 开始运行生产级批改系统测试")
    print("=" * 60)
    
    # 测试各个 Agent
    state = test_input_parser()
    
    if state:
        state = test_question_analyzer(state)
    
    if state:
        state = test_question_grader(state)
    
    if state:
        state = test_result_aggregator(state)
    
    # 测试完整工作流
    test_workflow()
    
    # 测试数据库
    test_database()
    
    print("\n" + "=" * 60)
    print("✨ 所有测试完成！")
    print("=" * 60)


if __name__ == '__main__':
    run_all_tests()

