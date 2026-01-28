"""辅助批改建议生成器

为识别的错误生成改进建议。
"""

import logging
import json
import uuid
from typing import List, Dict, Any, Optional

from src.services.llm_client import UnifiedLLMClient, LLMMessage
from src.models.assistant_models import Suggestion, SuggestionType, Severity, ErrorRecord


logger = logging.getLogger(__name__)


# ==================== Prompt 模板 ====================


SUGGESTION_PROMPT = """你是一位耐心的教师，需要为学生的错误提供建设性的改进建议。

**任务**：针对识别出的错误，生成具体的、可操作的建议。

**建议类型**：
1. **correction** (纠正建议)：针对错误的直接纠正
2. **improvement** (改进建议)：提升解题方法和思路
3. **alternative** (替代方案)：提供其他解法

**输出格式**（必须是有效的 JSON）：
```json
{
  "suggestions": [
    {
      "related_error_id": "err_xxx",
      "suggestion_type": "correction",
      "description": "具体的建议内容（简洁、可操作）",
      "example": "示例或步骤（可选）",
      "priority": "high",
      "resources": ["推荐学习资源1", "推荐学习资源2"],
      "expected_improvement": "预期改进效果"
    }
  ]
}
```

**要求**：
- 仅输出 JSON，不要有其他文字
- 每个建议必须具体、可操作
- 优先级根据错误严重程度设置
- 提供学习资源（教材章节、视频链接等）
"""


# ==================== 建议生成器 ====================


class SuggestionGenerator:
    """建议生成器"""
    
    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        """
        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client or UnifiedLLMClient()
    
    async def generate_suggestions(
        self,
        errors: List[ErrorRecord],
        understanding: Dict[str, Any],
    ) -> List[Suggestion]:
        """
        生成建议
        
        Args:
            errors: 错误记录列表
            understanding: 理解分析结果
            
        Returns:
            建议列表
        """
        try:
            if not errors:
                logger.info("[SuggestionGenerator] 没有错误，无需生成建议")
                return []
            
            logger.info(f"[SuggestionGenerator] 开始生成建议: errors={len(errors)}")
            
            # 构建消息
            messages = self._build_suggestion_messages(errors, understanding)
            
            # 调用 LLM
            response = await self.llm_client.complete(
                messages=messages,
                temperature=0.4,  # 中等温度，保持创造性
                max_tokens=3000,
            )
            
            # 解析响应
            suggestions = self._parse_suggestion_response(response.content, errors)
            
            logger.info(f"[SuggestionGenerator] 建议生成完成: 生成 {len(suggestions)} 条建议")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"[SuggestionGenerator] 建议生成失败: {e}", exc_info=True)
            return []
    
    def _build_suggestion_messages(
        self,
        errors: List[ErrorRecord],
        understanding: Dict[str, Any],
    ) -> List[LLMMessage]:
        """构建建议消息"""
        
        prompt = SUGGESTION_PROMPT
        
        # 添加错误列表
        errors_json = [
            {
                "error_id": err.error_id,
                "error_type": err.error_type.value,
                "description": err.description,
                "severity": err.severity.value,
                "correct_approach": err.correct_approach,
            }
            for err in errors
        ]
        
        prompt += f"\n\n**识别的错误**：\n```json\n{json.dumps(errors_json, ensure_ascii=False, indent=2)}\n```"
        
        # 添加理解上下文
        if understanding:
            prompt += f"\n\n**作业理解上下文**：\n{json.dumps(understanding, ensure_ascii=False, indent=2)[:300]}"
        
        return [LLMMessage(role="user", content=prompt)]
    
    def _parse_suggestion_response(
        self,
        response_text: str,
        errors: List[ErrorRecord],
    ) -> List[Suggestion]:
        """解析建议响应"""
        try:
            # 提取 JSON
            json_text = response_text.strip()
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0].strip()
            else:
                start = json_text.find("{")
                end = json_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    json_text = json_text[start : end + 1]
            
            data = json.loads(json_text)
            suggestions_data = data.get("suggestions", [])
            if not isinstance(suggestions_data, list):
                suggestions_data = []
            error_ids = {err.error_id for err in errors}
            fallback_error_id = errors[0].error_id if errors else None
            
            # 构建建议列表
            suggestions = []
            for sugg in suggestions_data:
                try:
                    if not isinstance(sugg, dict):
                        continue
                    # 映射建议类型
                    type_map = {
                        "correction": SuggestionType.CORRECTION,
                        "improvement": SuggestionType.IMPROVEMENT,
                        "alternative": SuggestionType.ALTERNATIVE,
                    }
                    suggestion_type = type_map.get(
                        sugg.get("suggestion_type", "correction"),
                        SuggestionType.CORRECTION
                    )
                    
                    # 映射优先级
                    priority_map = {
                        "high": Severity.HIGH,
                        "medium": Severity.MEDIUM,
                        "low": Severity.LOW,
                    }
                    priority = priority_map.get(
                        sugg.get("priority", "medium"),
                        Severity.MEDIUM
                    )
                    
                    related_error_id = sugg.get("related_error_id")
                    if related_error_id not in error_ids:
                        related_error_id = fallback_error_id

                    resources = sugg.get("resources", [])
                    if not isinstance(resources, list):
                        resources = []
                    resources = [str(r).strip() for r in resources if r is not None and str(r).strip()]

                    # 构建建议
                    suggestion = Suggestion(
                        suggestion_id=f"sug_{uuid.uuid4().hex[:8]}",
                        related_error_id=related_error_id,
                        suggestion_type=suggestion_type,
                        description=sugg.get("description", ""),
                        example=sugg.get("example"),
                        priority=priority,
                        resources=resources,
                        expected_improvement=sugg.get("expected_improvement"),
                    )
                    
                    suggestions.append(suggestion)
                    
                except Exception as e:
                    logger.warning(f"[SuggestionGenerator] 解析单个建议失败: {e}")
                    continue
            
            return suggestions
            
        except Exception as e:
            logger.error(f"[SuggestionGenerator] 解析建议响应失败: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return []
    
    async def close(self):
        """关闭资源"""
        if self.llm_client:
            await self.llm_client.close()


# ==================== 便捷函数 ====================


async def generate_suggestions(
    errors: List[ErrorRecord],
    understanding: Dict[str, Any],
) -> List[Suggestion]:
    """
    便捷函数：生成建议
    
    Args:
        errors: 错误记录列表
        understanding: 理解分析结果
        
    Returns:
        建议列表
    """
    generator = SuggestionGenerator()
    try:
        return await generator.generate_suggestions(errors, understanding)
    finally:
        await generator.close()
