#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RubricInterpreterAgent - 评分标准解析Agent
解析评分标准，提取评分点和分值
"""

import logging
import json
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

from ..state import GradingState
from ..multimodal_models import RubricUnderstanding, GradingCriterion
from ..prompts.multimodal_prompts import format_rubric_interpretation_prompt
from ...llm_client import LLMClient

logger = logging.getLogger(__name__)


class RubricInterpreterAgent:
    """评分标准解析Agent"""

    def __init__(self):
        self.name = "RubricInterpreterAgent"
        # 使用 Gemini 2.5 Pro 作为视觉模型，提供强大的多模态能力和复杂推理
        # 启用 high reasoning_effort 以获得最佳的批改标准理解
        self.llm_client = LLMClient(
            provider='openrouter',
            model='google/gemini-2.5-pro-exp-03-25'
        )
        self.reasoning_effort = "high"  # 启用高强度思考模式

    async def __call__(self, state: GradingState) -> GradingState:
        """执行评分标准解析"""
        logger.info(f"{self.name} 开始处理...")

        try:
            # 获取评分标准文件
            marking_files = state.get('marking_multimodal_files', [])
            if not marking_files:
                logger.warning("没有评分标准文件，使用默认标准")
                return {
                    'rubric_understanding': self._default_rubric()
                }

            # 处理第一个评分标准文件
            marking_file = marking_files[0]
            modality_type = marking_file['modality_type']
            content = marking_file['content_representation']

            logger.info(f"处理评分标准文件，模态类型: {modality_type}")

            # 根据模态类型选择处理方式
            if modality_type == 'pdf_image':
                # PDF文件：直接使用 Vision API 处理原始 PDF，不转换为图片
                pdf_file_path = marking_file.get('file_path')
                if pdf_file_path:
                    logger.info(f"检测到PDF文件，直接使用Vision API处理: {pdf_file_path}")
                    rubric_understanding = await self._extract_and_parse_rubric_from_pdf(pdf_file_path)

                    # 直接返回解析结果
                    logger.info(f"Vision API深度解析完成，共 {len(rubric_understanding['criteria'])} 个评分点")
                    return {
                        'rubric_understanding': rubric_understanding,
                        'rubric_parsing_result': {
                            'rubric_id': rubric_understanding['rubric_id'],
                            'total_points': rubric_understanding['total_points'],
                            'criteria_count': len(rubric_understanding['criteria']),
                            'parsing_method': 'vision_api_pdf_direct'
                        }
                    }
                else:
                    logger.warning("PDF文件路径为空，无法使用Vision API解析")
                    return {'rubric_understanding': self._default_rubric()}

            # 对于文本类型的评分标准，使用原有的文本提取逻辑
            rubric_text = ""
            if modality_type == 'text':
                rubric_text = content['text']
            elif modality_type == 'pdf_text':
                rubric_text = content['text']

            # 解析评分标准（文本类型）
            if rubric_text and len(rubric_text.strip()) > 10:
                understanding = await self._interpret_rubric(rubric_text)
            else:
                logger.warning("评分标准文本为空或过短，使用默认标准")
                understanding = self._default_rubric()

            # 记录详细的解析结果
            criteria_count = len(understanding.get('criteria', []))
            total_points = understanding.get('total_points', 0)
            logger.info(f"{self.name} 处理完成")
            logger.info(f"   共解析出 {criteria_count} 个评分点")
            logger.info(f"   总分: {total_points} 分")

            # 打印每个评分点的详细信息
            for i, criterion in enumerate(understanding.get('criteria', []), 1):
                logger.info(f"   评分点{i}: [{criterion.get('criterion_id', 'N/A')}] {criterion.get('description', 'N/A')[:50]}... ({criterion.get('points', 0)}分)")

            # 保存原始文本用于调试
            understanding['raw_rubric_text'] = rubric_text[:500]  # 保存前500字符用于调试

            # 只返回需要更新的字段，避免并发更新冲突
            # 注意：不返回progress_percentage和current_step，因为并行节点会冲突
            return {
                'rubric_understanding': understanding
            }

        except Exception as e:
            logger.error(f"{self.name} 失败: {e}")
            return {
                'errors': [{
                    'step': 'rubric_interpretation',
                    'error': str(e),
                    'timestamp': str(datetime.now())
                }],
                'rubric_understanding': self._default_rubric()
            }

    async def _interpret_rubric(self, rubric_text: str) -> RubricUnderstanding:
        """解析评分标准"""
        # 检查文本长度，如果太长则分批处理
        text_length = len(rubric_text)
        logger.info(f"评分标准文本长度: {text_length} 字符")

        # 如果文本很长（超过20000字符），使用分批处理策略
        if text_length > 20000:
            logger.info("评分标准文本较长，使用分批处理策略")
            return await self._interpret_rubric_in_batches(rubric_text)

        prompt = format_rubric_interpretation_prompt(rubric_text)

        messages = [
            {"role": "system", "content": "你是一位资深教育专家，擅长解析评分标准。请确保输出完整的JSON，包含所有题目的评分点。"},
            {"role": "user", "content": prompt}
        ]

        try:
            # 不限制 max_tokens，让模型输出完整的评分标准
            # 使用 high reasoning_effort 以获得最佳的批改标准理解
            response = self.llm_client.chat(messages, temperature=0.2, reasoning_effort=self.reasoning_effort)
            logger.info(f"LLM响应长度: {len(response)} 字符")

            # 检查响应是否可能被截断
            if response.rstrip().endswith('...') or (response.count('{') > response.count('}')):
                logger.warning("LLM响应可能被截断，尝试分批处理")
                return await self._interpret_rubric_in_batches(rubric_text)

            return self._parse_rubric(response, rubric_text)
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._parse_simple_rubric(rubric_text)

    def _parse_rubric(self, response: str, rubric_text: str = None) -> RubricUnderstanding:
        """解析LLM响应"""
        import re

        # 尝试提取JSON（支持多行JSON和代码块）
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start < 0 or json_end <= json_start:
            logger.warning("未找到JSON内容，使用默认标准")
            return self._default_rubric()

        json_str = response[json_start:json_end]

        # 移除代码块标记
        json_str = json_str.replace('```json', '').replace('```', '').strip()

        # 如果JSON字符串以{开头但可能没有正确结束，尝试修复
        if json_str.startswith('{') and not json_str.rstrip().endswith('}'):
            # 尝试找到最后一个完整的}
            last_brace = json_str.rfind('}')
            if last_brace > len(json_str) * 0.8:  # 如果最后一个}在80%位置之后
                json_str = json_str[:last_brace+1]
                logger.info(f"JSON可能未完整，截断到最后一个}}，新长度: {len(json_str)}")

        # 记录JSON字符串长度用于调试
        logger.info(f"准备解析JSON，长度: {len(json_str)} 字符")
        if len(json_str) > 10000:
            logger.info(f"JSON很长，前500字符: {json_str[:500]}")
            logger.info(f"JSON后500字符: {json_str[-500:]}")

        # 多次尝试解析，逐步修复JSON问题
        for attempt in range(5):  # 增加到5次尝试
            try:
                # 尝试直接解析
                result = json.loads(json_str)

                # 转换criteria为GradingCriterion类型
                criteria = []
                criteria_list = result.get('criteria', [])

                logger.info(f"解析到 {len(criteria_list)} 个评分点")

                for c in criteria_list:
                    criterion_id = c.get('criterion_id', '')
                    description = c.get('description', '')
                    points = float(c.get('points', 0))
                    question_id = c.get('question_id', '')

                    # 如果question_id为空，尝试从criterion_id提取
                    if not question_id and criterion_id:
                        if '_' in criterion_id:
                            question_id = criterion_id.split('_')[0]
                        elif criterion_id.startswith('Q'):
                            # 提取Q后面的数字
                            import re
                            match = re.match(r'Q(\d+)', criterion_id)
                            if match:
                                question_id = f"Q{match.group(1)}"

                    # 如果仍然没有question_id，记录警告
                    if not question_id:
                        logger.warning(f"评分点 {criterion_id} 缺少question_id，尝试从criterion_id提取")
                        if '_' in criterion_id:
                            question_id = criterion_id.split('_')[0]
                        else:
                            question_id = 'UNKNOWN'

                    # 记录每个评分点的详细信息
                    logger.info(f"  评分点: [{criterion_id}] 题目: {question_id}, {description[:50]}... ({points}分)")
                    if c.get('alternative_methods'):
                        logger.info(f"    另类解法: {len(c.get('alternative_methods', []))} 种")
                    if c.get('scoring_criteria'):
                        logger.info(f"    得分条件: 满分={c.get('scoring_criteria', {}).get('full_credit', 'N/A')[:30]}...")

                    # 创建详细的评分标准对象（包含所有字段）
                    criterion_dict = {
                        'criterion_id': criterion_id,
                        'question_id': question_id,
                        'description': description,
                        'points': points,
                        'evaluation_method': c.get('evaluation_method', 'semantic'),
                        'keywords': c.get('keywords'),
                        'required_elements': c.get('required_elements'),
                        'detailed_requirements': c.get('detailed_requirements'),
                        'standard_answer': c.get('standard_answer'),
                        'scoring_criteria': c.get('scoring_criteria'),
                        'alternative_methods': c.get('alternative_methods'),
                        'common_mistakes': c.get('common_mistakes')
                    }
                    # 移除None值
                    criterion_dict = {k: v for k, v in criterion_dict.items() if v is not None}
                    criteria.append(criterion_dict)

                # 验证解析结果
                if len(criteria) == 0:
                    logger.warning("解析后没有评分点，使用默认标准")
                    break

                # 检查是否只解析出1个评分点（可能是解析失败）
                if len(criteria) == 1 and criteria[0].get('points', 0) == 100.0:
                    logger.warning("只解析出1个评分点且为100分，可能是解析失败")
                    # 记录原始响应用于调试
                    logger.warning(f"原始响应前1000字符: {response[:1000]}")
                    break

                total_points = float(result.get('total_points', sum(c.get('points', 0) for c in criteria)))

                # 检查解析到的题目数量
                question_ids = set()
                for c in criteria:
                    qid = c.get('question_id', '')
                    if qid:
                        question_ids.add(qid)

                logger.info(f"评分标准解析成功: {len(criteria)}个评分点，{len(question_ids)}道题，总分: {total_points}分")
                logger.info(f"解析到的题目: {sorted(question_ids)}")

                # 如果题目数量明显偏少（如只有3道题但应该有19道），发出警告
                if len(question_ids) < 10:
                    logger.warning(f"警告：只解析到{len(question_ids)}道题，可能不完整！")
                    logger.warning(f"   解析到的题目: {sorted(question_ids)}")
                    logger.warning(f"   如果应该有19道题，请检查：")
                    logger.warning(f"   1. 评分标准文本是否完整提取（检查PDF页面是否全部处理）")
                    logger.warning(f"   2. LLM响应是否被截断（检查max_tokens是否足够）")
                    logger.warning(f"   3. 评分标准文本中是否包含所有题目的信息")

                return RubricUnderstanding(
                    rubric_id=result.get('rubric_id', 'R1'),
                    criteria=criteria,
                    total_points=total_points,
                    grading_rules=result.get('grading_rules', {}),
                    strictness_guidance=result.get('strictness_guidance')
                )

            except json.JSONDecodeError as e:
                error_pos = getattr(e, 'pos', None)
                error_msg = str(e)

                if attempt < 4:  # 前4次尝试修复
                    logger.warning(f"JSON解析失败（尝试{attempt+1}/5）: {error_msg}")

                    # 修复策略1: 修复分隔符问题
                    if 'Expecting' in error_msg and 'delimiter' in error_msg:
                        # 尝试修复常见的分隔符问题
                        json_str = json_str.replace(',,', ',').replace('{,', '{').replace(',}', '}')
                        # 修复缺少逗号的情况（在}和{之间）
                        json_str = re.sub(r'\}\s*\{', '}, {', json_str)
                        # 修复缺少逗号的情况（在}和"之间）
                        json_str = re.sub(r'\}\s*"', '}, "', json_str)

                    # 修复策略1.5: 修复未终止的字符串
                    elif 'Unterminated string' in error_msg:
                        logger.info("检测到未终止的字符串，尝试修复...")
                        # 找到未终止字符串的位置
                        if error_pos:
                            # 从错误位置向前查找最近的未闭合引号
                            # 简单方法：在错误位置附近添加闭合引号
                            # 但更安全的方法是：找到最后一个完整的JSON对象
                            # 尝试找到最后一个完整的}
                            last_brace = json_str.rfind('}')
                            if last_brace > error_pos - 1000:  # 如果最后一个}在错误位置附近
                                # 尝试截断到最后一个完整的JSON对象
                                # 找到匹配的{
                                brace_count = 0
                                start_pos = json_str.rfind('{', 0, last_brace)
                                if start_pos >= 0:
                                    # 验证这是一个完整的对象
                                    test_str = json_str[start_pos:last_brace+1]
                                    if test_str.count('{') == test_str.count('}'):
                                        json_str = json_str[start_pos:last_brace+1]
                                        logger.info(f"截断到最后一个完整JSON对象，新长度: {len(json_str)}")
                                    else:
                                        # 如果截断后仍然不完整，尝试更保守的方法
                                        # 在错误位置之前找到最后一个完整的字符串值
                                        logger.warning("截断后JSON仍不完整，尝试其他修复方法")
                        else:
                            # 如果无法确定错误位置，尝试找到最后一个完整的}
                            last_brace = json_str.rfind('}')
                            if last_brace > len(json_str) * 0.9:  # 如果最后一个}在90%位置之后
                                json_str = json_str[:last_brace+1]
                                logger.info("截断到最后一个}，尝试修复未终止字符串")

                    # 修复策略2: 修复LaTeX转义（避免使用可变宽度look-behind）
                    elif 'Invalid \\escape' in error_msg or '\\escape' in error_msg:
                        logger.info(f"检测到转义字符错误（位置: {error_pos}），尝试修复...")
                        # 使用更简单可靠的方法：逐字符扫描并修复
                        # 只在字符串值内部修复转义问题
                        fixed_parts = []
                        i = 0
                        in_string = False
                        string_start = -1

                        while i < len(json_str):
                            char = json_str[i]

                            if char == '"' and (i == 0 or json_str[i-1] != '\\' or (i > 1 and json_str[i-2] == '\\')):
                                # 字符串开始或结束
                                in_string = not in_string
                                if in_string:
                                    string_start = len(fixed_parts)
                                fixed_parts.append(char)
                                i += 1
                            elif in_string and char == '\\' and i + 1 < len(json_str):
                                # 在字符串内部遇到反斜杠
                                next_char = json_str[i + 1]
                                # 检查是否是合法的转义序列
                                if next_char in '\\/bfnrt"':
                                    fixed_parts.append('\\' + next_char)
                                    i += 2
                                elif next_char == 'u' and i + 5 < len(json_str) and all(c in '0123456789abcdefABCDEF' for c in json_str[i+2:i+6]):
                                    # Unicode转义序列 \uXXXX
                                    fixed_parts.append(json_str[i:i+6])
                                    i += 6
                                else:
                                    # 非法的转义序列，转义反斜杠
                                    fixed_parts.append('\\\\')
                                    fixed_parts.append(next_char)
                                    i += 2
                            else:
                                fixed_parts.append(char)
                                i += 1

                        json_str = ''.join(fixed_parts)
                        logger.info(f"转义字符修复完成，修复后长度: {len(json_str)}")

                    logger.info(f"尝试修复JSON（错误位置: {error_pos}，尝试{attempt+1}/5）...")
                else:
                    # 最后一次尝试失败，记录详细信息
                    if attempt == 4:  # 最后一次尝试
                        logger.error(f"JSON解析最终失败: {error_msg}")
                        logger.error(f"错误位置: {error_pos}")
                        if error_pos:
                            start = max(0, error_pos - 500)
                            end = min(len(json_str), error_pos + 500)
                            logger.error(f"错误位置附近的内容: {json_str[start:end]}")
                        logger.error(f"JSON字符串长度: {len(json_str)}")
                        logger.error(f"响应内容前2000字符: {response[:2000]}")
                        # 尝试保存失败的JSON到文件用于调试
                        try:
                            debug_file = Path(__file__).parent.parent.parent / "debug_json.txt"
                            with open(debug_file, 'w', encoding='utf-8') as f:
                                f.write("=== 原始响应 ===\n")
                                f.write(response)
                                f.write("\n\n=== JSON字符串 ===\n")
                                f.write(json_str)
                            logger.info(f"失败的JSON已保存到: {debug_file}")
                        except Exception as save_error:
                            logger.warning(f"保存调试文件失败: {save_error}")
                        break
            except Exception as e:
                logger.error(f"解析失败: {e}")
                logger.error(f"响应内容前1000字符: {response[:1000]}")
                break

        logger.warning("所有JSON解析尝试失败，尝试使用文本解析作为备用方案...")
        # 如果有rubric_text，尝试使用简单解析
        if rubric_text:
            logger.info("使用文本解析作为备用方案...")
            return self._parse_simple_rubric(rubric_text)
        else:
            logger.error("JSON解析完全失败，且没有rubric_text可用")
            logger.error("建议：检查LLM响应是否被截断，或尝试增加max_tokens")
            return self._default_rubric()

    def _parse_simple_rubric(self, rubric_text: str) -> RubricUnderstanding:
        """简单解析评分标准（文本分析）- 改进版，能识别题目编号"""
        import re

        # 尝试提取评分点和分值，并识别题目编号
        criteria = []
        total_points = 0.0
        current_question_id = None
        criterion_counter = {}  # 记录每个题目的评分点计数

        # 查找包含分值的行
        lines = rubric_text.split('\n')
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 首先尝试识别题目编号（Q1, Q2, 题目1, Question 1等）
            question_patterns = [
                r'Q(\d+)',  # Q1, Q2, Q17等
                r'题目\s*(\d+)',  # 题目1, 题目2等
                r'Question\s*(\d+)',  # Question 1等
                r'^(\d+)[.、：:]',  # 1., 2.等（行首）
            ]

            for pattern in question_patterns:
                match = re.search(pattern, line_stripped, re.IGNORECASE)
                if match:
                    q_num = match.group(1)
                    current_question_id = f"Q{q_num}"
                    if current_question_id not in criterion_counter:
                        criterion_counter[current_question_id] = 0
                    logger.info(f"识别到题目: {current_question_id}")
                    break

            # 匹配评分点模式：如 "1. xxx (5分)" 或 "评分点1：xxx 5分" 或 "Q17_C1: xxx (1分)"
            patterns = [
                r'(Q\d+_C\d+)[：:]\s*(.+?)\s*[（(]?(\d+(?:\.\d+)?)\s*分[）)]?',  # Q17_C1: xxx (1分)
                r'(\d+)[.、：:]\s*(.+?)\s*[（(]?(\d+(?:\.\d+)?)\s*分[）)]?',  # 1. xxx (5分)
                r'(.+?)\s*[（(]?(\d+(?:\.\d+)?)\s*分[）)]?',  # xxx (5分)
            ]

            for pattern in patterns:
                match = re.search(pattern, line_stripped)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        # 确定criterion_id和question_id
                        if len(groups) == 3 and groups[0].startswith('Q') and '_C' in groups[0]:
                            # 格式：Q17_C1: xxx (1分)
                            criterion_id = groups[0]
                            question_id = criterion_id.split('_')[0]
                            description = groups[1].strip()
                            points = float(groups[2])
                        elif len(groups) == 3:
                            # 格式：1. xxx (5分)
                            if current_question_id:
                                criterion_counter[current_question_id] += 1
                                criterion_id = f"{current_question_id}_C{criterion_counter[current_question_id]}"
                                question_id = current_question_id
                            else:
                                criterion_id = f"C{i+1}"
                                question_id = 'UNKNOWN'
                            description = groups[1].strip()
                            points = float(groups[2])
                        else:
                            # 格式：xxx (5分)
                            if current_question_id:
                                criterion_counter[current_question_id] += 1
                                criterion_id = f"{current_question_id}_C{criterion_counter[current_question_id]}"
                                question_id = current_question_id
                            else:
                                criterion_id = f"C{i+1}"
                                question_id = 'UNKNOWN'
                            description = groups[0].strip()
                            points = float(groups[1])

                        criteria.append(GradingCriterion(
                            criterion_id=criterion_id,
                            question_id=question_id,
                            description=description,
                            points=points,
                            evaluation_method='semantic',
                            keywords=None,
                            required_elements=None
                        ))
                        total_points += points
                        logger.info(f"文本解析提取评分点: [{criterion_id}] 题目: {question_id}, {description[:50]}... ({points}分)")
                        break

        if not criteria:
            # 如果没有找到评分点，创建默认评分点
            logger.warning("文本解析未找到任何评分点，使用默认标准")
            criteria = [
                GradingCriterion(
                    criterion_id="C1",
                    description="答案正确性",
                    points=100.0,
                    evaluation_method='semantic',
                    keywords=None,
                    required_elements=None
                )
            ]
            total_points = 100.0
        else:
            # 统计题目数量
            question_ids = set(c.get('question_id', '') for c in criteria if c.get('question_id') != 'UNKNOWN')
            logger.info(f"文本解析成功: {len(criteria)}个评分点，{len(question_ids)}道题，总分: {total_points}分")
            if question_ids:
                logger.info(f"解析到的题目: {sorted(question_ids)}")

        return RubricUnderstanding(
            rubric_id='R1_TEXT_PARSED',
            criteria=criteria,
            total_points=total_points,
            grading_rules={},
            strictness_guidance=None
        )

    async def _extract_and_parse_rubric_from_pdf(self, pdf_file_path: str) -> RubricUnderstanding:
        """直接从PDF文件提取并解析评分标准（使用Vision API）- 一次性处理整个PDF"""
        try:
            import base64
            from pathlib import Path

            logger.info(f"开始从PDF文件中提取并解析评分标准: {Path(pdf_file_path).name}")
            logger.info("使用Vision API直接处理PDF文件，无需转换为图片")

            # 读取PDF文件并转换为base64
            with open(pdf_file_path, 'rb') as f:
                pdf_bytes = f.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # 构建深度解析的 prompt（精简版）
            prompt = f"""分析PDF中的评分标准，提取所有评分点。

