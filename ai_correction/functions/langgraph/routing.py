#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic Routing Functions - 动态路由函数
支持条件执行和并行处理
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第12节
"""

import logging
from typing import Dict, Any, List, Literal
from langgraph.types import Send

from .state import GradingState

logger = logging.getLogger(__name__)


def should_skip_batch_processing(state: GradingState) -> Literal["skip", "process"]:
    """
    判断是否跳过批次处理
    
    场景:
    - 如果只有1道题且token数很少，直接评分
    - 如果没有题目，跳过
    
    返回:
        "skip": 跳过批次处理，直接到aggregate
        "process": 正常批次处理流程
    """
    questions = state.get('questions', [])
    batches = state.get('batches', [])
    
    # 没有题目
    if not questions:
        logger.warning("没有识别到题目，跳过批次处理")
        return "skip"
    
    # 只有1个批次且题目很少
    if len(batches) == 1 and len(questions) <= 2:
        logger.info("题目较少，使用简化流程")
        return "skip"
    
    return "process"


def route_after_decide_batches(state: GradingState) -> str:
    """
    decide_batches之后的路由决策
    
    返回:
        "orchestrator": 使用Orchestrator并行处理
        "evaluate_batches": 使用简化的顺序处理
    """
    batches = state.get('batches', [])
    mode = state.get('mode', 'professional')
    
    # 如果批次数大于1，使用Orchestrator并行
    if len(batches) > 1:
        logger.info(f"批次数={len(batches)}，启用Orchestrator并行处理")
        return "orchestrator"
    
    # 单批次，使用简化流程
    logger.info("单批次，使用顺序处理")
    return "evaluate_batches"


def route_by_mode(state: GradingState) -> str:
    """
    根据模式路由
    
    返回:
        "professional_path": 专业模式路径（包含评价生成）
        "efficient_path": 高效模式路径（跳过评价生成）
    """
    mode = state.get('mode', 'professional')
    
    if mode == 'professional':
        logger.info("专业模式：将生成详细评价")
        return "professional_path"
    else:
        logger.info("高效模式：跳过评价生成")
        return "efficient_path"


def should_push_to_class_system(state: GradingState) -> Literal["push", "skip"]:
    """
    判断是否推送到班级系统
    
    场景:
    - 如果是测试任务，不推送
    - 如果没有配置API，不推送
    - 正常任务，推送
    
    返回:
        "push": 推送到班级系统
        "skip": 跳过推送
    """
    task_id = state.get('task_id', '')
    push_enabled = state.get('push_enabled', True)
    
    # 测试任务
    if task_id.startswith('test_'):
        logger.info("测试任务，跳过推送")
        return "skip"
    
    # 推送未启用
    if not push_enabled:
        logger.info("推送未启用，跳过")
        return "skip"
    
    logger.info("推送已启用")
    return "push"


def create_parallel_batch_workers(state: GradingState) -> List[Send]:
    """
    创建并行批次worker
    
    这是Orchestrator的核心功能，为每个批次创建独立的Send对象
    
    返回:
        Send对象列表，LangGraph会自动并行执行
    """
    batches = state.get('batches', [])
    
    if not batches:
        logger.warning("没有批次需要处理")
        return []
    
    sends = []
    shared_context = {
        'task_id': state.get('task_id'),
        'mode': state.get('mode', 'professional'),
        'mm_tokens': state.get('mm_tokens', []),
        'rubric_struct': state.get('rubric_struct'),
        'questions': state.get('questions', []),
    }
    
    for batch in batches:
        # 为每个批次创建独立的state
        batch_state = {
            'batch_index': batch['batch_index'],
            'question_ids': batch.get('question_ids', []),
            **shared_context
        }
        
        # 创建Send对象，指向evaluate_batch_worker节点
        send_obj = Send("evaluate_batch_worker", batch_state)
        sends.append(send_obj)
        
        logger.info(f"创建worker - 批次{batch['batch_index']}: {len(batch.get('question_ids', []))}题")
    
    logger.info(f"共创建{len(sends)}个并行worker")
    return sends


def route_on_error(state: GradingState) -> Literal["retry", "fail", "continue"]:
    """
    错误处理路由
    
    根据错误类型和重试次数决定下一步
    
    返回:
        "retry": 重试当前步骤
        "fail": 标记为失败并结束
        "continue": 忽略错误继续执行
    """
    errors = state.get('errors', [])
    retry_count = state.get('retry_count', 0)
    max_retries = state.get('max_retries', 3)
    
    if not errors:
        return "continue"
    
    # 检查最近的错误
    last_error = errors[-1]
    error_step = last_error.get('step', '')
    
    # 关键步骤失败，需要重试
    critical_steps = ['extract_mm', 'parse_rubric', 'evaluate_batch']
    if error_step in critical_steps and retry_count < max_retries:
        logger.warning(f"关键步骤{error_step}失败，重试{retry_count + 1}/{max_retries}")
        return "retry"
    
    # 超过重试次数
    if retry_count >= max_retries:
        logger.error(f"超过最大重试次数{max_retries}，标记为失败")
        return "fail"
    
    # 非关键错误，继续执行
    logger.info(f"非关键错误，继续执行")
    return "continue"


def aggregate_worker_results(worker_results: List[Dict]) -> Dict[str, Any]:
    """
    聚合多个worker的结果
    
    这是Orchestrator模式的关键：收集所有并行worker的输出
    
    参数:
        worker_results: 所有worker返回的结果列表
    
    返回:
        聚合后的结果字典
    """
    all_evaluations = []
    all_errors = []
    
    for result in worker_results:
        evaluations = result.get('evaluations', [])
        errors = result.get('errors', [])
        
        all_evaluations.extend(evaluations)
        all_errors.extend(errors)
    
    logger.info(f"聚合了{len(worker_results)}个worker的结果，共{len(all_evaluations)}个评分")
    
    return {
        'evaluations': all_evaluations,
        'errors': all_errors,
        'worker_count': len(worker_results)
    }


# 条件路由配置
ROUTING_CONFIG = {
    'skip_batch_check': should_skip_batch_processing,
    'batch_routing': route_after_decide_batches,
    'mode_routing': route_by_mode,
    'push_check': should_push_to_class_system,
    'error_routing': route_on_error,
}


def get_routing_function(name: str):
    """获取路由函数"""
    return ROUTING_CONFIG.get(name)
