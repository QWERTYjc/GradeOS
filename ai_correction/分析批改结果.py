#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析批改结果和日志 - 检查Agent执行情况
"""

import json
from pathlib import Path
from datetime import datetime

# Windows控制台UTF-8编码支持
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def analyze_log_file(log_file: Path):
    """分析日志文件"""
    print("="*80)
    print("📋 分析日志文件")
    print("="*80)
    
    if not log_file.exists():
        print(f"❌ 日志文件不存在: {log_file}")
        return
    
    agent_activities = {
        'OrchestratorAgent': [],
        'MultiModalInputAgent': [],
        'QuestionUnderstandingAgent': [],
        'AnswerUnderstandingAgent': [],
        'RubricInterpreterAgent': [],
        'StudentDetectionAgent': [],
        'BatchPlanningAgent': [],
        'GradingWorkerAgent': [],
        'ResultAggregatorAgent': []
    }
    
    api_calls = []
    errors = []
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            # 检查Agent活动
            for agent_name in agent_activities.keys():
                if agent_name in line:
                    if '开始处理' in line or '处理完成' in line:
                        agent_activities[agent_name].append(line.strip())
            
            # 检查API调用
            if 'OpenRouter 响应成功' in line or 'OpenRouter API 调用失败' in line:
                api_calls.append(line.strip())
            
            # 检查错误
            if 'ERROR' in line:
                errors.append(line.strip())
    
    print("\n🤖 Agent执行情况:")
    for agent_name, activities in agent_activities.items():
        if activities:
            print(f"\n  {agent_name}:")
            for activity in activities[-3:]:  # 显示最后3条
                print(f"    - {activity}")
        else:
            print(f"\n  {agent_name}: ⚠️  未执行")
    
    print("\n📡 API调用情况:")
    for call in api_calls[-5:]:  # 显示最后5条
        print(f"  - {call}")
    
    print("\n❌ 错误情况:")
    if errors:
        for error in errors[-5:]:  # 显示最后5条
            print(f"  - {error}")
    else:
        print("  ✅ 无错误")


def analyze_result_file(result_file: Path):
    """分析批改结果文件"""
    print("\n" + "="*80)
    print("📊 分析批改结果文件")
    print("="*80)
    
    if not result_file.exists():
        print(f"❌ 结果文件不存在: {result_file}")
        return
    
    with open(result_file, 'r', encoding='utf-8') as f:
        result = json.load(f)
    
    print(f"\n任务ID: {result.get('task_id', 'N/A')}")
    print(f"状态: {result.get('status', 'N/A')}")
    print(f"总分: {result.get('total_score', 0)}")
    print(f"等级: {result.get('grade_level', 'N/A')}")
    
    # 分析错误
    errors = result.get('errors', [])
    if errors:
        print(f"\n❌ 错误数量: {len(errors)}")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. [{err.get('step', 'unknown')}]")
            print(f"     {err.get('error', str(err))}")
    
    # 分析警告
    warnings = result.get('warnings', [])
    if warnings:
        print(f"\n⚠️  警告数量: {len(warnings)}")
        for i, warn in enumerate(warnings, 1):
            if isinstance(warn, dict):
                print(f"  {i}. [{warn.get('step', 'unknown')}] {warn.get('warning', str(warn))}")
            else:
                print(f"  {i}. {warn}")
    
    # 分析详细反馈
    feedback = result.get('detailed_feedback', [])
    if feedback:
        print(f"\n✅ 详细反馈数量: {len(feedback)}")
        for i, fb in enumerate(feedback[:3], 1):
            if isinstance(fb, dict):
                content = fb.get('content', str(fb))
                print(f"  {i}. {content[:200]}...")
            else:
                print(f"  {i}. {str(fb)[:200]}...")
    
    # 分析进度历史
    tracking = result.get('tracking', {})
    progress_history = tracking.get('progress_history', [])
    if progress_history:
        print(f"\n📈 进度历史 ({len(progress_history)} 条记录):")
        for progress in progress_history[-10:]:  # 显示最后10条
            print(f"  [{progress.get('progress', 0)}%] {progress.get('step', 'unknown')}: {progress.get('message', '')}")


def main():
    """主函数"""
    project_root = Path(__file__).parent
    
    # 查找最新的结果文件
    results_dir = project_root.parent / "correction_results"
    if results_dir.exists():
        result_files = sorted(results_dir.glob("correction_result_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        if result_files:
            latest_result = result_files[0]
            print(f"📁 找到最新结果文件: {latest_result.name}")
            analyze_result_file(latest_result)
    
    # 分析日志文件
    log_file = project_root / "batch_correction.log"
    analyze_log_file(log_file)
    
    print("\n" + "="*80)
    print("✅ 分析完成")
    print("="*80)


if __name__ == "__main__":
    main()


