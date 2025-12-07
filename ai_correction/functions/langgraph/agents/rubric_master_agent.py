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
            # 获取评分标准理解结果（由RubricInterpreterAgent提供）
            rubric_understanding = state.get('rubric_understanding')
            
            if not rubric_understanding:
                logger.warning("未找到评分标准理解结果，使用默认标准")
                rubric_understanding = {
                    'criteria': [],
                    'total_score': 100.0,
                    'summary': '默认评分标准'
                }
            
            batches_info = state.get('batches_info', [])
            
            if not batches_info:
                logger.warning("未找到批次信息，创建默认批次")
                batches_info = [{'batch_id': 'default_batch', 'question_ids': []}]
            
            batch_rubric_packages = {}
            
            for batch in batches_info:
                batch_id = batch.get('batch_id', 'default_batch')
                
                # ?????????
                rubric_package = self._generate_batch_rubric_package(
                    batch_id,
                    rubric_understanding,
                    batch
                )
                
                batch_rubric_packages[batch_id] = rubric_package
            
            logger.info(f"   ? {len(batches_info)} ????????")
            logger.info(f"[{self.agent_name}] ????????")

            
            # 只返回需要更新的字段，避免并发更新冲突
            # 注意：不返回progress_percentage和current_step，因为并行节点会冲突
            return {
                'batch_rubric_packages': batch_rubric_packages
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
                'batch_rubric_packages': {}
            }
    
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
        
        如果批次有question_ids，只包含这些题目的评分点
        """
        all_criteria = rubric_understanding.get('criteria', [])
        if not all_criteria:
            logger.warning("评分标准为空，使用默认评分点确保流程可继续")
            all_criteria = [{
                'criterion_id': 'C1',
                'question_id': 'UNKNOWN',
                'description': rubric_understanding.get('summary', '默认评分点'),
                'points': rubric_understanding.get('total_score', 100.0) or 100.0,
                'evaluation_method': 'semantic'
            }]
        
        # 如果批次指定了question_ids，只包含这些题目的评分点
        question_ids = batch_info.get('question_ids', [])
        if question_ids:
            # 过滤出属于这些题目的评分点
            criteria = []
            for criterion in all_criteria:
                criterion_question_id = criterion.get('question_id', '')
                if not criterion_question_id:
                    # 如果没有question_id，尝试从criterion_id提取
                    criterion_id = criterion.get('criterion_id', '')
                    if '_' in criterion_id:
                        criterion_question_id = criterion_id.split('_')[0]
                    else:
                        # 保留未知题目，避免直接丢弃评分点
                        criterion_question_id = 'UNKNOWN'
                
                if criterion_question_id in question_ids:
                    criteria.append(criterion)
            
            logger.info(f"批次 {batch_id}: 从 {len(all_criteria)} 个评分点中筛选出 {len(criteria)} 个（题目: {question_ids}）")
        else:
            # 如果没有指定question_ids，包含所有评分点
            criteria = all_criteria
        
        # 检查是否只有默认评分点
        if len(criteria) == 1 and criteria[0].get('points', 0) == 100.0:
            logger.warning(f"检测到默认评分标准（只有1个评分点），批改标准解析可能失败")
            logger.warning(f"   评分点ID: {criteria[0].get('criterion_id', 'N/A')}")
            logger.warning(f"   描述: {criteria[0].get('description', 'N/A')[:100]}")
        
        compressed_criteria = []
        decision_trees = {}
        quick_checks = {}
        
        logger.info(f"为批次 {batch_id} 生成评分包，共 {len(criteria)} 个评分点")
        
        for criterion in criteria:
            if not criterion or not isinstance(criterion, dict):
                continue
                
            cid = criterion.get('criterion_id', '')
            
            # 压缩版评分点
            description = criterion.get('description', '')
            compressed = {
                'id': cid,
                'desc': description[:50] if description else '',  # 截断描述
                'pts': criterion.get('points', 0),
                'method': criterion.get('evaluation_method', 'semantic')
            }
            compressed_criteria.append(compressed)
            
            # 生成决策树（简化版）
            keywords_list = criterion.get('keywords', []) or []
            required_elements = criterion.get('required_elements', []) or []
            decision_trees[cid] = {
                'keywords': keywords_list[:5],  # 限制关键词数量
                'required': required_elements[:3]
            }
            
            # 快速检查方法
            if keywords_list:
                quick_checks[cid] = f"查找关键词: {', '.join(keywords_list[:3])}"
            else:
                quick_checks[cid] = "检查描述内容"
        
        logger.info(f"   生成了 {len(compressed_criteria)} 个压缩评分点")
        
        return {
            'batch_id': batch_id,
            'compressed_criteria': compressed_criteria,
            'decision_trees': decision_trees,
            'quick_checks': quick_checks,
            'total_points': rubric_understanding.get('total_points', 100)
        }
