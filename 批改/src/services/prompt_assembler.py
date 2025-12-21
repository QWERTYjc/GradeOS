"""
动态提示词拼装服务

根据题型、错误模式、判例等上下文动态构建提示词。
验证：需求 5.1, 5.2, 5.3, 5.4, 5.5
"""

import logging
import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from src.models.prompt import PromptSection, AssembledPrompt
from src.models.exemplar import Exemplar


logger = logging.getLogger(__name__)


class PromptAssembler:
    """
    提示词拼装器
    
    根据题型和上下文动态选择和拼装提示词模板。
    支持判例格式化、错误引导、详细推理提示等功能。
    
    验证：需求 5.1, 5.2, 5.3, 5.4, 5.5
    """
    
    # Token 估算：平均每个字符约 0.25 个 token（中文）
    CHARS_PER_TOKEN = 4
    
    # 优先级顺序（从高到低）
    PRIORITY_ORDER = [
        PromptSection.SYSTEM,
        PromptSection.RUBRIC,
        PromptSection.EXEMPLARS,
        PromptSection.ERROR_GUIDANCE,
        PromptSection.DETAILED_REASONING,
        PromptSection.CALIBRATION
    ]
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        初始化提示词拼装器
        
        Args:
            templates_dir: 模板文件目录路径，默认为 src/services/prompt_templates
        """
        if templates_dir is None:
            # 默认模板目录
            current_dir = Path(__file__).parent
            templates_dir = current_dir / "prompt_templates"
        
        self.templates_dir = Path(templates_dir)
        self._template_cache: Dict[str, str] = {}
        
        logger.info(f"PromptAssembler 初始化完成，模板目录: {self.templates_dir}")
    
    def load_base_template(self, question_type: str) -> str:
        """
        加载题型基础模板
        
        验证：需求 5.1
        属性 11：提示词模板选择正确性
        
        Args:
            question_type: 题目类型（objective, stepwise, essay 等）
        
        Returns:
            str: 基础模板内容
        
        Raises:
            FileNotFoundError: 如果模板文件不存在
        """
        # 检查缓存
        if question_type in self._template_cache:
            logger.debug(f"从缓存加载模板: {question_type}")
            return self._template_cache[question_type]
        
        # 构建模板文件路径
        template_path = self.templates_dir / f"{question_type}.txt"
        
        if not template_path.exists():
            error_msg = f"模板文件不存在: {template_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 读取模板
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # 缓存模板
            self._template_cache[question_type] = template_content
            
            logger.info(f"成功加载模板: {question_type}")
            return template_content
            
        except Exception as e:
            logger.error(f"读取模板文件失败: {e}")
            raise
    
    def add_error_guidance(self, error_patterns: List[str]) -> str:
        """
        添加错误模式引导
        
        验证：需求 5.2
        
        Args:
            error_patterns: 错误模式列表
        
        Returns:
            str: 错误引导提示词
        """
        if not error_patterns:
            return ""
        
        guidance_parts = ["## 常见错误提示\n"]
        guidance_parts.append("在批改时，请特别注意以下常见错误模式：\n")
        
        for i, pattern in enumerate(error_patterns, 1):
            guidance_parts.append(f"{i}. {pattern}")
        
        return "\n".join(guidance_parts)
    
    def add_detailed_reasoning_prompt(self, previous_confidence: float) -> str:
        """
        添加详细推理提示（低置信度时）
        
        验证：需求 5.3
        
        Args:
            previous_confidence: 上一次批改的置信度
        
        Returns:
            str: 详细推理提示词
        """
        if previous_confidence >= 0.85:
            return ""
        
        return """## 详细推理要求

由于之前的批改置信度较低，请在本次批改中：

1. **详细记录推理过程**：在 reasoning_trace 中记录每一步的思考过程
2. **明确不确定因素**：说明哪些地方存在歧义或不确定性
3. **提供多种解释**：如果答案有多种理解方式，请列出所有可能性
4. **标注证据位置**：明确指出支持你判断的证据在图像中的位置