**核心任务：**
1. 识别题目编号（如 1., 8(a), 15(a)）
2. 识别分值标记：
   - "1M" = 1分方法分, "2A" = 2分准确分
   - "1M+1A" = 拆分成2个评分点（1M + 1A）
3. 识别多种解法（Case 1/Case 2, Method 1/Method 2）：
   - 为每种方法生成独立评分点
   - criterion_id 格式：Q8a_C1_Case1, Q15_C1_Method1

**关键规则：**
- 每个评分点只识别一次，不重复
- 不遗漏任何评分点
- 数学公式避免反斜杠（\\frac → a/b, \\times → ×）

**JSON 输出格式：**
```json
{{
  "criteria": [
    {{
      "criterion_id": "Q1_C1",
      "question_id": "Q1",
      "description": "评分点描述",
      "detailed_requirements": "详细要求",
      "points": 1.0,
      "mark_type": "M",
      "standard_answer": "标准答案",
      "evaluation_method": "manual",
      "scoring_criteria": {{"full_credit": "满分条件", "no_credit": "不得分条件"}},
      "common_mistakes": ["常见错误"],
      "keywords": ["关键词"]
    }}
  ]
}}
```

**示例（多种解法）：**
Q8a 有 Case 1 (2分) 和 Case 2 (1分)：
- criterion_id: "Q8a_C1_Case1", points: 2.0, description: "Case 1: 完整证明含理由"
- criterion_id: "Q8a_C2_Case2", points: 1.0, description: "Case 2: 正确证明但不含理由"

