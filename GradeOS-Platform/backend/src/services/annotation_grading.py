"""批注批改服务

让 AI 批改时输出带坐标的批注信息，包括：
1. 分数标注位置
2. 错误圈选区域
3. 错误讲解位置
4. 正确/部分正确标记

使用 Gemini 的视觉能力识别答题区域并输出归一化坐标
"""

import base64
import json
import logging
import re
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage

from src.services.chat_model_factory import get_chat_model
from src.config.models import get_default_model
from src.models.annotation import (
    AnnotationType,
    AnnotationColor,
    BoundingBox,
    VisualAnnotation,
    PageAnnotations,
    GradingAnnotationResult,
)
from src.models.grading_models import (
    QuestionRubric,
    QuestionResult,
    ScoringPointResult,
    ScoringPoint,
)


logger = logging.getLogger(__name__)


# 批注批改提示词模板
ANNOTATION_GRADING_PROMPT = """你是一位专业的阅卷老师，请对学生答卷进行**逐步骤**批改，并输出带坐标的详细批注信息。

## 评分标准
{rubric_context}

## 批改要求
1. **识别每个步骤**：找出学生作答的每一个步骤/行的位置
2. **区分 A mark 和 M mark**：
   - **A mark（Answer mark）**：答案分，只看最终答案是否正确
   - **M mark（Method mark）**：方法分，看解题步骤/方法是否正确
3. **逐步骤标注**：每个步骤都要标注坐标和得分情况
4. **错误标注**：错误的地方必须圈出并说明原因
5. **输出坐标**：所有批注都要输出归一化坐标 (0.0-1.0)

## 坐标系统说明
- 坐标原点在图片**左上角**
- x 轴向右增加 (0.0 = 最左, 1.0 = 最右)
- y 轴向下增加 (0.0 = 最上, 1.0 = 最下)
- 使用 bounding_box 表示区域: {{x_min, y_min, x_max, y_max}}

## 批注类型
- `a_mark`: A mark 标注（答案分），显示 "A1" 或 "A0"
- `m_mark`: M mark 标注（方法分），显示 "M1" 或 "M0"
- `score`: 总分标注，放在题目答案旁边
- `step_check`: 步骤正确勾选 ✓
- `step_cross`: 步骤错误叉 ✗
- `error_circle`: 错误圈选，圈出错误的地方
- `error_underline`: 错误下划线
- `comment`: 文字批注/错误讲解
- `highlight`: 高亮区域

## 输出格式 (JSON)
```json
{{
    "page_index": 0,
    "questions": [
        {{
            "question_id": "1",
            "score": 8,
            "max_score": 10,
            "feedback": "整体思路正确，但计算有误",
            "student_answer": "学生的答案内容",
            "answer_region": {{
                "x_min": 0.1,
                "y_min": 0.2,
                "x_max": 0.9,
                "y_max": 0.4
            }},
            "steps": [
                {{
                    "step_id": "1.1",
                    "step_content": "学生写的第一步内容",
                    "step_region": {{
                        "x_min": 0.1,
                        "y_min": 0.2,
                        "x_max": 0.8,
                        "y_max": 0.25
                    }},
                    "is_correct": true,
                    "mark_type": "M",
                    "mark_value": 1,
                    "feedback": "方法正确"
                }},
                {{
                    "step_id": "1.2",
                    "step_content": "学生写的第二步内容",
                    "step_region": {{
                        "x_min": 0.1,
                        "y_min": 0.26,
                        "x_max": 0.8,
                        "y_max": 0.31
                    }},
                    "is_correct": false,
                    "mark_type": "M",
                    "mark_value": 0,
                    "feedback": "计算错误：3+5 应该等于 8，不是 9",
                    "error_detail": "3+5=9 写错了"
                }},
                {{
                    "step_id": "1.3",
                    "step_content": "最终答案",
                    "step_region": {{
                        "x_min": 0.1,
                        "y_min": 0.32,
                        "x_max": 0.5,
                        "y_max": 0.36
                    }},
                    "is_correct": false,
                    "mark_type": "A",
                    "mark_value": 0,
                    "feedback": "答案错误，因为前面计算有误"
                }}
            ],
            "scoring_details": [
                {{
                    "point_id": "1.1",
                    "description": "正确列出方程",
                    "mark_type": "M",
                    "max_score": 1,
                    "awarded_score": 1,
                    "is_correct": true,
                    "evidence": "学生正确写出 x + y = 10"
                }},
                {{
                    "point_id": "1.2",
                    "description": "正确求解",
                    "mark_type": "M",
                    "max_score": 1,
                    "awarded_score": 0,
                    "is_correct": false,
                    "evidence": "计算过程有误",
                    "error_region": {{
                        "x_min": 0.3,
                        "y_min": 0.26,
                        "x_max": 0.5,
                        "y_max": 0.31
                    }}
                }},
                {{
                    "point_id": "1.3",
                    "description": "最终答案正确",
                    "mark_type": "A",
                    "max_score": 1,
                    "awarded_score": 0,
                    "is_correct": false,
                    "evidence": "答案错误"
                }}
            ],
            "annotations": [
                {{
                    "type": "score",
                    "bounding_box": {{"x_min": 0.85, "y_min": 0.2, "x_max": 0.95, "y_max": 0.25}},
                    "text": "2/3",
                    "color": "#FF8800"
                }},
                {{
                    "type": "m_mark",
                    "bounding_box": {{"x_min": 0.82, "y_min": 0.21, "x_max": 0.88, "y_max": 0.24}},
                    "text": "M1",
                    "color": "#00AA00"
                }},
                {{
                    "type": "m_mark",
                    "bounding_box": {{"x_min": 0.82, "y_min": 0.27, "x_max": 0.88, "y_max": 0.30}},
                    "text": "M0",
                    "color": "#FF0000"
                }},
                {{
                    "type": "a_mark",
                    "bounding_box": {{"x_min": 0.82, "y_min": 0.33, "x_max": 0.88, "y_max": 0.36}},
                    "text": "A0",
                    "color": "#FF0000"
                }},
                {{
                    "type": "step_check",
                    "bounding_box": {{"x_min": 0.78, "y_min": 0.21, "x_max": 0.81, "y_max": 0.24}},
                    "text": "",
                    "color": "#00AA00"
                }},
                {{
                    "type": "step_cross",
                    "bounding_box": {{"x_min": 0.78, "y_min": 0.27, "x_max": 0.81, "y_max": 0.30}},
                    "text": "",
                    "color": "#FF0000"
                }},
                {{
                    "type": "error_circle",
                    "bounding_box": {{"x_min": 0.3, "y_min": 0.26, "x_max": 0.5, "y_max": 0.31}},
                    "text": "3+5≠9",
                    "color": "#FF0000"
                }},
                {{
                    "type": "comment",
                    "bounding_box": {{"x_min": 0.55, "y_min": 0.27, "x_max": 0.78, "y_max": 0.30}},
                    "text": "应为 3+5=8",
                    "color": "#0066FF"
                }}
            ]
        }}
    ],
    "total_score": 2,
    "max_score": 3,
    "overall_feedback": "方法基本正确，但计算有误导致答案错误"
}}
```

## 重要提示
1. **每个步骤都要标注**：识别学生写的每一行/每一步，给出坐标
2. **区分 A/M mark**：
   - M mark 标注在方法步骤旁边，显示 "M1"（得分）或 "M0"（不得分）
   - A mark 标注在最终答案旁边，显示 "A1"（得分）或 "A0"（不得分）
3. **错误必须圈出**：用 error_circle 圈出具体错误位置，并用 comment 说明原因
4. **坐标必须准确**：仔细观察图片，给出精确的坐标位置
5. **颜色规范**：
   - 绿色 #00AA00：正确（M1, A1, ✓）
   - 红色 #FF0000：错误（M0, A0, ✗, 错误圈选）
   - 橙色 #FF8800：部分正确/总分
   - 蓝色 #0066FF：讲解/批注

请仔细分析图片中的学生答案，输出完整的批改结果和批注坐标。"""