请确保你的推理过程清晰、完整、可追溯。
"""
    
    def format_exemplars(self, exemplars: List[Exemplar]) -> str:
        """
        格式化判例为 few-shot 示例
        
        验证：需求 5.4
        
        Args:
            exemplars: 判例列表
        
        Returns:
            str: 格式化后的判例文本
        """
        if not exemplars:
            return ""
        
        formatted_parts = ["## 参考判例\n"]
        formatted_parts.append("以下是老师确认过的正确批改示例，供你参考：\n")
        
        for i, exemplar in enumerate(exemplars, 1):
            formatted_parts.append(f"### 示例 {i}")
            formatted_parts.append(f"**题目类型**: {exemplar.question_type}")
            formatted_parts.append(f"**学生答案**: {exemplar.student_answer_text}")
            formatted_parts.append(f"**得分**: {exemplar.score}/{exemplar.max_score}")
            formatted_parts.append(f"**教师评语**: {exemplar.teacher_feedback}")
            formatted_parts.append("")  # 空行分隔
        
        return "\n".join(formatted_parts)
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        
        Args:
            text: 文本内容
        
        Returns:
            int: 估算的 token 数量
        """
        return len(text) // self.CHARS_PER_TOKEN
    
    def _truncate_by_priority(
        self,
        sections: Dict[PromptSection, str],
        max_tokens: int
    ) -> tuple[Dict[PromptSection, str], List[PromptSection]]:
        """
        按优先级截断提示词
        
        验证：需求 5.5
        属性 12：提示词截断优先级
        
        Args:
            sections: 各区段内容
            max_tokens: 最大 token 数
        
        Returns:
            tuple: (截断后的区段, 被截断的区段列表)
        """
        truncated_sections = []
        result_sections = {}
        current_tokens = 0
        has_truncated = False  # 标记是否已经发生截断
        
        # 按优先级顺序处理
        for section in self.PRIORITY_ORDER:
            if section not in sections or not sections[section]:
                continue
            
            section_text = sections[section]
            section_tokens = self._estimate_tokens(section_text)
            
            # 如果已经发生过截断，跳过所有后续低优先级区段
            if has_truncated:
                truncated_sections.append(section)
                continue
            
            # 检查是否超过限制
            if current_tokens + section_tokens <= max_tokens:
                # 完整保留
                result_sections[section] = section_text
                current_tokens += section_tokens
            else:
                # 需要截断或丢弃
                remaining_tokens = max_tokens - current_tokens
                
                # 对于高优先级区段（SYSTEM, RUBRIC），即使空间很小也要尽量保留
                min_tokens_threshold = 50 if section in [PromptSection.SYSTEM, PromptSection.RUBRIC] else 100
                
                if remaining_tokens > min_tokens_threshold:
                    # 截断保留（预留截断标记的空间）
                    truncation_marker = "\n\n[内容已截断...]"
                    marker_tokens = self._estimate_tokens(truncation_marker)
                    available_tokens = remaining_tokens - marker_tokens
                    
                    if available_tokens > 20:  # 确保有足够空间
                        truncated_text = section_text[:available_tokens * self.CHARS_PER_TOKEN]
                        result_sections[section] = truncated_text + truncation_marker
                        current_tokens += self._estimate_tokens(result_sections[section])
                
                # 记录被截断的区段
                truncated_sections.append(section)
                has_truncated = True  # 标记已发生截断
                
                # 已达到限制，停止处理后续区段
                # 将所有剩余的低优先级区段标记为截断
                for remaining_section in self.PRIORITY_ORDER:
                    if (remaining_section in sections and 
                        remaining_section not in result_sections and 
                        remaining_section not in truncated_sections):
                        truncated_sections.append(remaining_section)
                
                break
        
        return result_sections, truncated_sections
    
    def assemble(
        self,
        question_type: str,
        rubric: str,
        exemplars: Optional[List[Exemplar]] = None,
        error_patterns: Optional[List[str]] = None,
        previous_confidence: Optional[float] = None,
        calibration: Optional[Dict[str, Any]] = None,
        max_tokens: int = 8000
    ) -> AssembledPrompt:
        """
        拼装完整提示词
        
        验证：需求 5.1, 5.2, 5.3, 5.4, 5.5
        
        Args:
            question_type: 题目类型
            rubric: 评分细则
            exemplars: 判例列表（可选）
            error_patterns: 错误模式列表（可选）
            previous_confidence: 上一次置信度（可选）
            calibration: 校准配置（可选）
            max_tokens: 最大 token 数，默认 8000
        
        Returns:
            AssembledPrompt: 拼装后的提示词
        """
        try:
            # 构建各区段
            sections: Dict[PromptSection, str] = {}
            
            # 1. 系统提示（基础模板）
            sections[PromptSection.SYSTEM] = self.load_base_template(question_type)
            
            # 2. 评分细则
            sections[PromptSection.RUBRIC] = f"## 评分细则\n\n{rubric}"
            
            # 3. 判例（如果有）
            if exemplars:
                sections[PromptSection.EXEMPLARS] = self.format_exemplars(exemplars)
            
            # 4. 错误引导（如果有）
            if error_patterns:
                sections[PromptSection.ERROR_GUIDANCE] = self.add_error_guidance(error_patterns)
            
            # 5. 详细推理提示（如果需要）
            if previous_confidence is not None:
                detailed_prompt = self.add_detailed_reasoning_prompt(previous_confidence)
                if detailed_prompt:
                    sections[PromptSection.DETAILED_REASONING] = detailed_prompt
            
            # 6. 校准配置（如果有）
            if calibration:
                calibration_text = self._format_calibration(calibration)
                if calibration_text:
                    sections[PromptSection.CALIBRATION] = calibration_text
            
            # 计算总 token 数
            total_tokens = sum(self._estimate_tokens(text) for text in sections.values())
            
            # 如果超过限制，按优先级截断
            truncated_sections_list = []
            if total_tokens > max_tokens:
                logger.warning(f"提示词超过限制 ({total_tokens} > {max_tokens})，开始截断")
                sections, truncated_sections_list = self._truncate_by_priority(sections, max_tokens)
                total_tokens = sum(self._estimate_tokens(text) for text in sections.values())
            
            logger.info(f"提示词拼装完成，总 tokens: {total_tokens}")
            
            return AssembledPrompt(
                sections=sections,
                total_tokens=total_tokens,
                truncated_sections=truncated_sections_list
            )
            
        except Exception as e:
            logger.error(f"拼装提示词失败: {e}")
            raise
    
    def _format_calibration(self, calibration: Dict[str, Any]) -> str:
        """
        格式化校准配置
        
        Args:
            calibration: 校准配置字典
        
        Returns:
            str: 格式化后的校准配置文本
        """
        if not calibration:
            return ""
        
        parts = ["## 个性化校准配置\n"]
        
        # 扣分规则
        if "deduction_rules" in calibration:
            parts.append("### 扣分规则")
            for error_type, deduction in calibration["deduction_rules"].items():
                parts.append(f"- {error_type}: 扣 {deduction} 分")
            parts.append("")
        
        # 容差设置
        if "tolerance_rules" in calibration:
            parts.append("### 容差设置")
            for rule in calibration["tolerance_rules"]:
                parts.append(f"- {rule.get('description', rule.get('rule_type'))}")
            parts.append("")
        
        # 严格程度
        if "strictness_level" in calibration:
            level = calibration["strictness_level"]
            if level < 0.3:
                strictness_desc = "宽松"
            elif level < 0.7:
                strictness_desc = "适中"
            else:
                strictness_desc = "严格"
            parts.append(f"### 评分严格程度: {strictness_desc}\n")
        
        return "\n".join(parts)