只返回 JSON，不要添加解释。

请开始分析："""

            # 构建Vision API请求
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:application/pdf;base64,{pdf_base64}"
                        }
                    }
                ]
            }]

            logger.info(f"使用Vision API一次性解析整个PDF文件...")
            # 不限制 max_tokens，让模型输出完整的评分标准
            # 使用 temperature=0.0 以获得最大的确定性和稳定性
            # 使用 high reasoning_effort 以获得最佳的批改标准理解
            response = self.llm_client.chat(messages, temperature=0.0, reasoning_effort=self.reasoning_effort)

            if response.strip():
                logger.info(f"解析完成，响应长度: {len(response)} 字符")

                # 解析JSON响应
                parsed_result = self._parse_rubric(response, "")
                return parsed_result
            else:
                logger.warning("Vision API响应为空")
                return self._default_rubric()

        except Exception as e:
            logger.error(f"从PDF文件提取并解析评分标准失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._default_rubric()

    async def _extract_and_parse_rubric_from_images(self, pages: List[Dict]) -> RubricUnderstanding:
        """从图片页面直接提取并解析评分标准（使用Vision API）- 一次性处理所有页面

        注意：此方法已被 _extract_and_parse_rubric_from_pdf 替代，建议直接使用PDF文件
        """
        if not pages:
            return self._default_rubric()

        logger.info(f"开始从图片中提取并解析评分标准，共{len(pages)}页")
        logger.info("使用一次性处理策略，将所有页面一起发送给 Vision API")

        try:
            # 构建深度解析的 prompt（精简版）
            prompt = f"""分析图片中的评分标准，提取所有评分点。

