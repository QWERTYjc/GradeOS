#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RubricMasterAgent - 评分标准主控Agent
职责：深度理解评分标准，为每个批次生成定制化理解
核心价值：一次性深度理解，为多个批改Agent提供压缩版指导，大幅减少token消耗
"""

import logging
import json
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class RubricMasterAgent:
    """评分标准主控Agent"""
    
    def __init__(self):
        self.agent_name = "RubricMasterAgent"
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行评分标准深度理解"""
        logger.info(f"📏 [{self.agent_name}] 开始深度理解评分标准...")
        
        try:
            state['current_step'] = "评分标准理解"
            state['progress_percentage'] = 30.0
            
            # 获取评分标准理解结果（由RubricInterpreterAgent提供）
            rubric_understanding = state.get('rubric_understanding')
            
            if not rubric_understanding:
                logger.warning("未找到评分标准理解结果，跳过")
                return state
            
            batches_info = state.get('batches_info', [])
            
            # 为每个批次生成压缩版评分包
            batch_rubric_packages = {}
            
            for batch in batches_info:
                batch_id = batch['batch_id']
                
                # 生成批次专属评分包
                rubric_package = self._generate_batch_rubric_package(
                    batch_id,
                    rubric_understanding,
                    batch
                )
                
                batch_rubric_packages[batch_id] = rubric_package
            
            state['batch_rubric_packages'] = batch_rubric_packages
            
            logger.info(f"   为 {len(batches_info)} 个批次生成评分包")
            logger.info(f"✅ [{self.agent_name}] 评分标准理解完成")
            
            return state
            
        except Exception as e:
            error_msg = f"[{self.agent_name}] 执行失败: {str(e)}"
            logger.error(error_msg)
            
            if 'errors' not in state:
                state['errors'] = []
            state['errors'].append({
                'agent': self.agent_name,
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            
            return state
    
    def _generate_batch_rubric_package(
        self,
        batch_id: str,
        rubric_understanding: Dict[str, Any],
        batch_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        为批次生成压缩版评分包
        
        Token优化策略：
        - 提取决策树而非完整描述
        - 使用简写代替完整术语
        - 提供快速检查方法
        """
        criteria = rubric_understanding.get('criteria', [])
        
        compressed_criteria = []
        decision_trees = {}
        quick_checks = {}
        
        for criterion in criteria:
            cid = criterion.get('criterion_id', '')
            
            # 压缩版评分点
            compressed = {
                'id': cid,
                'desc': criterion.get('description', '')[:50],  # 截断描述
                'pts': criterion.get('points', 0),
                'method': criterion.get('evaluation_method', 'semantic')
            }
            compressed_criteria.append(compressed)
            
            # 生成决策树（简化版）
            decision_trees[cid] = {
                'keywords': criterion.get('keywords', [])[:5],  # 限制关键词数量
                'required': criterion.get('required_elements', [])[:3]
            }
            
            # 快速检查方法
            keywords = criterion.get('keywords', [])
            if keywords:
                quick_checks[cid] = f"查找关键词: {', '.join(keywords[:3])}"
            else:
                quick_checks[cid] = "检查描述内容"
        
        return {
            'batch_id': batch_id,
            'compressed_criteria': compressed_criteria,
            'decision_trees': decision_trees,
            'quick_checks': quick_checks,
            'total_points': rubric_understanding.get('total_points', 100)
        }