@dataclass
class AnnotationGradingConfig:
    """批注批改配置"""

    model_name: Optional[str] = None
    temperature: float = 0.1
    enable_thinking: bool = True
    max_retries: int = 3
    retry_delay: float = 2.0


class AnnotationGradingService:
    """
    批注批改服务

    让 AI 批改时输出带坐标的批注信息
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[AnnotationGradingConfig] = None,
    ):
        self.config = config or AnnotationGradingConfig()
        model_name = self.config.model_name or get_default_model()

        self.llm = get_chat_model(
            api_key=api_key,
            model_name=model_name,
            temperature=self.config.temperature,
            purpose="vision",
            enable_thinking=self.config.enable_thinking,
            streaming=True,
        )

    def _format_rubric_context(
        self,
        rubrics: List[QuestionRubric],
    ) -> str:
        """格式化评分标准上下文"""
        lines = []
        for rubric in rubrics:
            lines.append(f"### 第 {rubric.question_id} 题 (满分 {rubric.max_score} 分)")
            if rubric.question_text:
                lines.append(f"题目：{rubric.question_text}")
            if rubric.standard_answer:
                lines.append(f"标准答案：{rubric.standard_answer}")

            if rubric.scoring_points:
                lines.append("得分点：")
                for sp in rubric.scoring_points:
                    point_id = (
                        sp.point_id or f"{rubric.question_id}.{rubric.scoring_points.index(sp)+1}"
                    )
                    lines.append(f"  - [{point_id}] ({sp.score}分) {sp.description}")

            if rubric.grading_notes:
                lines.append(f"批改注意：{rubric.grading_notes}")
            lines.append("")

        return "\n".join(lines)

    def _extract_json_from_response(self, text: str) -> str:
        """从响应中提取 JSON"""
        # 尝试提取 ```json ... ``` 块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # 尝试提取 ``` ... ``` 块
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # 尝试找到 JSON 对象
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]

        return text

    def _parse_grading_response(
        self,
        response_text: str,
        page_index: int,
    ) -> PageAnnotations:
        """解析批改响应"""
        json_text = self._extract_json_from_response(response_text)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            # 尝试修复常见错误
            json_text = re.sub(r",\s*}", "}", json_text)
            json_text = re.sub(r",\s*]", "]", json_text)
            data = json.loads(json_text)

        # 构建 PageAnnotations
        page_annotations = PageAnnotations(
            page_index=page_index,
            total_score=float(data.get("total_score") or 0),
            max_score=float(data.get("max_score") or 0),
        )

        # 解析每道题的批注
        for q_data in data.get("questions") or []:
            question_id = str(q_data.get("question_id") or "")

            # 解析题目级别的批注
            for ann_data in q_data.get("annotations") or []:
                annotation = self._parse_annotation(ann_data, question_id)
                if annotation:
                    page_annotations.annotations.append(annotation)

            # 解析得分点级别的错误区域
            for sp_data in q_data.get("scoring_details") or []:
                if not sp_data.get("is_correct") and sp_data.get("error_region"):
                    error_ann = VisualAnnotation(
                        annotation_type=AnnotationType.ERROR_CIRCLE,
                        bounding_box=BoundingBox.from_dict(sp_data["error_region"]),
                        text=sp_data.get("evidence") or "",
                        color=AnnotationColor.RED.value,
                        question_id=question_id,
                        scoring_point_id=sp_data.get("point_id") or "",
                    )
                    page_annotations.annotations.append(error_ann)

        return page_annotations

    def _parse_annotation(
        self,
        data: Dict[str, Any],
        question_id: str = "",
    ) -> Optional[VisualAnnotation]:
        """解析单个批注"""
        try:
            ann_type_str = data.get("type") or data.get("annotation_type") or "comment"
            try:
                ann_type = AnnotationType(ann_type_str)
            except ValueError:
                ann_type = AnnotationType.COMMENT

            bbox_data = data.get("bounding_box") or data.get("boundingBox") or {}
            if not bbox_data:
                return None

            return VisualAnnotation(
                annotation_type=ann_type,
                bounding_box=BoundingBox.from_dict(bbox_data),
                text=data.get("text") or data.get("message") or "",
                color=data.get("color") or AnnotationColor.RED.value,
                question_id=question_id,
            )
        except Exception as e:
            logger.warning(f"解析批注失败: {e}")
            return None

    async def grade_page_with_annotations(
        self,
        image_data: bytes,
        rubrics: List[QuestionRubric],
        page_index: int = 0,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> PageAnnotations:
        """
        批改单页并输出带坐标的批注

        Args:
            image_data: 页面图像数据 (bytes)
            rubrics: 该页涉及的评分标准列表
            page_index: 页码
            stream_callback: 流式回调函数

        Returns:
            PageAnnotations: 包含所有批注的结果
        """
        # 编码图像
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        # 构建提示词
        rubric_context = self._format_rubric_context(rubrics)
        prompt = ANNOTATION_GRADING_PROMPT.format(rubric_context=rubric_context)

        # 构建消息
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:image/png;base64,{image_b64}"},
            ]
        )

        # 调用 LLM（流式）
        full_response = ""
        retry_count = 0

        while retry_count < self.config.max_retries:
            try:
                async for chunk in self.llm.astream([message]):
                    content = chunk.content
                    if content:
                        if isinstance(content, str):
                            full_response += content
                            if stream_callback:
                                await stream_callback(content)
                        elif isinstance(content, list):
                            for part in content:
                                if isinstance(part, str):
                                    full_response += part
                                    if stream_callback:
                                        await stream_callback(part)
                                elif isinstance(part, dict) and "text" in part:
                                    full_response += part["text"]
                                    if stream_callback:
                                        await stream_callback(part["text"])
                break
            except Exception as e:
                retry_count += 1
                logger.warning(f"批改请求失败 (尝试 {retry_count}/{self.config.max_retries}): {e}")
                if retry_count >= self.config.max_retries:
                    raise
                import asyncio

                await asyncio.sleep(self.config.retry_delay * retry_count)
                full_response = ""

        # 解析响应
        return self._parse_grading_response(full_response, page_index)

    async def grade_submission_with_annotations(
        self,
        pages: List[bytes],
        rubrics: List[QuestionRubric],
        submission_id: str = "",
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> GradingAnnotationResult:
        """
        批改整份提交并输出带坐标的批注

        Args:
            pages: 所有页面的图像数据列表
            rubrics: 评分标准列表
            submission_id: 提交 ID
            stream_callback: 流式回调函数

        Returns:
            GradingAnnotationResult: 完整的批改批注结果
        """
        result = GradingAnnotationResult(submission_id=submission_id)

        for page_index, page_data in enumerate(pages):
            logger.info(f"批改第 {page_index + 1}/{len(pages)} 页")

            page_annotations = await self.grade_page_with_annotations(
                image_data=page_data,
                rubrics=rubrics,
                page_index=page_index,
                stream_callback=stream_callback,
            )

            result.pages.append(page_annotations)
            result.total_score += page_annotations.total_score
            result.max_total_score += page_annotations.max_score

        return result


def update_annotations_after_review(
    original_annotations: List[Dict[str, Any]],
    original_score: float,
    new_score: float,
    max_score: float,
    question_id: str,
) -> List[Dict[str, Any]]:
    """
    复核后增量修正批注

    当教师复核修改分数后，只更新分数相关的批注，保留其他批注不变。
    这是一种低成本的增量修正方案。

    Args:
        original_annotations: 原始批注列表
        original_score: 原始分数
        new_score: 复核后的新分数
        max_score: 满分
        question_id: 题目 ID

    Returns:
        List[Dict[str, Any]]: 更新后的批注列表
    """
    if original_score == new_score:
        # 分数没变，不需要修改
        return original_annotations

    updated_annotations = []
    score_annotation_found = False

    for ann in original_annotations:
        ann_type = ann.get("type") or ann.get("annotation_type")

        if ann_type == "score" and ann.get("question_id") == question_id:
            # 更新分数批注的文字
            score_annotation_found = True
            updated_ann = ann.copy()
            updated_ann["text"] = f"{new_score}/{max_score}"

            # 根据新分数更新颜色
            if new_score >= max_score * 0.8:
                updated_ann["color"] = AnnotationColor.GREEN.value
            elif new_score >= max_score * 0.5:
                updated_ann["color"] = AnnotationColor.ORANGE.value
            else:
                updated_ann["color"] = AnnotationColor.RED.value

            updated_annotations.append(updated_ann)
        else:
            # 保留其他批注不变
            updated_annotations.append(ann)

    # 如果没有找到分数批注，添加一个新的
    if not score_annotation_found:
        # 尝试找到该题目的答案区域位置
        answer_region = None
        for ann in original_annotations:
            if ann.get("question_id") == question_id:
                bbox = ann.get("bounding_box") or ann.get("boundingBox")
                if bbox:
                    answer_region = bbox
                    break

        # 如果找到了答案区域，在其右上角添加分数批注
        if answer_region:
            x_max = answer_region.get("x_max", 0.9)
            y_min = answer_region.get("y_min", 0.1)

            new_score_ann = {
                "type": "score",
                "annotation_type": "score",
                "question_id": question_id,
                "bounding_box": {
                    "x_min": min(x_max + 0.02, 0.95),
                    "y_min": y_min,
                    "x_max": min(x_max + 0.1, 1.0),
                    "y_max": y_min + 0.05,
                },
                "text": f"{new_score}/{max_score}",
                "color": (
                    AnnotationColor.GREEN.value
                    if new_score >= max_score * 0.8
                    else (
                        AnnotationColor.ORANGE.value
                        if new_score >= max_score * 0.5
                        else AnnotationColor.RED.value
                    )
                ),
            }
            updated_annotations.append(new_score_ann)

    return updated_annotations


async def regenerate_annotations_for_question(
    service: "AnnotationGradingService",
    image_data: bytes,
    question_id: str,
    new_score: float,
    max_score: float,
    feedback: str,
    page_index: int = 0,
) -> List[Dict[str, Any]]:
    """
    为单道题目重新生成批注（用于分数变化较大的情况）

    当复核后分数变化较大时，可能需要重新生成该题的批注。
    这是一种中等成本的方案，只对分数变化的题目重新调用 LLM。

    Args:
        service: 批注批改服务实例
        image_data: 页面图像数据
        question_id: 题目 ID
        new_score: 新分数
        max_score: 满分
        feedback: 复核反馈
        page_index: 页码

    Returns:
        List[Dict[str, Any]]: 新生成的批注列表
    """
    # 构建单题评分标准
    rubric = QuestionRubric(
        question_id=question_id,
        max_score=max_score,
        grading_notes=f"复核后分数: {new_score}/{max_score}。反馈: {feedback}",
    )

    # 构建提示词
    prompt = f"""请为以下已批改的题目生成批注坐标。

