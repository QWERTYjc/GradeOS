#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decide Batches Agent - 批次划分决策
根据token数量、模式类型决定批次划分策略
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第3节
"""

import logging
import math
from typing import Dict, List, Any
from datetime import datetime

from ..state import GradingState, Batch

logger = logging.getLogger(__name__)


class DecideBatchesAgent:
    """
    批次划分Agent
    
    职责:
    1. 计算所有题目的token数量和预计输出token数
    2. 根据模式选择阈值(高效模式6000, 专业模式4000)
    3. 生成批次列表,保证题目顺序和依赖性
    4. 优化批次大小以最大化并行效率
    
    算法: BalancedBatchPlanning (设计文档第3.2节)
    """
    
    def __init__(self):
        # Token阈值配置
        self.mode_thresholds = {
            'efficient': 6000,      # 高效模式
            'professional': 4000    # 专业模式(更保守)
        }
        
        # 估算参数
        self.avg_token_per_char = 0.4  # 每个字符约0.4个token
        self.output_multiplier = {
            'efficient': 1.2,       # 高效模式输出较少
            'professional': 3.0     # 专业模式输出详细
        }
        
    def __call__(self, state: GradingState) -> GradingState:
        """
        执行批次划分
        
        Args:
            state: 包含questions和mode的状态对象
            
        Returns:
            更新后的状态对象(包含batches列表)
        """
        state.setdefault('errors', [])
        state.setdefault('step_results', {})
        task_id = state.get('task_id', 'unknown_task')
        state.setdefault('task_id', task_id)
        logger.info(f"开始批次划分 - 任务ID: {state['task_id']}")
        
        try:
            # 更新进度
            state['current_step'] = '批次划分规划'
            state['progress_percentage'] = 60.0
            
            questions = state.get('questions', [])
            mode = state.get('mode', 'professional')
            
            if not questions:
                logger.warning("未找到题目,无法划分批次")
                state['batches'] = []
                return state
            
            # 执行批次划分算法
            batches = self._plan_batches(questions, mode)
            
            state['batches'] = batches
            
            # 更新进度
            state['progress_percentage'] = 65.0
            state['step_results']['decide_batches'] = {
                'total_questions': len(questions),
                'total_batches': len(batches),
                'mode': mode,
                'threshold': self.mode_thresholds[mode],
                'timestamp': str(datetime.now())
            }
            
            logger.info(f"批次划分完成 - 任务ID: {state['task_id']}, "
                       f"题目数: {len(questions)}, 批次数: {len(batches)}")
            
            return state
            
        except Exception as e:
            error_msg = f"批次划分失败: {str(e)}"
            logger.error(error_msg)
            state['errors'].append({
                'step': 'decide_batches',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            # 降级: 所有题目放入单批次
            state['batches'] = self._create_single_batch(state.get('questions', []))
            return state
    
    def _plan_batches(
        self,
        questions: List[Dict[str, Any]],
        mode: str
    ) -> List[Dict[str, Any]]:
        """
        批次划分算法 (BalancedBatchPlanning)
        
        Args:
            questions: 题目列表
            mode: 批改模式
            
        Returns:
            批次列表
        """
        # 1. 根据mode设置阈值
        threshold = self.mode_thresholds.get(mode, 4000)
        
        # 2. 计算每道题的token数
        questions_with_tokens = []
        for q in questions:
            token_count = self._estimate_question_tokens(q, mode)
            questions_with_tokens.append({
                **q,
                'estimated_tokens': token_count
            })
        
        # 3. 计算总token数
        total_tokens = sum(q['estimated_tokens'] for q in questions_with_tokens)
        
        logger.info(f"总题目数: {len(questions)}, 总token数: {total_tokens}, 阈值: {threshold}")
        
        # 4. 判断是否需要分批
        if total_tokens <= threshold:
            # 单批次处理
            logger.info("token数量在阈值内,使用单批次处理")
            return [{
                'batch_index': 0,
                'question_ids': [q['qid'] for q in questions],
                'estimated_tokens': total_tokens
            }]
        
        # 5. 计算批次数
        batch_count = math.ceil(total_tokens / threshold)
        logger.info(f"需要分为{batch_count}个批次")
        
        # 6. 按题号顺序均分 (保证顺序一致性)
        batches = self._distribute_questions(
            questions_with_tokens,
            batch_count,
            threshold
        )
        
        # 7. 验证并调整
        batches = self._validate_and_adjust_batches(batches, threshold)
        
        return batches
    
    def _estimate_question_tokens(
        self,
        question: Dict[str, Any],
        mode: str
    ) -> int:
        """
        估算单道题的token数
        
        包括:
        - 输入: token_ids对应的文本长度
        - 输出: 根据模式估算的输出token
        
        Args:
            question: 题目对象
            mode: 批改模式
            
        Returns:
            估算的总token数
        """
        # 估算输入token (基于token_ids数量)
        token_ids = question.get('token_ids', [])
        input_tokens = len(token_ids)
        
        # 如果token_ids为空,使用关键词估算
        if input_tokens == 0:
            keywords = question.get('keywords', [])
            text_length = sum(len(kw) for kw in keywords)
            input_tokens = int(text_length * self.avg_token_per_char)
        
        # 估算输出token
        multiplier = self.output_multiplier.get(mode, 2.0)
        output_tokens = int(input_tokens * multiplier)
        
        # 总token数
        total_tokens = input_tokens + output_tokens
        
        return total_tokens
    
    def _distribute_questions(
        self,
        questions: List[Dict[str, Any]],
        batch_count: int,
        threshold: int
    ) -> List[Dict[str, Any]]:
        """
        按题号顺序均分题目到各批次
        
        Args:
            questions: 题目列表(包含estimated_tokens)
            batch_count: 批次数量
            threshold: token阈值
            
        Returns:
            批次列表
        """
        batches = []
        
        # 简单均分策略
        questions_per_batch = math.ceil(len(questions) / batch_count)
        
        for i in range(0, len(questions), questions_per_batch):
            batch_questions = questions[i:i + questions_per_batch]
            
            batch_tokens = sum(q['estimated_tokens'] for q in batch_questions)
            
            batch = {
                'batch_index': len(batches),
                'question_ids': [q['qid'] for q in batch_questions],
                'estimated_tokens': batch_tokens
            }
            
            batches.append(batch)
        
        return batches
    
    def _validate_and_adjust_batches(
        self,
        batches: List[Dict[str, Any]],
        threshold: int
    ) -> List[Dict[str, Any]]:
        """
        验证并调整批次
        
        如果某批次超过阈值,进一步拆分
        
        Args:
            batches: 初始批次列表
            threshold: token阈值
            
        Returns:
            调整后的批次列表
        """
        adjusted_batches = []
        
        for batch in batches:
            if batch['estimated_tokens'] > threshold:
                logger.warning(
                    f"批次{batch['batch_index']}超过阈值"
                    f"({batch['estimated_tokens']} > {threshold}), 进行拆分"
                )
                
                # 拆分批次
                question_ids = batch['question_ids']
                mid = len(question_ids) // 2
                
                # 前半部分
                batch1 = {
                    'batch_index': len(adjusted_batches),
                    'question_ids': question_ids[:mid],
                    'estimated_tokens': batch['estimated_tokens'] // 2
                }
                adjusted_batches.append(batch1)
                
                # 后半部分
                batch2 = {
                    'batch_index': len(adjusted_batches),
                    'question_ids': question_ids[mid:],
                    'estimated_tokens': batch['estimated_tokens'] - batch1['estimated_tokens']
                }
                adjusted_batches.append(batch2)
            else:
                # 重新编号
                batch['batch_index'] = len(adjusted_batches)
                adjusted_batches.append(batch)
        
        # 记录批次统计
        self._log_batch_stats(adjusted_batches, threshold)
        
        return adjusted_batches
    
    def _log_batch_stats(
        self,
        batches: List[Dict[str, Any]],
        threshold: int
    ) -> None:
        """记录批次统计信息"""
        logger.info("=== 批次划分统计 ===")
        for batch in batches:
            utilization = (batch['estimated_tokens'] / threshold) * 100
            logger.info(
                f"批次{batch['batch_index']}: "
                f"{len(batch['question_ids'])}道题, "
                f"{batch['estimated_tokens']} tokens "
                f"(利用率: {utilization:.1f}%)"
            )
        
        total_questions = sum(len(b['question_ids']) for b in batches)
        total_tokens = sum(b['estimated_tokens'] for b in batches)
        logger.info(f"总计: {len(batches)}个批次, {total_questions}道题, {total_tokens} tokens")
    
    def _create_single_batch(
        self,
        questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """创建单个批次(降级方案)"""
        if not questions:
            return []
        
        return [{
            'batch_index': 0,
            'question_ids': [q['qid'] for q in questions],
            'estimated_tokens': 10000  # 默认值
        }]


# 便捷函数
def create_decide_batches_agent() -> DecideBatchesAgent:
    """创建DecideBatchesAgent实例"""
    return DecideBatchesAgent()
