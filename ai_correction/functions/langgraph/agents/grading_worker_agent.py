#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GradingWorkerAgent - 批改工作Agent
职责：基于定制化标准和题目上下文批改学生答案
核心价值：接收压缩版评分包和上下文，高效执行批改，最小化token消耗
"""

import logging
import json
from typing import Dict, Any, List
from datetime import datetime

from ...llm_client import get_llm_client, LLMClient

logger = logging.getLogger(__name__)


class GradingWorkerAgent:
    """批改工作Agent"""

    def __init__(self, llm_client=None):
        self.agent_name = "GradingWorkerAgent"
        # 使用 Gemini 2.5 Pro 作为批改模型，提供强大的多模态能力和复杂推理
        # 启用 high reasoning_effort 以获得最佳的批改质量
        self.llm_client = llm_client or LLMClient(
            provider='openrouter',
            model='google/gemini-2.5-pro-exp-03-25'
        )
        self.reasoning_effort = "high"  # 启用高强度思考模式
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行批改工作"""
        logger.info(f"[{self.agent_name}] 开始批改作业...")
        
        try:
            state['current_step'] = "批改作业"
            state['progress_percentage'] = 50.0
            
            # 获取批次信息
            batches_info = state.get('batches_info', [])
            batch_rubric_packages = state.get('batch_rubric_packages', {})
            question_context_packages = state.get('question_context_packages', {})
            answer_understanding = state.get('answer_understanding')
            
            if not batches_info:
                logger.warning("没有批次信息，跳过批改")
                return {
                    'grading_results': [],
                    'total_score': 0
                }
            
            all_grading_results = []
            
            # 并行处理所有批次
            import asyncio
            
            async def grade_batch(batch):
                """批改单个批次"""
                batch_id = batch.get('batch_id', 'default_batch')
                students = batch.get('students', [])
                question_ids = batch.get('question_ids', [])
                
                rubric_package = batch_rubric_packages.get(batch_id, {})
                context_package = question_context_packages.get(batch_id, {})
                
                logger.info("=" * 60)
                logger.info(f"[开始批改批次] {batch_id}")
                logger.info(f"   题目: {question_ids if question_ids else 'all'}")
                logger.info(f"   学生数量: {len(students)}")
                logger.info(f"   评分点数量: {len(rubric_package.get('criteria', []))}")
                logger.info("=" * 60)
                
                batch_results = []
                # 批改该批次的学生（每个批次处理相同的学生，但只批改指定的题目）
                for idx, student in enumerate(students, 1):
                    logger.info(f"   批改学生 {idx}/{len(students)}: {student.get('student_name', student.get('student_id', 'Unknown'))}")
                    result = await self._grade_student(
                        student,
                        rubric_package,
                        context_package,
                        answer_understanding,
                        state,  # 传递state以便获取answer_multimodal_files
                        question_ids  # 传递题目ID列表，用于过滤评估结果
                    )
                    batch_results.append(result)
                
                logger.info("=" * 60)
                logger.info(f"[批次完成] {batch_id}")
                logger.info(f"   处理了 {len(batch_results)} 个学生")
                total_eval_count = sum(len(r.get('evaluations', [])) for r in batch_results)
                logger.info(f"   总评估结果: {total_eval_count} 个")
                logger.info("=" * 60)
                return batch_results
            
            # 并行执行所有批次的批改
            if len(batches_info) > 1:
                logger.info(f"并行处理 {len(batches_info)} 个批次...")
                try:
                    batch_results_list = await asyncio.gather(*[grade_batch(batch) for batch in batches_info])
                    # 展平结果列表
                    for i, batch_results in enumerate(batch_results_list):
                        logger.info(f"批次 {batches_info[i].get('batch_id')} 返回了 {len(batch_results)} 个结果")
                        all_grading_results.extend(batch_results)
                    logger.info(f"并行批改完成，总共 {len(all_grading_results)} 个学生结果")
                except Exception as e:
                    logger.error(f"并行批改失败: {e}", exc_info=True)
                    # 如果并行失败，尝试顺序处理
                    logger.warning("并行批改失败，尝试顺序处理...")
                    for batch in batches_info:
                        try:
                            batch_results = await grade_batch(batch)
                            all_grading_results.extend(batch_results)
                        except Exception as batch_error:
                            logger.error(f"批次 {batch.get('batch_id')} 处理失败: {batch_error}", exc_info=True)
                            # 继续处理其他批次，不中断整个流程
            else:
                # 单批次顺序处理
                logger.info("单批次顺序处理...")
                for batch in batches_info:
                    batch_results = await grade_batch(batch)
                    all_grading_results.extend(batch_results)
            
            # 计算总分
            total_score = sum(r.get('total_score', 0) for r in all_grading_results) / len(all_grading_results) if all_grading_results else 0
            
            logger.info(f"   批改了 {len(all_grading_results)} 个学生")
            logger.info(f"   平均分: {total_score:.1f}")
            
            # 统计评估结果数量
            total_evaluations = sum(len(r.get('evaluations', [])) for r in all_grading_results)
            logger.info(f"   总评估结果数量: {total_evaluations}")
            
            # 统计题目覆盖
            all_question_ids_in_results = set()
            for r in all_grading_results:
                for e in r.get('evaluations', []):
                    criterion_id = e.get('criterion_id', '')
                    if '_' in criterion_id:
                        qid = criterion_id.split('_')[0]
                        all_question_ids_in_results.add(qid)
            logger.info(f"   批改覆盖的题目: {sorted(all_question_ids_in_results)} ({len(all_question_ids_in_results)}道题)")
            
            logger.info(f"[{self.agent_name}] 批改完成")
            
            # 只返回需要更新的字段
            return {
                'grading_results': all_grading_results,
                'total_score': total_score,
                'progress_percentage': 80.0,
                'current_step': "批改作业"
            }
            
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
    
    async def _grade_student(
        self,
        student: Dict[str, Any],
        rubric_package: Dict[str, Any],
        context_package: Dict[str, Any],
        answer_understanding: Dict[str, Any],
        state: Dict[str, Any] = None,
        question_ids: List[str] = None
    ) -> Dict[str, Any]:
        """批改单个学生（基于压缩版评分包和上下文）"""
        
        student_id = student.get('student_id', '')
        student_name = student.get('name', '')
        
        # 获取压缩版评分标准
        compressed_criteria = rubric_package.get('compressed_criteria', [])
        decision_trees = rubric_package.get('decision_trees', {})
        quick_checks = rubric_package.get('quick_checks', {})
        total_points = rubric_package.get('total_points', 100)
        
        # 检查是否只有默认评分点（说明批改标准解析失败）
        # 如果只有1个评分点且分值为100，可能是默认标准
        if len(compressed_criteria) == 1 and compressed_criteria[0].get('pts', 0) == 100.0:
            logger.warning("检测到默认评分标准，批改标准解析可能失败")
            # 尝试从state中获取原始的rubric_understanding
            if state:
                rubric_understanding = state.get('rubric_understanding')
                if rubric_understanding and rubric_understanding.get('criteria'):
                    criteria = rubric_understanding.get('criteria', [])
                    if len(criteria) > 1:
                        logger.info(f"从rubric_understanding中恢复 {len(criteria)} 个评分点")
                        # 重新构建compressed_criteria
                        compressed_criteria = []
                        for criterion in criteria:
                            if isinstance(criterion, dict):
                                compressed_criteria.append({
                                    'id': criterion.get('criterion_id', ''),
                                    'desc': criterion.get('description', '')[:50],
                                    'pts': criterion.get('points', 0),
                                    'method': criterion.get('evaluation_method', 'semantic')
                                })
                        logger.info(f"已恢复 {len(compressed_criteria)} 个评分点到compressed_criteria")
        
        # 获取学生答案内容
        # 优先从原始答案文件获取完整文本，而不是从理解结果获取（理解结果可能被LLM简化）
        answer_text = ''
        answer_summary = ''
        
        # PDF现在直接使用Vision API处理，不提取文本
        # 答案内容将通过Vision API在批改时直接获取
        if state:
            answer_files = state.get('answer_multimodal_files', [])
            if answer_files:
                answer_file = answer_files[0]
                modality_type = answer_file.get('modality_type', '')
                content_rep = answer_file.get('content_representation', {})
                
                # 如果是PDF图片格式，答案内容将通过Vision API在批改时获取
                if modality_type == 'pdf_image':
                    # 答案内容将在批改提示词中通过Vision API获取
                    answer_text = ""  # 留空，让LLM通过Vision API直接查看PDF
                    logger.info("PDF文件将直接通过Vision API处理，不提取文本")
                elif isinstance(content_rep, dict) and 'text' in content_rep:
                    # 文本格式（非PDF）
                    raw_text = content_rep['text']
                    answer_text = self._filter_toc_content(raw_text)
                    logger.info(f"从原始文件提取答案文本，原始长度: {len(raw_text)} 字符，过滤后: {len(answer_text)} 字符")
        
        # 如果原始文件没有文本，尝试从理解结果获取
        if not answer_text and answer_understanding:
            answer_text = answer_understanding.get('answer_text', '') or answer_understanding.get('answer_content', '')
            answer_summary = answer_understanding.get('summary', '') or answer_understanding.get('answer_summary', '')
            if answer_text:
                logger.info(f"从理解结果提取答案文本，长度: {len(answer_text)} 字符")
        
        # 如果还是没有，使用默认文本
        if not answer_text and not answer_summary:
            answer_text = "学生答案内容未提取"
            logger.warning("无法获取学生答案内容，使用默认文本")
        else:
            # 记录答案文本的前100个字符用于调试
            preview = (answer_text or answer_summary)[:100]
            logger.info(f"答案文本预览: {preview}...")
        
        # 获取题目上下文
        question_context = context_package.get('context_summary', '')
        
        if not compressed_criteria:
            logger.warning(f"没有评分标准，跳过批改")
            return {
                'student_id': student_id,
                'student_name': student_name,
                'evaluations': [],
                'total_score': 0,
                'processing_time_ms': 0
            }
        
        # 获取答案文件信息（用于Vision API）
        answer_file = None
        if state:
            answer_files = state.get('answer_multimodal_files', [])
            if answer_files:
                answer_file = answer_files[0]
        
        # 构建批改提示词（支持Vision API）
        prompt_text, vision_content = self._build_grading_prompt(
            answer_text or answer_summary,
            question_context,
            compressed_criteria,
            decision_trees,
            total_points,
            answer_file
        )
        
        # 调用LLM进行批改
        try:
            # 构建消息，如果有多模态内容则添加
            user_content = [{"type": "text", "text": prompt_text}]
            if vision_content:
                user_content.extend(vision_content)
            
            messages = [
                {"role": "system", "content": "你是一位资深教育专家，擅长根据评分标准批改学生答案。请严格按照评分标准进行评分，给出详细的评价和反馈。"},
                {"role": "user", "content": user_content if vision_content else prompt_text}
            ]
            
            logger.info(f"调用LLM批改学生 {student_name} 的答案...")
            if vision_content:
                logger.info(f"使用Vision API处理PDF，共{len(vision_content)}页")
            # 不限制 max_tokens，让模型输出完整的批改详情
            # 包括详细的学生作答、评分理由、证据等
            # 使用 high reasoning_effort 以获得最佳的批改质量
            num_criteria = len(compressed_criteria)
            logger.info(f"评分点数量: {num_criteria}，不限制 max_tokens 以确保完整输出")
            response = self.llm_client.chat(messages, temperature=0.2, reasoning_effort=self.reasoning_effort)
            logger.info(f"LLM批改响应长度: {len(response)} 字符")
            
            # 解析LLM响应
            evaluations = self._parse_grading_response(response, compressed_criteria)
            
        except Exception as e:
            logger.error(f"LLM批改失败: {e}，使用简化评分")
            # 降级到简化评分
            evaluations = self._simple_grading(compressed_criteria, quick_checks)
        
        # 如果指定了question_ids，只保留这些题目的评估结果
        if question_ids:
            filtered_evaluations = []
            for eval_item in evaluations:
                criterion_id = eval_item.get('criterion_id', '')
                # 检查是否属于指定的题目
                belongs_to_batch = False
                for qid in question_ids:
                    if criterion_id.startswith(qid + '_') or criterion_id == qid:
                        belongs_to_batch = True
                        break
                
                if belongs_to_batch:
                    filtered_evaluations.append(eval_item)
            
            evaluations = filtered_evaluations
            logger.info(f"过滤后保留 {len(evaluations)} 个评估项（题目: {question_ids}）")
        
        # 计算总分
        total_score = sum(e.get('score_earned', 0) for e in evaluations)
        
        return {
            'student_id': student_id,
            'student_name': student_name,
            'evaluations': evaluations,
            'total_score': total_score,
            'processing_time_ms': 1000,
            'question_ids': question_ids  # 记录处理的题目
        }
    
    def _build_grading_prompt(
        self,
        answer_text: str,
        question_context: str,
        compressed_criteria: List[Dict],
        decision_trees: Dict,
        total_points: float,
        answer_file: Dict[str, Any] = None
    ) -> tuple[str, List[Dict]]:
        """
        构建批改提示词
        
        Returns:
            (prompt_text, vision_content): 提示词文本和Vision API内容列表
        """
        
        criteria_text = "\n".join([
            f"{i+1}. [{c['id']}] {c['desc']} ({c['pts']}分)"
            for i, c in enumerate(compressed_criteria)
        ])
        
        vision_content = []

        # 如果答案文件是PDF格式，直接添加PDF文件（不转换为图片）
        if answer_file:
            modality_type = answer_file.get('modality_type', '')
            file_path = answer_file.get('file_path', '')

            if modality_type == 'pdf_image' and file_path:
                # 直接读取PDF文件并转换为base64
                try:
                    import base64
                    with open(file_path, 'rb') as f:
                        pdf_bytes = f.read()
                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

                    # 添加PDF到多模态内容
                    vision_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:application/pdf;base64,{pdf_base64}"
                        }
                    })
                    logger.info(f"添加PDF文件到多模态输入: {file_path}")
                except Exception as e:
                    logger.error(f"读取PDF文件失败: {file_path}, 错误: {e}")
                    # 返回空vision_content，让LLM使用文本模式
        
        prompt_text = f"""根据评分标准批改学生答案。

【题目上下文】
{question_context}

【学生答案】
{"（答案在图片中）" if vision_content else answer_text}

【评分标准】
{criteria_text}

**必须评估所有 {len(compressed_criteria)} 个评分点！**

【核心要求】
1. **逐项评估**：每个 criterion_id 单独评估
2. **识别解题方法**：
   - 如有多种方法（Case1/Case2, Method1/Method2），识别学生使用的方法
   - 只评估学生使用的方法，未使用的方法标记为"未满足"（score_earned=0）
3. **详细描述**：
   - student_work：学生的公式、步骤、结果、使用的方法
   - justification：为什么给这个分数，与标准答案对比
   - evidence：具体计算式、中间结果、最终答案
   - feedback：具体改进建议
4. **数学公式规则**：
   - 禁止反斜杠 LaTeX（\\frac, \\times 等）
   - 使用：a/b, ×, π, √x, ∠, △, ≅

【JSON 输出格式】
{{
  "evaluations": [
    {{
      "criterion_id": "Q1_C1",
      "score_earned": 5,
      "max_score": 5,
      "is_met": true,
      "satisfaction_level": "完全满足",
      "student_work": "学生的公式、步骤、结果、使用的方法",
      "justification": "为什么给这个分数，与标准答案对比",
      "matched_criterion": "符合评分标准的哪一项",
      "feedback": "具体改进建议",
      "evidence": ["具体计算式", "中间结果", "最终答案"]
    }}
  ],
  "total_score": 总分,
  "overall_feedback": "总体评价",
  "question_by_question_feedback": {{"Q1": "题目1批改说明"}}
}}

【示例 - 多种方法】
学生使用 Case1（含理由）：
- Q8a_C1_Case1: score_earned=2, is_met=true, justification="学生使用 Case1，理由完整"
- Q8a_C2_Case2: score_earned=0, is_met=false, justification="学生未使用 Case2"

禁止：概括性描述、合并评分点、含糊理由
正确：详细描述、逐项评估、识别方法"""
        
        return prompt_text, vision_content
    
    def _parse_grading_response(self, response: str, compressed_criteria: List[Dict]) -> List[Dict]:
        """解析LLM批改响应"""
        import re
        
        # 尝试提取JSON（支持多行JSON和代码块）
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start < 0 or json_end <= json_start:
            logger.warning("未找到JSON内容，使用简化评分")
            return self._simple_grading(compressed_criteria, {})
        
        json_str = response[json_start:json_end]
        
        # 多次尝试解析，逐步修复JSON问题
        for attempt in range(3):
            try:
                result = json.loads(json_str)
                evaluations = result.get('evaluations', [])
                
                if evaluations:
                    # 记录解析结果
                    logger.info(f"JSON解析成功！解析到 {len(evaluations)} 个评分点评估")
                    for i, eval_item in enumerate(evaluations, 1):
                        criterion_id = eval_item.get('criterion_id', 'N/A')
                        score = eval_item.get('score_earned', 0)
                        max_score = eval_item.get('max_score', 0)
                        student_work = eval_item.get('student_work', '')
                        matched_criterion = eval_item.get('matched_criterion', '')
                        justification = eval_item.get('justification', '')[:50]
                        logger.info(f"  评估{i}: [{criterion_id}] {score}/{max_score}分 - {justification}...")
                        if student_work:
                            logger.info(f"    学生作答: {student_work[:80]}...")
                        if matched_criterion:
                            logger.info(f"    符合标准: {matched_criterion[:80]}...")
                    
                    # 检查是否有question_by_question_feedback
                    if 'question_by_question_feedback' in result:
                        q_feedback = result['question_by_question_feedback']
                        logger.info(f"逐题反馈: {len(q_feedback)} 道题")
                        for q_id, feedback in q_feedback.items():
                            logger.info(f"  {q_id}: {feedback[:100]}...")
                    
                    # 检查是否所有评分点都被评估了
                    evaluated_criterion_ids = {e.get('criterion_id') for e in evaluations if e.get('criterion_id')}
                    all_criterion_ids = {c.get('id') for c in compressed_criteria if c.get('id')}
                    missing_criterion_ids = all_criterion_ids - evaluated_criterion_ids
                    
                    if missing_criterion_ids:
                        logger.warning(f"发现 {len(missing_criterion_ids)} 个未评估的评分点: {sorted(missing_criterion_ids)}")
                        # 为缺失的评分点创建默认评估项
                        for criterion_id in missing_criterion_ids:
                            # 找到对应的评分点信息
                            criterion_info = None
                            for c in compressed_criteria:
                                if c.get('id') == criterion_id:
                                    criterion_info = c
                                    break
                            
                            if criterion_info:
                                missing_eval = {
                                    'criterion_id': criterion_id,
                                    'score_earned': 0,
                                    'max_score': criterion_info.get('pts', 0),
                                    'is_met': False,
                                    'satisfaction_level': '未评估',
                                    'justification': f'该评分点未在LLM响应中找到，可能是响应被截断',
                                    'matched_criterion': criterion_info.get('desc', '')[:100],
                                    'student_work': '未评估',
                                    'feedback': '请检查批改结果是否完整',
                                    'evidence': []
                                }
                                evaluations.append(missing_eval)
                                logger.info(f"为缺失的评分点 {criterion_id} 创建默认评估项")
                    
                    # 确保所有评估项都包含必要字段
                    for eval_item in evaluations:
                        # 确保有max_score字段
                        if 'max_score' not in eval_item:
                            # 从compressed_criteria中查找对应的分值
                            criterion_id = eval_item.get('criterion_id', '')
                            for c in compressed_criteria:
                                if c.get('id') == criterion_id:
                                    eval_item['max_score'] = c.get('pts', 0)
                                    break
                        # 确保有matched_criterion字段（如果没有，从justification中提取或使用默认值）
                        if 'matched_criterion' not in eval_item or not eval_item.get('matched_criterion'):
                            # 尝试从justification中提取，或使用description
                            justification = eval_item.get('justification', '')
                            if justification:
                                # 简单提取：取justification的前100字符作为matched_criterion
                                eval_item['matched_criterion'] = justification[:100]
                            else:
                                eval_item['matched_criterion'] = '已评估'
                        # 确保有student_work字段
                        if 'student_work' not in eval_item or not eval_item.get('student_work'):
                            # 从evidence中提取或使用justification
                            evidence = eval_item.get('evidence', [])
                            if evidence:
                                eval_item['student_work'] = '；'.join(evidence[:3])  # 取前3个证据
                            else:
                                eval_item['student_work'] = eval_item.get('justification', '已评估')[:200]
                    
                    logger.info(f"最终评估项数量: {len(evaluations)}，评分点数量: {len(compressed_criteria)}")
                    return evaluations
                else:
                    logger.warning("JSON解析成功但evaluations为空")
                    break
                    
            except json.JSONDecodeError as e:
                error_pos = getattr(e, 'pos', None)
                error_msg = str(e)
                
                if attempt < 2:  # 前两次尝试修复
                    logger.warning(f"JSON解析失败（尝试{attempt+1}/3）: {error_msg}")
                    
                    # 修复策略1: 修复LaTeX数学公式中的反斜杠
                    # 在字符串值中，LaTeX命令如 \frac, \sqrt 需要转义
                    if 'Invalid \\escape' in error_msg or '\\escape' in error_msg:
                        # 使用更简单但有效的方法：在字符串值中修复反斜杠
                        # 遍历JSON字符串，找到字符串值并修复其中的反斜杠
                        fixed_parts = []
                        i = 0
                        in_string = False
                        escape_next = False
                        
                        while i < len(json_str):
                            char = json_str[i]
                            
                            if escape_next:
                                # 如果下一个字符是转义字符
                                if char not in '\\/bfnrtu"':
                                    # 不是合法的JSON转义，需要双转义
                                    fixed_parts.append('\\\\' + char)
                                else:
                                    fixed_parts.append('\\' + char)
                                escape_next = False
                            elif char == '\\':
                                # 遇到反斜杠，检查下一个字符
                                if i + 1 < len(json_str):
                                    next_char = json_str[i + 1]
                                    if next_char not in '\\/bfnrtu"':
                                        # 不是合法的JSON转义，需要双转义
                                        fixed_parts.append('\\\\')
                                        escape_next = True
                                    else:
                                        fixed_parts.append('\\')
                                        escape_next = True
                                else:
                                    fixed_parts.append('\\')
                            elif char == '"':
                                # 检查是否是转义的引号
                                if i > 0 and json_str[i-1] == '\\' and (i < 2 or json_str[i-2] != '\\'):
                                    # 转义的引号，保持原样
                                    fixed_parts.append(char)
                                else:
                                    # 字符串开始或结束
                                    in_string = not in_string
                                    fixed_parts.append(char)
                            else:
                                fixed_parts.append(char)
                            
                            i += 1
                        
                        json_str = ''.join(fixed_parts)
                    
                    # 修复策略2: 修复未转义的引号
                    elif 'Expecting' in error_msg and 'delimiter' in error_msg:
                        # 尝试修复常见的分隔符问题
                        json_str = json_str.replace(',,', ',').replace('{,', '{').replace(',}', '}')
                    
                    # 修复策略3: 移除代码块标记
                    json_str = json_str.replace('```json', '').replace('```', '')
                    
                    logger.info(f"尝试修复JSON（错误位置: {error_pos}）...")
                else:
                    # 最后一次尝试失败，记录详细信息
                    logger.error(f"JSON解析最终失败: {error_msg}")
                    logger.error(f"错误位置: {error_pos}")
                    logger.error(f"错误位置附近的内容: {json_str[max(0, (error_pos or 0)-100):(error_pos or 0)+100] if error_pos else 'N/A'}")
                    logger.error(f"响应内容前1000字符: {response[:1000]}")
                    break
            except Exception as e:
                logger.error(f"解析失败: {e}")
                logger.error(f"响应内容前500字符: {response[:500]}")
                break
        
        # 如果所有尝试都失败，尝试使用更宽松的方法提取evaluations
        logger.warning("所有JSON解析尝试失败，尝试使用宽松方法提取evaluations...")
        
        try:
            # 方法1: 使用正则表达式提取evaluations数组中的对象
            # 查找evaluations数组的开始和结束
            eval_start = json_str.find('"evaluations"')
            if eval_start < 0:
                eval_start = json_str.find("'evaluations'")
            
            if eval_start >= 0:
                # 找到数组开始
                array_start = json_str.find('[', eval_start)
                if array_start >= 0:
                    # 找到匹配的右括号
                    bracket_count = 0
                    array_end = array_start
                    for i in range(array_start, len(json_str)):
                        if json_str[i] == '[':
                            bracket_count += 1
                        elif json_str[i] == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                array_end = i + 1
                                break
                    
                    if array_end > array_start:
                        eval_array_str = json_str[array_start:array_end]
                        # 尝试提取每个evaluation对象
                        evaluations = []
                        i = 0
                        while i < len(eval_array_str):
                            if eval_array_str[i] == '{':
                                # 找到匹配的}
                                brace_count = 0
                                obj_start = i
                                obj_end = i
                                for j in range(i, len(eval_array_str)):
                                    if eval_array_str[j] == '{':
                                        brace_count += 1
                                    elif eval_array_str[j] == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            obj_end = j + 1
                                            break
                                
                                if obj_end > obj_start:
                                    obj_str = eval_array_str[obj_start:obj_end]
                                    # 尝试解析这个对象
                                    try:
                                        # 修复常见的JSON问题
                                        obj_str_fixed = obj_str
                                        # 修复单引号
                                        obj_str_fixed = obj_str_fixed.replace("'", '"')
                                        # 修复Python布尔值
                                        obj_str_fixed = obj_str_fixed.replace('True', 'true').replace('False', 'false').replace('None', 'null')
                                        # 修复LaTeX转义：在字符串值中双转义反斜杠
                                        # 简单方法：找到所有 "key": "value" 模式，修复value中的反斜杠
                                        import re
                                        # 匹配 "key": "value" 模式
                                        def fix_value_escape(match):
                                            key_part = match.group(1)
                                            value_part = match.group(2)
                                            # 修复value中的反斜杠（但保留合法转义）
                                            fixed_value = ''
                                            j = 0
                                            while j < len(value_part):
                                                if value_part[j] == '\\' and j + 1 < len(value_part):
                                                    next_char = value_part[j + 1]
                                                    if next_char not in '\\/bfnrtu"':
                                                        fixed_value += '\\\\' + next_char
                                                        j += 2
                                                    else:
                                                        fixed_value += '\\' + next_char
                                                        j += 2
                                                else:
                                                    fixed_value += value_part[j]
                                                    j += 1
                                            return f'"{key_part}": "{fixed_value}"'
                                        
                                        # 尝试直接解析
                                        obj = json.loads(obj_str_fixed)
                                        if 'criterion_id' in obj:
                                            evaluations.append(obj)
                                    except Exception as parse_err:
                                        # 如果解析失败，尝试手动提取字段
                                        try:
                                            # 使用正则表达式提取关键字段
                                            criterion_id_match = re.search(r'"criterion_id"\s*:\s*"([^"]+)"', obj_str)
                                            score_match = re.search(r'"score_earned"\s*:\s*(\d+(?:\.\d+)?)', obj_str)
                                            max_score_match = re.search(r'"max_score"\s*:\s*(\d+(?:\.\d+)?)', obj_str)
                                            justification_match = re.search(r'"justification"\s*:\s*"([^"]+)"', obj_str)
                                            
                                            if criterion_id_match:
                                                student_work_match = re.search(r'"student_work"\s*:\s*"([^"]+)"', obj_str)
                                                matched_criterion_match = re.search(r'"matched_criterion"\s*:\s*"([^"]+)"', obj_str)
                                                evidence_match = re.search(r'"evidence"\s*:\s*\[([^\]]+)\]', obj_str)
                                                
                                                eval_obj = {
                                                    'criterion_id': criterion_id_match.group(1),
                                                    'score_earned': float(score_match.group(1)) if score_match else 0,
                                                    'max_score': float(max_score_match.group(1)) if max_score_match else 0,
                                                    'is_met': True,
                                                    'satisfaction_level': '完全满足',
                                                    'justification': justification_match.group(1) if justification_match else '已评估',
                                                    'feedback': '无',
                                                    'evidence': [],
                                                    'student_work': student_work_match.group(1) if student_work_match else (justification_match.group(1)[:200] if justification_match else '已评估'),
                                                    'matched_criterion': matched_criterion_match.group(1) if matched_criterion_match else (justification_match.group(1)[:100] if justification_match else '已评估')
                                                }
                                                evaluations.append(eval_obj)
                                        except:
                                            pass
                                    
                                    i = obj_end
                                else:
                                    i += 1
                            else:
                                i += 1
                        
                        if evaluations:
                            logger.info(f"使用宽松方法提取成功！获得 {len(evaluations)} 个评分点评估")
                            return evaluations
            
            # 方法2: 从原始响应中直接搜索evaluation对象
            # 查找所有包含criterion_id的行
            criterion_pattern = r'"criterion_id"\s*:\s*"([^"]+)"'
            criterion_matches = list(re.finditer(criterion_pattern, response))
            
            if criterion_matches:
                logger.info(f"在响应中找到 {len(criterion_matches)} 个criterion_id，尝试提取...")
                evaluations = []
                for match in criterion_matches:
                    criterion_id = match.group(1)
                    # 在匹配位置附近查找其他字段
                    start_pos = max(0, match.start() - 200)
                    end_pos = min(len(response), match.end() + 1000)
                    region = response[start_pos:end_pos]
                    
                    # 提取字段
                    score_match = re.search(r'"score_earned"\s*:\s*(\d+(?:\.\d+)?)', region)
                    max_score_match = re.search(r'"max_score"\s*:\s*(\d+(?:\.\d+)?)', region)
                    justification_match = re.search(r'"justification"\s*:\s*"([^"]+)"', region)
                    student_work_match = re.search(r'"student_work"\s*:\s*"([^"]+)"', region)
                    matched_criterion_match = re.search(r'"matched_criterion"\s*:\s*"([^"]+)"', region)
                    
                    eval_obj = {
                        'criterion_id': criterion_id,
                        'score_earned': float(score_match.group(1)) if score_match else 0,
                        'max_score': float(max_score_match.group(1)) if max_score_match else 0,
                        'is_met': True,
                        'satisfaction_level': '完全满足',
                        'justification': justification_match.group(1) if justification_match else '已评估',
                        'feedback': '无',
                        'evidence': [],
                        'student_work': student_work_match.group(1) if student_work_match else (justification_match.group(1)[:200] if justification_match else '已评估'),
                        'matched_criterion': matched_criterion_match.group(1) if matched_criterion_match else (justification_match.group(1)[:100] if justification_match else '已评估')
                    }
                    evaluations.append(eval_obj)
                
                if evaluations:
                    logger.info(f"从响应中直接提取成功！获得 {len(evaluations)} 个评分点评估")
                    return evaluations
                    
        except Exception as e:
            logger.warning(f"宽松提取方法也失败: {e}")
        
        # 最后使用简化评分
        logger.warning("所有解析方法失败，使用简化评分作为备选")
        return self._simple_grading(compressed_criteria, {})
    
    def _filter_toc_content(self, text: str) -> str:
        """过滤掉目录页内容"""
        if not text:
            return text
        
        # 目录页关键词
        toc_keywords = [
            'table of contents',
            '目录',
            'contents',
            '目 录',
            'paper 1 exemplar',
            'paper 2 exemplar',
            'level 5',
            'level 6'
        ]
        
        # 按行分割文本
        lines = text.split('\n')
        filtered_lines = []
        skip_mode = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # 检查是否是目录页标题行
            if any(keyword in line_lower for keyword in toc_keywords):
                skip_mode = True
                continue
            
            # 如果遇到实际内容（包含数字、公式、中文等），停止跳过
            if skip_mode:
                # 检查是否是实际内容行（包含数字、中文、公式符号等）
                has_content = any([
                    any(c.isdigit() for c in line),  # 包含数字
                    any('\u4e00' <= c <= '\u9fff' for c in line),  # 包含中文
                    any(c in line for c in ['=', '+', '-', '×', '÷', '(', ')']),  # 包含公式符号
                    len(line.strip()) > 20  # 长行可能是内容
                ])
                
                if has_content:
                    skip_mode = False
                    filtered_lines.append(line)
                # 否则继续跳过（可能是目录项）
            else:
                filtered_lines.append(line)
        
        result = '\n'.join(filtered_lines).strip()
        
        # 如果过滤后内容太少，返回原始文本
        if len(result) < len(text) * 0.3:
            logger.warning("过滤后内容过少，使用原始文本")
            return text
        
        return result
    
    def _simple_grading(self, compressed_criteria: List[Dict], quick_checks: Dict) -> List[Dict]:
        """简化评分（降级方案）"""
        evaluations = []
        for criterion in compressed_criteria:
            cid = criterion['id']
            pts = criterion['pts']
            desc = criterion.get('desc', '')
            score_earned = pts * 0.8  # 默认80%分数
            
            evaluations.append({
                'criterion_id': cid,
                'score_earned': score_earned,
                'max_score': pts,
                'is_met': score_earned >= pts * 0.5,
                'satisfaction_level': '部分满足',
                'justification': f"基于快速检查: {quick_checks.get(cid, '默认评分')}",
                'feedback': '请查看详细批改结果',
                'evidence': ['答案已检查'],
                'student_work': quick_checks.get(cid, '已检查学生作答'),
                'matched_criterion': desc[:100] if desc else '已评估'
            })
        return evaluations