**核心任务：**
1. 识别题目编号（如 1., 8(a), 15(a)）
2. 识别分值标记：
   - "1M" = 1分方法分, "2A" = 2分准确分
   - "1M+1A" = 拆分成2个评分点（1M + 1A）
3. 识别多种解法（Case 1/Case 2, Method 1/Method 2）：
   - 为每种方法生成独立评分点
   - criterion_id 格式：Q8a_C1_Case1, Q15_C1_Method1

**关键规则：**
- 每个评分点只识别一次，不重复
- 不遗漏任何评分点
- 数学公式避免反斜杠（\\frac → a/b, \\times → ×）

**JSON 输出格式：**
```json
{{
  "criteria": [
    {{
      "criterion_id": "Q1_C1",
      "question_id": "Q1",
      "description": "评分点描述",
      "detailed_requirements": "详细要求",
      "points": 1.0,
      "mark_type": "M",
      "standard_answer": "标准答案",
      "evaluation_method": "manual",
      "scoring_criteria": {{"full_credit": "满分条件", "no_credit": "不得分条件"}},
      "common_mistakes": ["常见错误"],
      "keywords": ["关键词"]
    }}
  ]
}}
```

**示例（多种解法）：**
Q8a 有 Case 1 (2分) 和 Case 2 (1分)：
- criterion_id: "Q8a_C1_Case1", points: 2.0, description: "Case 1: 完整证明含理由"
- criterion_id: "Q8a_C2_Case2", points: 1.0, description: "Case 2: 正确证明但不含理由"

