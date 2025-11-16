#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuestionContextAgent - 题目上下文Agent
职责：为批改提供题目语境，支持批改Agent理解答案
提取轻量级上下文，减少批改Agent的token消耗
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class QuestionContextAgent:
    """题目上下文Agent"""
    
    def __init__(self):
        self.agent_name = "QuestionContextAgent"
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行题目上下文提取"""
        logger.info(f"📖 [{self.agent_name}] 开始提取题目上下文...")
        
        try:
            # 获取题目理解结果
            question_understanding = state.get('question_understanding')
            
            if not question_understanding:
                logger.warning("未找到题目理解结果，使用默认理解")
                question_understanding = {
                    'questions': [],
                    'summary': '默认题目理解'
                }
            
            batches_info = state.get('batches_info', [])
            
            # 为每个批次生成压缩版题目上下文
            question_context_packages = {}
            
            for batch in batches_info:
                batch_id = batch['batch_id']
                
                # 生成批次专属上下文包
                context_package = self._generate_context_package(
                    batch_id,
                    question_understanding
                )
                
                question_context_packages[batch_id] = context_package
            
            logger.info(f"   为 {len(batches_info)} 个批次生成上下文包")
            logger.info(f"[{self.agent_name}] 题目上下文提取完成")
            
            # 只返回需要更新的字段，避免并发更新冲突
            # 注意：不返回progress_percentage和current_step，因为并行节点会冲突
            return {
                'question_context_packages': question_context_packages
            }
            
        except Exception as e:
            error_msg = f"[{self.agent_name}] 执行失败: {str(e)}"
            logger.error(error_msg)
            
            return {
                'errors': [{
                    'agent': self.agent_name,
                    'error': error_msg,
                    'timestamp': str(datetime.now())
                }],
                'question_context_packages': {}
            }
    
    def _generate_context_package(
        self,
        batch_id: str,
        question_understanding: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成批次专属题目上下文包（压缩版）"""
        
        question_text = question_understanding.get('question_text', '')
        key_requirements = question_understanding.get('key_requirements', [])
        
        # 压缩题目文本（提取核心部分）
        compressed_text = question_text[:200] if len(question_text) > 200 else question_text
        
        return {
            'batch_id': batch_id,
            'compressed_text': compressed_text,
            'key_requirements': key_requirements[:5],  # 限制数量
            'quick_ref': compressed_text[:50] + '...' if len(compressed_text) > 50 else compressed_text
        }
