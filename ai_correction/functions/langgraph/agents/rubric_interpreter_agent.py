#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RubricInterpreterAgent - 评分标准解析Agent
解析评分标准，提取评分点和分值
"""

import logging
import json
import os
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
        # 使用 Gemini 3 Pro 原生 API，支持真正的多模态 PDF 处理
        self.llm_client = LLMClient(
            provider='gemini',
            model='gemini-3-pro-preview'
        )
        self.reasoning_effort = None

    async def __call__(self, state: GradingState) -> GradingState:
        """执行评分标准解析"""
        logger.info(f"{self.name} 开始处理...")

        state.setdefault('step_results', {})
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

            # ????????????
            if modality_type in ['pdf', 'pdf_image', 'image']:
                pdf_file_path = marking_file.get('file_path') or content.get('file_path')
                if pdf_file_path:
                    file_type = "PDF" if modality_type in ['pdf', 'pdf_image'] else "图片"
                    logger.info(f"📄 检测到 {file_type} 评分标准，准备解析: path={pdf_file_path}, pages={content.get('page_count', 'unknown')}")
                    
                    logger.info(f"🔍 使用 Gemini 3 Pro 原生多模态解析评分标准 {file_type}: {pdf_file_path}")
                    rubric_understanding = await self._extract_and_parse_rubric_from_pdf(pdf_file_path)

                    criteria_num = len(rubric_understanding.get('criteria', []))
                    logger.info(f"Gemini 解析完成，提取到 {criteria_num} 个评分点")
                    self._record_step_trace(
                        state,
                        summary=f"Gemini 解析 {file_type}，提取 {criteria_num} 个评分点",
                        extra={
                            'criteria_count': criteria_num,
                            'total_points': rubric_understanding.get('total_points')
                        }
                    )
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
                    logger.warning(f"评分标准为 {modality_type} 但缺少文件路径，无法调用 Gemini 解析")
                    return {'rubric_understanding': self._default_rubric()}

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

            # 记录LLM调用轨迹
            self._record_step_trace(
                state,
                summary=f"解析评分标准，共 {criteria_count} 个评分点，总分 {total_points}",
                extra={
                    'criteria_count': criteria_count,
                    'total_points': total_points,
                    'source': 'text' if rubric_text else 'pdf'
                }
            )

            # 只返回需要更新的字段，避免并发更新冲突
            # 注意：不返回progress_percentage和current_step，因为并行节点会冲突
            return {
                'rubric_understanding': understanding
            }

        except Exception as e:
            logger.error(f"{self.name} ??: {e}")
            return {
                'errors': [{
                    'step': 'rubric_interpretation',
                    'error': str(e),
                    'timestamp': str(datetime.now())
                }],
                'rubric_understanding': self._default_rubric()
            }


    def _get_llm_timeout(self) -> int:
        """获取LLM请求的超时时间（秒）"""
        try:
            return int(os.getenv("RUBRIC_LLM_TIMEOUT", os.getenv("LLM_REQUEST_TIMEOUT", "30")))
        except Exception:
            return getattr(self.llm_client, "default_timeout", 30)

    def _record_step_trace(self, state: GradingState, summary: str, extra: Dict[str, Any] | None = None):
        """记录LLM调用轨迹，方便前端展示"""
        try:
            trace = dict(self.llm_client.last_call or {})
            trace['summary'] = summary
            if extra:
                trace.update(extra)
            state['step_results'][self.name] = trace
        except Exception as err:
            logger.warning(f"{self.name} 记录LLM轨迹失败: {err}")

    async def _extract_and_parse_rubric_from_images(self, pages: List[Dict]) -> RubricUnderstanding:
        """???????????????????????????"""
        if not pages:
            return self._default_rubric()
        try:
            logger.warning('???????????????????????')
            return self._default_rubric()
        except Exception:
            return self._default_rubric()


    def _extract_text_from_pdf_local(self, pdf_file_path: str) -> str:
        """??????????PDF???????????Vision??"""
        try:
            import PyPDF2
            with open(pdf_file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                texts = []
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        texts.append(page_text)
            result = "\n".join(texts).strip()
            if not result:
                logger.warning("??PDF??????")
            else:
                logger.info(f"????PDF??????? {len(result)}")
            return result
        except Exception as e:
            logger.warning(f"??PDF??????: {e}")
            return ""

    async def _extract_text_from_pdf_file(self, pdf_file_path: str) -> str:
        """???PDF???????????????????????????"""
        try:
            local_text = self._extract_text_from_pdf_local(pdf_file_path)
            if local_text:
                return local_text
        except Exception as e:
            logger.error(f"PDF??????: {e}")
        return ""

    async def _extract_and_parse_rubric_from_pdf(self, pdf_file_path: str) -> RubricUnderstanding:
        """
        使用 Gemini 3 Pro 原生多模态能力解析评分标准（支持 PDF 和图片）
        严格禁止文本提取，完全依赖 Gemini 原生多模态能力
        """
        try:
            # 检查文件类型
            from pathlib import Path
            file_ext = Path(pdf_file_path).suffix.lower()
            is_image = file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            
            # 使用 Gemini 原生多模态解析（PDF 或图片）
            prompt = format_rubric_interpretation_prompt("")
            messages = [{"role": "user", "content": prompt}]
            
            file_type = "图片" if is_image else "PDF"
            logger.info(f"📄 使用 Gemini 3 Pro 原生多模态解析 {file_type}: {pdf_file_path}")
            
            response = self.llm_client.chat(
                messages,
                temperature=0.2,
                max_tokens=8000,
                files=[pdf_file_path],
                thinking_level="high",
                timeout=self._get_llm_timeout()
            )
            rubric_understanding = self._parse_rubric(response, "")
            criteria_count = len(rubric_understanding.get('criteria', []))
            logger.info(f"✅ Gemini 3 Pro 成功解析 {file_type}，提取了 {criteria_count} 个评分点")
            return rubric_understanding

        except Exception as e:
            logger.error(f"❌ Gemini 3 Pro 解析失败: {e}")
            logger.warning("⚠️ 回退到默认评分标准")
            return self._default_rubric()

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

                logger.info(f"???? {batch_start//batch_size + 1} ???????: {len(batch_criteria)} ???????")
            except Exception as e:
                logger.error(f"???? {batch_start//batch_size + 1} ???????: {e}")
                continue

        logger.info(f"分批处理完成: 共 {len(all_criteria)} 个评分点，总分 {total_points}")

        return RubricUnderstanding(
            rubric_id='R1_BATCHED',
            criteria=all_criteria,
            total_points=total_points,
            grading_rules={'partial_credit': 'yes'},
            strictness_guidance=None
        )

    def _parse_rubric(self, response: str, rubric_text: str) -> RubricUnderstanding:
        """
        解析 LLM 返回的评分标准 JSON

        Args:
            response: LLM 返回的响应文本
            rubric_text: 原始评分标准文本（用于备用解析）

        Returns:
            RubricUnderstanding 对象
        """
        try:
            import json
            import re

            # 提取 JSON 部分 (支持 ```json 代码块)
            json_str = response

            # 移除 markdown 代码块标记
            json_str = re.sub(r'```json\s*', '', json_str)
            json_str = re.sub(r'```\s*', '', json_str)

            # 查找 JSON 对象
            json_start = json_str.find('{')
            json_end = json_str.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = json_str[json_start:json_end]

                # 尝试修复常见的 JSON 格式错误
                # 1. 修复未转义的换行符
                json_str = json_str.replace('\n', '\\n')
                # 2. 修复未转义的引号 (在字符串值中)
                # 这个比较复杂,暂时跳过

                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 解析失败 (第一次尝试): {e}")
                    # 尝试使用 json5 或更宽松的解析
                    # 如果还是失败,尝试提取部分信息
                    logger.info("尝试从响应中提取部分评分标准信息...")
                    return self._extract_criteria_from_text(response, rubric_text)

                # 转换为 RubricUnderstanding 格式
                criteria = []
                for c in result.get('criteria', []):
                    try:
                        criterion = GradingCriterion(
                            criterion_id=c.get('criterion_id', 'C1'),
                            question_id=c.get('question_id', ''),
                            description=c.get('description', ''),
                            detailed_requirements=c.get('detailed_requirements', ''),
                            points=float(c.get('points', 0)),
                            standard_answer=c.get('standard_answer', ''),
                            evaluation_method=c.get('evaluation_method', 'semantic'),
                            scoring_criteria=c.get('scoring_criteria', {}),
                            alternative_methods=c.get('alternative_methods', []),
                            keywords=c.get('keywords', []),
                            required_elements=c.get('required_elements', []),
                            common_mistakes=c.get('common_mistakes', [])
                        )
                        criteria.append(criterion)
                    except Exception as e:
                        logger.warning(f"跳过无效的评分点: {e}")
                        continue

                if not criteria:
                    logger.warning("未能从 JSON 中提取任何评分点")
                    return self._extract_criteria_from_text(response, rubric_text)

                return RubricUnderstanding(
                    rubric_id=result.get('rubric_id', 'R1'),
                    criteria=criteria,
                    total_points=float(result.get('total_points', sum(c.points for c in criteria))),
                    grading_rules=result.get('grading_rules', {'partial_credit': 'yes'}),
                    strictness_guidance=result.get('strictness_guidance', '')
                )
            else:
                logger.warning("响应中未找到 JSON，尝试从文本中提取")
                return self._extract_criteria_from_text(response, rubric_text)

        except Exception as e:
            logger.error(f"评分标准解析失败: {e}")
            return self._extract_criteria_from_text(response, rubric_text)

    def _extract_criteria_from_text(self, response: str, rubric_text: str) -> RubricUnderstanding:
        """
        从 LLM 响应文本中提取评分标准 (当 JSON 解析失败时使用)

        尝试从响应中提取 criterion_id, description, points 等信息
        """
        try:
            import re

            criteria = []
            total_points = 0.0

            # 尝试匹配评分点模式
            # 模式 1: "criterion_id": "Q1_C1", "description": "...", "points": 5
            pattern1 = r'"criterion_id"\s*:\s*"([^"]+)"[^}]*"description"\s*:\s*"([^"]+)"[^}]*"points"\s*:\s*(\d+(?:\.\d+)?)'
            matches1 = re.findall(pattern1, response, re.DOTALL)

            for criterion_id, description, points in matches1:
                # 提取 question_id
                question_id_match = re.match(r'(Q\d+)_', criterion_id)
                question_id = question_id_match.group(1) if question_id_match else ''

                criterion = GradingCriterion(
                    criterion_id=criterion_id,
                    question_id=question_id,
                    description=description[:200],  # 限制长度
                    points=float(points),
                    evaluation_method='semantic'
                )
                criteria.append(criterion)
                total_points += float(points)

            if criteria:
                logger.info(f"从文本中提取了 {len(criteria)} 个评分点")
                return RubricUnderstanding(
                    rubric_id='R_EXTRACTED',
                    criteria=criteria,
                    total_points=total_points,
                    grading_rules={'partial_credit': 'yes'},
                    strictness_guidance=None
                )
            else:
                logger.warning("无法从文本中提取评分点，尝试简单解析原始文本")
                return self._parse_simple_rubric(rubric_text)

        except Exception as e:
            logger.error(f"从文本提取评分标准失败: {e}")
            return self._parse_simple_rubric(rubric_text)

    def _parse_simple_rubric(self, rubric_text: str) -> RubricUnderstanding:
        """
        简单解析评分标准文本（备用方案）

        使用正则表达式提取题目和评分点
        """
        try:
            import re

            criteria = []
            total_points = 0.0

            # 按题目分割
            # 匹配格式: "题目1（10分）" 或 "Q1 (10分)" 或 "1. (10分)"
            question_pattern = r'(?:题目|Question|Q)?(\d+)[：:.\s]*[（\(]?(\d+(?:\.\d+)?)\s*分[）\)]?'
            question_matches = list(re.finditer(question_pattern, rubric_text, re.IGNORECASE))

            if question_matches:
                for i, match in enumerate(question_matches):
                    question_num = match.group(1)
                    question_points = float(match.group(2))
                    question_id = f"Q{question_num}"

                    # 提取该题目的内容（从当前匹配到下一个匹配之间的文本）
                    start = match.end()
                    end = question_matches[i + 1].start() if i + 1 < len(question_matches) else len(rubric_text)
                    question_content = rubric_text[start:end].strip()

                    # 提取评分点
                    # 匹配格式: "- 描述（5分）" 或 "1. 描述 (5分)"
                    criterion_pattern = r'[-•\d+\.]\s*(.+?)[（\(](\d+(?:\.\d+)?)\s*分[）\)]'
                    criterion_matches = re.findall(criterion_pattern, question_content)

                    if criterion_matches:
                        for j, (desc, points) in enumerate(criterion_matches, 1):
                            criterion = GradingCriterion(
                                criterion_id=f"{question_id}_C{j}",
                                question_id=question_id,
                                description=desc.strip(),
                                points=float(points),
                                evaluation_method='semantic'
                            )
                            criteria.append(criterion)
                            total_points += float(points)
                    else:
                        # 如果没有找到具体评分点，创建一个默认评分点
                        criterion = GradingCriterion(
                            criterion_id=f"{question_id}_C1",
                            question_id=question_id,
                            description=f"题目{question_num}整体评分",
                            points=question_points,
                            evaluation_method='semantic'
                        )
                        criteria.append(criterion)
                        total_points += question_points

            if not criteria:
                logger.warning("未能解析出任何评分点，使用默认标准")
                return self._default_rubric()

            return RubricUnderstanding(
                rubric_id='R_SIMPLE',
                criteria=criteria,
                total_points=total_points,
                grading_rules={'partial_credit': 'yes'},
                strictness_guidance=None
            )

        except Exception as e:
            logger.error(f"简单解析失败: {e}")
            return self._default_rubric()

    async def _interpret_rubric(self, rubric_text: str) -> RubricUnderstanding:
        """
        解析评分标准文本（使用 LLM）

        Args:
            rubric_text: 评分标准文本

        Returns:
            RubricUnderstanding 对象
        """
        try:
            # 如果文本很长，使用分批处理
            if len(rubric_text) > 5000:
                return await self._interpret_rubric_in_batches(rubric_text)

            # 构建 Prompt
            prompt = format_rubric_interpretation_prompt(rubric_text)

            messages = [
                {"role": "system", "content": "你是一位资深教育专家，擅长解析评分标准。"},
                {"role": "user", "content": prompt}
            ]

            # 调用 LLM
            response = self.llm_client.chat(
                messages,
                temperature=0.2,
                max_tokens=8000,
                timeout=self._get_llm_timeout()
            )

            # 解析响应
            return self._parse_rubric(response, rubric_text)

        except Exception as e:
            logger.error(f"LLM 解析评分标准失败: {e}")
            return self._parse_simple_rubric(rubric_text)

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
