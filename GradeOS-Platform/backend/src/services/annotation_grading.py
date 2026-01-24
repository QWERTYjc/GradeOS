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
from src.models.grading_models import QuestionRubric, QuestionResult, ScoringPointResult, ScoringPoint


logger = logging.getLogger(__name__)


# 批注批改提示词模板
ANNOTATION_GRADING_PROMPT = """你是一位专业的阅卷老师，请对学生答卷进行批改，并输出带坐标的批注信息。

## 评分标准
{rubric_context}

## 批改要求
1. **识别答题区域**：找出每道题的作答位置
2. **逐题评分**：根据评分标准给出分数
3. **标注错误**：圈出错误位置，给出讲解
4. **输出坐标**：所有批注都要输出归一化坐标 (0.0-1.0)

## 坐标系统说明
- 坐标原点在图片**左上角**
- x 轴向右增加 (0.0 = 最左, 1.0 = 最右)
- y 轴向下增加 (0.0 = 最上, 1.0 = 最下)
- 使用 bounding_box 表示区域: {{x_min, y_min, x_max, y_max}}

## 批注类型
- `score`: 分数标注，放在题目答案旁边
- `error_circle`: 错误圈选，圈出错误的地方
- `error_underline`: 错误下划线
- `correct_check`: 正确勾选 ✓
- `partial_check`: 部分正确 △
- `wrong_cross`: 错误叉 ✗
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
            "scoring_details": [
                {{
                    "point_id": "1.1",
                    "description": "正确列出方程",
                    "max_score": 3,
                    "awarded_score": 3,
                    "is_correct": true,
                    "evidence": "学生正确写出 x + y = 10"
                }},
                {{
                    "point_id": "1.2",
                    "description": "正确求解",
                    "max_score": 7,
                    "awarded_score": 5,
                    "is_correct": false,
                    "evidence": "计算过程有误，3+5=9 写成了 3+5=8",
                    "error_region": {{
                        "x_min": 0.3,
                        "y_min": 0.35,
                        "x_max": 0.5,
                        "y_max": 0.38
                    }}
                }}
            ],
            "annotations": [
                {{
                    "type": "score",
                    "bounding_box": {{"x_min": 0.85, "y_min": 0.2, "x_max": 0.95, "y_max": 0.25}},
                    "text": "8/10",
                    "color": "#FF8800"
                }},
                {{
                    "type": "error_circle",
                    "bounding_box": {{"x_min": 0.3, "y_min": 0.35, "x_max": 0.5, "y_max": 0.38}},
                    "text": "计算错误：3+5=8",
                    "color": "#FF0000"
                }},
                {{
                    "type": "comment",
                    "bounding_box": {{"x_min": 0.55, "y_min": 0.35, "x_max": 0.9, "y_max": 0.4}},
                    "text": "应为 3+5=8，请检查计算",
                    "color": "#0066FF"
                }},
                {{
                    "type": "correct_check",
                    "bounding_box": {{"x_min": 0.88, "y_min": 0.25, "x_max": 0.92, "y_max": 0.28}},
                    "text": "",
                    "color": "#00AA00"
                }}
            ]
        }}
    ],
    "total_score": 8,
    "max_score": 10,
    "overall_feedback": "整体表现良好，注意计算准确性"
}}
```

## 重要提示
1. **坐标必须准确**：仔细观察图片，给出精确的坐标位置
2. **分数标注位置**：通常放在答案区域的右上角或右侧
3. **错误圈选**：只圈出具体错误的部分，不要圈太大范围
4. **讲解位置**：放在错误旁边或下方，不要遮挡答案
5. **颜色规范**：
   - 红色 #FF0000：错误
   - 绿色 #00AA00：正确
   - 橙色 #FF8800：部分正确
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
                    point_id = sp.point_id or f"{rubric.question_id}.{rubric.scoring_points.index(sp)+1}"
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
            json_text = re.sub(r',\s*}', '}', json_text)
            json_text = re.sub(r',\s*]', ']', json_text)
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
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        # 构建提示词
        rubric_context = self._format_rubric_context(rubrics)
        prompt = ANNOTATION_GRADING_PROMPT.format(rubric_context=rubric_context)
        
        # 构建消息
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{image_b64}"
                }
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


# 导出
__all__ = [
    "AnnotationGradingConfig",
    "AnnotationGradingService",
    "ANNOTATION_GRADING_PROMPT",
]
