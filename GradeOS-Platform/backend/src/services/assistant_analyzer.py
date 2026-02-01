"""辅助批改分析引擎

提供作业深度理解和分析功能。
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional

from src.services.llm_client import UnifiedLLMClient, LLMMessage
from src.models.assistant_models import UnderstandingResult, KnowledgePoint, DifficultyLevel


logger = logging.getLogger(__name__)


# ==================== Prompt 模板 ====================


UNDERSTANDING_PROMPT = """你是一位资深教师，需要深度理解学生的作业内容。

**任务**：分析以下作业图片，理解学生的答题情况。

**要求**：
1. 识别涉及的知识点（不少于 3 个）
2. 判断题目类型（选择题/填空题/计算题/证明题/开放题）
3. 分析学生的解题思路和逻辑链条
4. 评估作业难度（easy/medium/hard）
5. 估算完成时间（分钟）

**输出格式**（必须是有效的 JSON）：
```json
{
  "knowledge_points": [
    {
      "name": "知识点名称",
      "category": "知识点分类",
      "confidence": 0.95
    }
  ],
  "question_types": ["calculation", "proof"],
  "solution_approaches": [
    "第一步：...",
    "第二步：...",
    "第三步：..."
  ],
  "logic_chain": [
    "推理步骤1",
    "推理步骤2",
    "推理步骤3"
  ],
  "difficulty_level": "medium",
  "estimated_time_minutes": 30
}
```

**注意**：
- 仅输出 JSON，不要有其他文字
- 知识点confidence 范围 0.0-1.0
- difficulty_level 只能是 easy/medium/hard 之一
"""


# ==================== 分析引擎 ====================


class AssistantAnalyzer:
    """辅助批改分析引擎"""

    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        """
        Args:
            llm_client: LLM 客户端（如果不提供，会创建默认客户端）
        """
        self.llm_client = llm_client or UnifiedLLMClient()

    async def analyze_understanding(
        self,
        images: List[str],
        subject: Optional[str] = None,
        context_info: Optional[Dict[str, Any]] = None,
    ) -> UnderstandingResult:
        """
        深度理解作业内容

        Args:
            images: 作业图片 Base64 列表
            subject: 科目（可选）
            context_info: 上下文信息（可选）

        Returns:
            理解分析结果
        """
        try:
            logger.info(
                f"[AssistantAnalyzer] 开始分析理解: images={len(images)}, subject={subject}"
            )

            # 构建消息
            messages = self._build_understanding_messages(images, subject, context_info)

            # 调用 LLM
            response = await self.llm_client.complete(
                messages=messages,
                temperature=0.3,  # 较低温度，确保输出稳定
                max_tokens=2000,
            )

            # 解析响应
            understanding = self._parse_understanding_response(response.content)

            logger.info(
                f"[AssistantAnalyzer] 理解分析完成: knowledge_points={len(understanding.knowledge_points)}"
            )

            return understanding

        except Exception as e:
            logger.error(f"[AssistantAnalyzer] 理解分析失败: {e}", exc_info=True)
            # 返回默认结果
            return UnderstandingResult(
                knowledge_points=[],
                question_types=[],
                solution_approaches=[],
                difficulty_level=DifficultyLevel.MEDIUM,
                estimated_time_minutes=None,
                logic_chain=[],
            )

    def _build_understanding_messages(
        self,
        images: List[str],
        subject: Optional[str],
        context_info: Optional[Dict[str, Any]],
    ) -> List[LLMMessage]:
        """构建理解分析消息"""

        # 构建提示词
        prompt = UNDERSTANDING_PROMPT

        if subject:
            prompt += f"\n\n**科目**: {subject}"

        if context_info:
            prompt += f"\n\n**上下文信息**: {json.dumps(context_info, ensure_ascii=False)}"

        # 构建多模态消息
        content_parts = [{"type": "text", "text": prompt}]

        # 添加图片
        for img_base64 in images:
            # 确保 base64 格式正确
            if not img_base64.startswith("data:"):
                img_base64 = f"data:image/jpeg;base64,{img_base64}"

            content_parts.append({"type": "image_url", "image_url": {"url": img_base64}})

        return [LLMMessage(role="user", content=content_parts)]

    def _parse_understanding_response(self, response_text: str) -> UnderstandingResult:
        """解析 LLM 响应"""
        try:
            # 提取 JSON（可能被 markdown 代码块包裹）
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

            # 解析 JSON
            data = json.loads(json_text)

            # 构建结果
            raw_kps = data.get("knowledge_points", [])
            if isinstance(raw_kps, dict):
                raw_kps = list(raw_kps.values())
            if not isinstance(raw_kps, list):
                raw_kps = []
            knowledge_points = [
                KnowledgePoint(
                    name=kp.get("name", ""),
                    category=kp.get("category", ""),
                    confidence=min(max(kp.get("confidence", 0.0), 0.0), 1.0),
                )
                for kp in raw_kps
                if isinstance(kp, dict)
            ]

            question_types = data.get("question_types", [])
            if not isinstance(question_types, list):
                question_types = []
            question_types = [
                str(q).strip().lower() for q in question_types if q is not None and str(q).strip()
            ]

            difficulty_map = {
                "easy": DifficultyLevel.EASY,
                "medium": DifficultyLevel.MEDIUM,
                "hard": DifficultyLevel.HARD,
            }
            difficulty_level = difficulty_map.get(
                data.get("difficulty_level", "medium"), DifficultyLevel.MEDIUM
            )

            estimated_time = data.get("estimated_time_minutes")
            if isinstance(estimated_time, str):
                digits = re.findall(r"\d+", estimated_time)
                estimated_time = int(digits[0]) if digits else None
            elif isinstance(estimated_time, (int, float)):
                estimated_time = int(estimated_time)
            else:
                estimated_time = None

            return UnderstandingResult(
                knowledge_points=knowledge_points,
                question_types=question_types,
                solution_approaches=data.get("solution_approaches", []),
                difficulty_level=difficulty_level,
                estimated_time_minutes=estimated_time,
                logic_chain=data.get("logic_chain", []),
            )

        except Exception as e:
            logger.error(f"[AssistantAnalyzer] 解析响应失败: {e}")
            logger.debug(f"Response text: {response_text[:500]}")

            # 返回默认结果
            return UnderstandingResult(
                knowledge_points=[],
                question_types=[],
                solution_approaches=[],
                difficulty_level=DifficultyLevel.MEDIUM,
                estimated_time_minutes=None,
                logic_chain=[],
            )

    async def close(self):
        """关闭资源"""
        if self.llm_client:
            await self.llm_client.close()


# ==================== 便捷函数 ====================


async def analyze_understanding(
    images: List[str],
    subject: Optional[str] = None,
    context_info: Optional[Dict[str, Any]] = None,
) -> UnderstandingResult:
    """
    便捷函数：分析作业理解

    Args:
        images: 作业图片 Base64 列表
        subject: 科目（可选）
        context_info: 上下文信息（可选）

    Returns:
        理解分析结果
    """
    analyzer = AssistantAnalyzer()
    try:
        return await analyzer.analyze_understanding(images, subject, context_info)
    finally:
        await analyzer.close()
