"""辅助批改错误检测器

识别作业中的各类错误（计算、逻辑、概念、书写）。
"""

import logging
import json
import uuid
from typing import List, Dict, Any, Optional

from src.services.llm_client import UnifiedLLMClient, LLMMessage
from src.models.assistant_models import ErrorRecord, ErrorLocation, ErrorType, Severity


logger = logging.getLogger(__name__)


# ==================== Prompt 模板 ====================


ERROR_DETECTION_PROMPT = """你是一位严谨的教师，需要仔细检查学生作业中的错误。

**任务**：识别作业中的各类错误。

**错误类型**：
1. **计算错误** (calculation)：数值计算错误、公式应用错误
2. **逻辑错误** (logic)：推理不严密、前后矛盾、逻辑跳跃
3. **概念错误** (concept)：概念理解偏差、定理使用错误
4. **书写错误** (writing)：符号错误、表述不清、格式问题

**严重程度**：
- **high**: 导致结论完全错误
- **medium**: 影响部分结果
- **low**: 不影响结果但需改进

**输出格式**（必须是有效的 JSON）：
```json
{
  "errors": [
    {
      "error_type": "calculation",
      "description": "具体错误描述（简洁、明确）",
      "severity": "high",
      "location": {
        "page": 0,
        "region": "middle",
        "step_number": 3
      },
      "affected_steps": ["步骤3", "步骤4"],
      "correct_approach": "正确的做法是...",
      "context": "错误上下文"
    }
  ]
}
```

**要求**：
- 仅输出 JSON，不要有其他文字
- 每个错误必须有明确的位置和描述
- 必须提供正确做法 (correct_approach)
- 如果没有错误，返回空数组
"""


# ==================== 错误检测器 ====================


class ErrorDetector:
    """错误检测器"""

    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        """
        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client or UnifiedLLMClient()

    async def detect_errors(
        self,
        images: List[str],
        understanding: Dict[str, Any],
    ) -> List[ErrorRecord]:
        """
        检测错误

        Args:
            images: 作业图片 Base64 列表
            understanding: 理解分析结果

        Returns:
            错误记录列表
        """
        try:
            logger.info(f"[ErrorDetector] 开始检测错误: images={len(images)}")

            # 构建消息
            messages = self._build_detection_messages(images, understanding)

            # 调用 LLM
            response = await self.llm_client.complete(
                messages=messages,
                temperature=0.2,  # 低温度，确保准确性
                max_tokens=3000,
            )

            # 解析响应
            errors = self._parse_error_response(response.content)

            logger.info(f"[ErrorDetector] 错误检测完成: 发现 {len(errors)} 个错误")

            return errors

        except Exception as e:
            logger.error(f"[ErrorDetector] 错误检测失败: {e}", exc_info=True)
            return []

    def _build_detection_messages(
        self,
        images: List[str],
        understanding: Dict[str, Any],
    ) -> List[LLMMessage]:
        """构建检测消息"""

        prompt = ERROR_DETECTION_PROMPT

        # 添加理解上下文
        if understanding:
            prompt += f"\n\n**作业理解上下文**：\n{json.dumps(understanding, ensure_ascii=False, indent=2)[:500]}"

        # 构建多模态消息
        content_parts = [{"type": "text", "text": prompt}]

        # 添加图片
        for img_base64 in images:
            if not img_base64.startswith("data:"):
                img_base64 = f"data:image/jpeg;base64,{img_base64}"

            content_parts.append({"type": "image_url", "image_url": {"url": img_base64}})

        return [LLMMessage(role="user", content=content_parts)]

    def _parse_error_response(self, response_text: str) -> List[ErrorRecord]:
        """解析错误响应"""
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
            errors_data = data.get("errors", [])
            if not isinstance(errors_data, list):
                errors_data = []

            # 构建错误记录
            error_records = []
            for idx, err in enumerate(errors_data):
                try:
                    if not isinstance(err, dict):
                        continue
                    # 映射错误类型
                    error_type_map = {
                        "calculation": ErrorType.CALCULATION,
                        "logic": ErrorType.LOGIC,
                        "concept": ErrorType.CONCEPT,
                        "writing": ErrorType.WRITING,
                    }
                    error_type = error_type_map.get(err.get("error_type", "logic"), ErrorType.LOGIC)

                    # 映射严重程度
                    severity_map = {
                        "high": Severity.HIGH,
                        "medium": Severity.MEDIUM,
                        "low": Severity.LOW,
                    }
                    severity = severity_map.get(err.get("severity", "medium"), Severity.MEDIUM)

                    # 构建位置
                    location_data = err.get("location", {})
                    if not isinstance(location_data, dict):
                        location_data = {}
                    page_value = location_data.get("page", 0)
                    try:
                        page_value = int(page_value)
                    except (TypeError, ValueError):
                        page_value = 0
                    if page_value < 0:
                        page_value = 0
                    step_value = location_data.get("step_number")
                    if step_value is not None:
                        try:
                            step_value = int(step_value)
                        except (TypeError, ValueError):
                            step_value = None
                    location = ErrorLocation(
                        page=page_value,
                        region=location_data.get("region"),
                        step_number=step_value,
                        coordinates=location_data.get("coordinates"),
                    )

                    # 构建错误记录
                    error_record = ErrorRecord(
                        error_id=f"err_{uuid.uuid4().hex[:8]}",
                        error_type=error_type,
                        description=err.get("description", ""),
                        severity=severity,
                        location=location,
                        affected_steps=err.get("affected_steps", []),
                        correct_approach=err.get("correct_approach"),
                        context=err.get("context"),
                    )

                    error_records.append(error_record)

                except Exception as e:
                    logger.warning(f"[ErrorDetector] 解析单个错误失败: {e}")
                    continue

            return error_records

        except Exception as e:
            logger.error(f"[ErrorDetector] 解析错误响应失败: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return []

    async def close(self):
        """关闭资源"""
        if self.llm_client:
            await self.llm_client.close()


# ==================== 便捷函数 ====================


async def detect_errors(
    images: List[str],
    understanding: Dict[str, Any],
) -> List[ErrorRecord]:
    """
    便捷函数：检测错误

    Args:
        images: 作业图片 Base64 列表
        understanding: 理解分析结果

    Returns:
        错误记录列表
    """
    detector = ErrorDetector()
    try:
        return await detector.detect_errors(images, understanding)
    finally:
        await detector.close()