只返回 JSON，不要添加解释。

请开始分析："""

            content = [{"type": "text", "text": prompt}]

            # 添加所有页面
            for page in pages:
                base64_data = page.get('base64_data', '')
                mime_type = page.get('mime_type', 'image/png')
                if base64_data:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_data}"
                        }
                    })

            if len(content) > 1:  # 确保有图片内容
                messages = [{"role": "user", "content": content}]

                logger.info(f"使用Vision API一次性解析所有{len(pages)}页评分标准...")
                # 不限制 max_tokens，让模型输出完整的评分标准
                # 使用 temperature=0.0 以获得最大的确定性和稳定性
                # 使用 high reasoning_effort 以获得最佳的批改标准理解
                response = self.llm_client.chat(messages, temperature=0.0, reasoning_effort=self.reasoning_effort)

                if response.strip():
                    logger.info(f"解析完成，响应长度: {len(response)} 字符")

                    # 尝试解析 JSON
                    try:
                        import json

                        # 提取 JSON 部分（可能包含在 ```json ... ``` 中）
                        if '```json' in response:
                            start_marker = '```json'
                            end_marker = '```'
                            start_idx = response.find(start_marker)
                            if start_idx != -1:
                                json_start = start_idx + len(start_marker)
                                end_idx = response.find(end_marker, json_start)
                                if end_idx != -1:
                                    json_str = response[json_start:end_idx].strip()
                                else:
                                    json_str = response[json_start:].strip()
                            else:
                                json_str = response.strip()
                        else:
                            json_str = response.strip()

                        result = json.loads(json_str)

                        # 提取 criteria
                        if 'criteria' in result:
                            all_criteria = result['criteria']
                            logger.info(f"成功解析，获得 {len(all_criteria)} 个评分点")
                        else:
                            logger.warning("JSON 中没有 criteria 字段")
                            all_criteria = []

                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析失败: {e}")
                        logger.error(f"响应内容前1000字符: {response[:1000]}")
                        all_criteria = []
            else:
                logger.warning("没有有效的图片内容")
                all_criteria = []

        except Exception as e:
            logger.error(f"Vision API处理失败: {e}")
            all_criteria = []

        # 构建最终的 RubricUnderstanding
        if not all_criteria:
            logger.warning("未能从图片中解析出任何评分点，使用默认标准")
            return self._default_rubric()

        # 计算总分，确保所有 points 都是有效的数字
        # 对于多种解法（如 Q8a_C1_Case1, Q8a_C2_Case2），只计算最高分值，避免重复计算
        total_points = 0.0

        # 按题目分组，识别多种解法
        # 关键：对于同一题目的多种解法（如 Q8a 的 Case1 和 Case2），应该按题目ID分组，而不是按 criterion_id 分组
        question_method_groups = {}  # 格式：{question_id: [criteria_list]}
        independent_criteria = []  # 独立评分点（不属于多种解法）

        for c in all_criteria:
            criterion_id = c.get('criterion_id', '')
            question_id = c.get('question_id', '')

            # 识别是否是多种解法（criterion_id 包含 _Case 或 _Method）
            if '_Case' in criterion_id or '_Method' in criterion_id:
                # 按题目ID分组（如 Q8a 的所有 Case 都归为一组）
                if question_id not in question_method_groups:
                    question_method_groups[question_id] = []
                question_method_groups[question_id].append(c)
            else:
                # 普通评分点，加入独立列表
                independent_criteria.append(c)

        # 计算独立评分点的总分
        for c in independent_criteria:
            criterion_id = c.get('criterion_id', '')
            points = c.get('points', 0.0)
            if points is not None:
                try:
                    total_points += float(points)
                except (ValueError, TypeError):
                    logger.warning(f"评分点 {criterion_id} 的分值无效: {points}")
                    pass

        # 对于多种解法的评分点，只计算最高分值
        for question_id, criteria_list in question_method_groups.items():
            max_points = 0.0
            for c in criteria_list:
                points = c.get('points', 0.0)
                if points is not None:
                    try:
                        max_points = max(max_points, float(points))
                    except (ValueError, TypeError):
                        logger.warning(f"评分点 {c.get('criterion_id', 'unknown')} 的分值无效: {points}")
                        pass
            total_points += max_points
            logger.info(f"题目 {question_id} 的多种解法: {len(criteria_list)} 种方法，最高分值 {max_points} 分")

        logger.info(f"评分标准解析完成，共 {len(all_criteria)} 个评分点，总分 {total_points} 分（已避免多种解法重复计算）")

        return RubricUnderstanding(
            rubric_id='VISION_PARSED',
            criteria=all_criteria,
            total_points=total_points,
            grading_rules={},
            strictness_guidance=None
        )

    async def _extract_text_from_pdf_file(self, pdf_file_path: str) -> str:
        """直接从PDF文件路径使用Vision API提取文本"""
        try:
            import base64
            from pathlib import Path

            # 读取PDF文件并转换为base64
            with open(pdf_file_path, 'rb') as f:
                pdf_bytes = f.read()

            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # 构建Vision API请求
            prompt = "请提取PDF中的所有文字内容，包括评分标准、评分点、分值、题目编号等信息。请完整提取所有内容，包括所有题目（Q1-Q19）。只返回文字内容，不要添加任何解释。"

            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:application/pdf;base64,{pdf_base64}"
                        }
                    }
                ]
            }]

            logger.info(f"使用Vision API直接从PDF文件提取文本: {Path(pdf_file_path).name}")
            # 设置max_tokens为1000000以确保完整提取
            response = self.llm_client.chat(messages, temperature=0.1, max_tokens=1000000)

            if response.strip():
                logger.info(f"PDF文本提取完成，响应长度: {len(response)} 字符")
                return response.strip()
            else:
                logger.warning("PDF文本提取为空")
                return ""

        except Exception as e:
            logger.error(f"从PDF文件提取文本失败: {e}")
            return ""


    async def _interpret_rubric_in_batches(self, rubric_text: str) -> RubricUnderstanding:
        """分批处理评分标准（用于处理长文本）"""
        logger.info("开始分批处理评分标准...")

        # 策略：按题目分批处理
        import re

        # 识别题目编号（支持多种格式：Q1, Question 1, 题目1, 1.等）
        # 优先匹配行首的数字+点号格式（如 "1.", "2."），这是最常见的格式
        question_pattern = r'(?:^|\n)(\d+)\.\s'
        matches = list(re.finditer(question_pattern, rubric_text, re.MULTILINE))

        # 如果没找到，尝试其他格式
        if not matches:
            question_pattern = r'(?:Q|Question\s+|题目\s*)(\d+)'
            matches = list(re.finditer(question_pattern, rubric_text, re.IGNORECASE))

        if not matches:
            logger.warning("未找到题目编号，使用简单解析")
            return self._parse_simple_rubric(rubric_text)

        logger.info(f"识别到 {len(matches)} 个题目标记")

        # 按题目分割文本
        question_texts = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(rubric_text)
            question_id = f"Q{match.group(1)}"
            question_text = rubric_text[start:end].strip()
            question_texts.append((question_id, question_text))

        logger.info(f"分割成 {len(question_texts)} 个题目段落")

        # 分批处理（每批处理5道题）
        batch_size = 5
        all_criteria = []
        total_points = 0.0

        for batch_start in range(0, len(question_texts), batch_size):
            batch_end = min(batch_start + batch_size, len(question_texts))
            batch = question_texts[batch_start:batch_end]

            # 合并这一批的文本
            batch_text = "\n\n".join([f"{qid}:\n{text}" for qid, text in batch])
            batch_qids = [qid for qid, _ in batch]

            logger.info(f"处理批次 {batch_start//batch_size + 1}/{(len(question_texts) + batch_size - 1)//batch_size}: {batch_qids}")

            # 调用LLM解析这一批
            prompt = format_rubric_interpretation_prompt(batch_text)
            messages = [
                {"role": "system", "content": f"你是一位资深教育专家，擅长解析评分标准。请解析以下题目的评分标准：{', '.join(batch_qids)}"},
                {"role": "user", "content": prompt}
            ]

            try:
                response = self.llm_client.chat(messages, temperature=0.2)
                batch_result = self._parse_rubric(response, batch_text)

                # 合并结果
                batch_criteria = batch_result.get('criteria', [])
                all_criteria.extend(batch_criteria)
                total_points += batch_result.get('total_points', 0)

                logger.info(f"批次 {batch_start//batch_size + 1} 解析完成: {len(batch_criteria)} 个评分点")
            except Exception as e:
                logger.error(f"批次 {batch_start//batch_size + 1} 解析失败: {e}")
                continue

        logger.info(f"分批处理完成: 共 {len(all_criteria)} 个评分点，总分 {total_points}")

        return RubricUnderstanding(
            rubric_id='R1_BATCHED',
            criteria=all_criteria,
            total_points=total_points,
            grading_rules={'partial_credit': 'yes'},
            strictness_guidance=None
        )

    def _default_rubric(self) -> RubricUnderstanding:
        """默认评分标准"""
        return RubricUnderstanding(
            rubric_id='R_DEFAULT',
            criteria=[
                GradingCriterion(
                    criterion_id="C1",
                    description="答案完整性和正确性",
                    points=100.0,
                    evaluation_method='semantic',
                    keywords=None,
                    required_elements=None
                )
            ],
            total_points=100.0,
            grading_rules={'partial_credit': 'yes'},
            strictness_guidance=None
        )