## 题目信息
- 题号: {question_id}
- 得分: {new_score}/{max_score}
- 反馈: {feedback}

## 要求
1. 找到该题目的答案区域
2. 在答案区域旁边标注分数 "{new_score}/{max_score}"
3. 如果有错误，圈出错误位置
4. 输出归一化坐标 (0.0-1.0)

## 输出格式 (JSON)
```json
{{
    "annotations": [
        {{
            "type": "score",
            "bounding_box": {{"x_min": 0.85, "y_min": 0.2, "x_max": 0.95, "y_max": 0.25}},
            "text": "{new_score}/{max_score}",
            "color": "{AnnotationColor.GREEN.value if new_score >= max_score * 0.8 else AnnotationColor.ORANGE.value if new_score >= max_score * 0.5 else AnnotationColor.RED.value}"
        }}
    ]
}}
```
"""

    # 编码图像
    image_b64 = base64.b64encode(image_data).decode("utf-8")

    # 构建消息
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": f"data:image/png;base64,{image_b64}"},
        ]
    )

    # 调用 LLM
    try:
        full_response = ""
        async for chunk in service.llm.astream([message]):
            content = chunk.content
            if content:
                if isinstance(content, str):
                    full_response += content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, str):
                            full_response += part
                        elif isinstance(part, dict) and "text" in part:
                            full_response += part["text"]

        # 解析响应
        json_text = service._extract_json_from_response(full_response)
        data = json.loads(json_text)

        annotations = []
        for ann_data in data.get("annotations", []):
            ann_data["question_id"] = question_id
            ann_data["page_index"] = page_index
            annotations.append(ann_data)

        return annotations
    except Exception as e:
        logger.error(f"重新生成批注失败: {e}")
        # 返回一个基本的分数批注
        return [
            {
                "type": "score",
                "annotation_type": "score",
                "question_id": question_id,
                "page_index": page_index,
                "bounding_box": {
                    "x_min": 0.85,
                    "y_min": 0.1,
                    "x_max": 0.95,
                    "y_max": 0.15,
                },
                "text": f"{new_score}/{max_score}",
                "color": (
                    AnnotationColor.GREEN.value
                    if new_score >= max_score * 0.8
                    else (
                        AnnotationColor.ORANGE.value
                        if new_score >= max_score * 0.5
                        else AnnotationColor.RED.value
                    )
                ),
            }
        ]


# 导出
__all__ = [
    "AnnotationGradingConfig",
    "AnnotationGradingService",
    "ANNOTATION_GRADING_PROMPT",
    "update_annotations_after_review",
    "regenerate_annotations_for_question",
]
