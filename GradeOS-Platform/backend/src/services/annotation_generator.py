"""批注坐标生成服务

使用 VLM (Gemini) 分析答题图片，为批改结果生成精确的批注坐标。
"""

import base64
import json
import logging
import uuid
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.db.postgres_grading import GradingAnnotation, GradingPageImage, StudentGradingResult
from src.db.postgres_images import get_batch_images_as_bytes_list


logger = logging.getLogger(__name__)


async def generate_annotations_for_student(
    grading_history_id: str,
    student_key: str,
    student_result: StudentGradingResult,
    page_images: List[GradingPageImage],
    batch_id: Optional[str] = None,
    page_indices: Optional[List[int]] = None,
) -> List[GradingAnnotation]:
    """
    为学生生成批注坐标
    
    Args:
        grading_history_id: 批改历史 ID
        student_key: 学生标识
        student_result: 学生批改结果
        page_images: 页面图片列表
        page_indices: 指定页码列表，None 表示所有页
    
    Returns:
        生成的批注列表
    """
    annotations: List[GradingAnnotation] = []
    now = datetime.now().isoformat()
    
    # 解析批改结果
    result_data = student_result.result_data or {}
    question_results = (
        result_data.get("question_results") 
        or result_data.get("questionResults")
        or result_data.get("question_details")
        or []
    )
    
    if not question_results:
        logger.warning(f"学生 {student_key} 没有批改结果数据")
        return annotations
    
    # 按页面分组图片
    page_image_map: Dict[int, GradingPageImage] = {}
    for img in page_images:
        if page_indices is None or img.page_index in page_indices:
            page_image_map[img.page_index] = img

    # 批次图片作为兜底（当未找到页面图片或页面图片缺失URL时）
    fallback_images: Dict[int, bytes] = {}
    needs_fallback = not page_image_map or any(
        not getattr(img, "file_url", None) for img in page_images
    )
    if batch_id and needs_fallback:
        try:
            batch_images = await get_batch_images_as_bytes_list(batch_id, "answer")
            if batch_images:
                fallback_images = {idx: img for idx, img in enumerate(batch_images)}
                logger.info(
                    f"[Annotation] 已加载 batch_images 作为兜底: batch_id={batch_id}, count={len(batch_images)}"
                )
        except Exception as e:
            logger.warning(f"[Annotation] 兜底加载 batch_images 失败: {e}")

    if not page_image_map and fallback_images:
        for idx in fallback_images.keys():
            if page_indices is not None and idx not in page_indices:
                continue
            page_image_map[idx] = GradingPageImage(
                id=str(uuid.uuid4()),
                grading_history_id=grading_history_id,
                student_key=student_key,
                page_index=idx,
                file_id="",
                file_url=None,
                content_type="image/jpeg",
                created_at=now,
            )
    
    if not page_image_map:
        logger.warning(f"学生 {student_key} 没有可用的页面图片")
        return annotations

    # Imported grading results often store question.page_indices as 0..N-1 (relative
    # to the student's answer pages) while page_images.page_index may be absolute
    # PDF page numbers (e.g. 26, 27). Build a stable mapping so we can match
    # questions to pages in both cases.
    sorted_page_indices = sorted(page_image_map.keys())
    actual_to_relative: Dict[int, int] = {actual: idx for idx, actual in enumerate(sorted_page_indices)}
    logger.info(
        f"[Annotation] page_index mapping for {student_key}: actual={sorted_page_indices} "
        f"-> relative=0..{len(sorted_page_indices) - 1}"
    )
    
    # 为每个页面生成批注
    for page_idx, page_image in page_image_map.items():
        try:
            page_annotations = await _generate_annotations_for_page(
                grading_history_id=grading_history_id,
                student_key=student_key,
                page_index=page_idx,
                question_page_index=actual_to_relative.get(page_idx, page_idx),
                page_image=page_image,
                question_results=question_results,
                fallback_images=fallback_images or None,
            )
            annotations.extend(page_annotations)
        except Exception as e:
            logger.error(f"页面 {page_idx} 批注生成失败: {e}")
            continue
    
    return annotations


async def _generate_annotations_for_page(
    grading_history_id: str,
    student_key: str,
    page_index: int,
    question_page_index: int,
    page_image: GradingPageImage,
    question_results: List[Dict[str, Any]],
    fallback_images: Optional[Dict[int, bytes]] = None,
) -> List[GradingAnnotation]:
    """为单个页面生成批注"""
    annotations: List[GradingAnnotation] = []
    now = datetime.now().isoformat()
    
    # 筛选该页面的题目
    page_questions = []
    for q in question_results:
        q_pages = q.get("page_indices") or q.get("pageIndices") or []
        # Prefer matching against the "question page index" (usually 0..N-1),
        # but keep compatibility with payloads that store absolute page indices.
        if question_page_index in q_pages or page_index in q_pages or not q_pages:
            page_questions.append(q)
    
    if not page_questions:
        logger.info(f"页面 {page_index} 没有关联的题目")
        return annotations
    
    # 获取图片数据
    image_data = await _fetch_image_data(page_image, fallback_images=fallback_images)
    if not image_data:
        logger.warning(f"无法获取页面 {page_index} 的图片数据")
        # 使用估算位置生成批注
        return _generate_estimated_annotations(
            grading_history_id, student_key, page_index, page_questions, now
        )
    
    # 调用 VLM 获取精确坐标
    try:
        vlm_annotations = await _call_vlm_for_annotations(
            image_data=image_data,
            page_index=page_index,
            questions=page_questions,
        )
        
        for ann_data in vlm_annotations:
            annotation = GradingAnnotation(
                id=str(uuid.uuid4()),
                grading_history_id=grading_history_id,
                student_key=student_key,
                page_index=page_index,
                annotation_type=ann_data.get("type", "score"),
                bounding_box=ann_data.get("bounding_box", {}),
                text=ann_data.get("text", ""),
                color=ann_data.get("color", "#FF0000"),
                question_id=ann_data.get("question_id", ""),
                scoring_point_id=ann_data.get("scoring_point_id", ""),
                created_by="ai",
                created_at=now,
                updated_at=now,
            )
            annotations.append(annotation)
        
    except Exception as e:
        logger.error(f"VLM 批注生成失败: {e}")
        # 降级到估算位置
        annotations = _generate_estimated_annotations(
            grading_history_id, student_key, page_index, page_questions, now
        )
    
    return annotations


async def _fetch_image_data(
    page_image: GradingPageImage,
    fallback_images: Optional[Dict[int, bytes]] = None,
) -> Optional[bytes]:
    """获取图片数据"""
    try:
        if page_image.file_url:
            # 从 URL 获取图片
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(page_image.file_url)
                if response.status_code == 200:
                    return response.content
        if fallback_images:
            fallback = fallback_images.get(page_image.page_index)
            if fallback:
                return fallback
        return None
    except Exception as e:
        logger.error(f"获取图片失败: {e}")
        return None


async def _call_vlm_for_annotations(
    image_data: bytes,
    page_index: int,
    questions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """调用 VLM 生成批注坐标"""
    from src.services.llm_reasoning import LLMReasoningClient
    
    # 构建 prompt
    prompt = _build_annotation_prompt(questions, page_index)
    
    # 调用 VLM
    client = LLMReasoningClient()
    
    # 编码图片
    image_b64 = base64.b64encode(image_data).decode("utf-8")
    
    try:
        result = await client.generate_annotations(
            image_base64=image_b64,
            prompt=prompt,
        )
        # LLMReasoningClient.generate_annotations returns {"annotations": [], "error": "..."} on failures
        # (e.g. OpenRouter 403). Treat that as a hard failure so the caller can fall back to
        # deterministic estimated annotations.
        if isinstance(result, dict):
            err = result.get("error")
            anns = result.get("annotations") or []
        else:
            err = None
            anns = []

        if err:
            raise RuntimeError(f"VLM returned error: {err}")
        if not anns:
            raise RuntimeError("VLM returned empty annotations")
        return anns
    except Exception as e:
        logger.error(f"VLM 调用失败: {e}")
        raise


def _build_annotation_prompt(questions: List[Dict[str, Any]], page_index: int) -> str:
    """构建批注生成 prompt"""
    
    # 构建题目信息
    questions_info = []
    for q in questions:
        qid = q.get("question_id") or q.get("questionId") or "unknown"
        score = q.get("score", 0)
        max_score = q.get("max_score") or q.get("maxScore", 0)
        feedback = q.get("feedback", "")
        student_answer = q.get("student_answer") or q.get("studentAnswer", "")
        
        scoring_points = q.get("scoring_point_results") or q.get("scoringPointResults") or []
        points_info = []
        for sp in scoring_points:
            point_id = sp.get("point_id") or sp.get("pointId", "")
            awarded = sp.get("awarded", 0)
            max_pts = sp.get("max_points") or sp.get("maxPoints", 1)
            evidence = sp.get("evidence", "")
            points_info.append({
                "point_id": point_id,
                "awarded": awarded,
                "max_points": max_pts,
                "evidence": evidence[:100] if evidence else "",
            })
        
        questions_info.append({
            "question_id": qid,
            "score": score,
            "max_score": max_score,
            "feedback": feedback[:200] if feedback else "",
            "student_answer_preview": student_answer[:100] if student_answer else "",
            "scoring_points": points_info,
        })
    
    prompt = f"""# 任务：为批改结果定位批注坐标

请分析这张答题图片，为以下批改结果定位批注位置。

## 页面信息
- 页码: {page_index + 1}

## 批改结果（需要标注）
{json.dumps(questions_info, ensure_ascii=False, indent=2)}

## 要求

1. **定位学生答案区域**：找到每道题学生作答的位置
2. **标注分数**：在答案区域右侧或下方放置分数标注
3. **标注错误**：如果有错误，圈出错误位置
4. **得分点标注**：为每个得分点的关键位置添加 M/A mark

## 坐标系统
- 使用归一化坐标 (0.0-1.0)
- 原点在左上角
- x 向右增加，y 向下增加

## 输出格式（JSON）
```json
{{
    "annotations": [
        {{
            "type": "score",
            "question_id": "1",
            "bounding_box": {{"x_min": 0.8, "y_min": 0.1, "x_max": 0.95, "y_max": 0.15}},
            "text": "3/5",
            "color": "#FF8800"
        }},
        {{
            "type": "m_mark",
            "question_id": "1",
            "scoring_point_id": "1.1",
            "bounding_box": {{"x_min": 0.75, "y_min": 0.12, "x_max": 0.78, "y_max": 0.15}},
            "text": "M1",
            "color": "#00AA00"
        }},
        {{
            "type": "error_circle",
            "question_id": "1",
            "bounding_box": {{"x_min": 0.3, "y_min": 0.15, "x_max": 0.5, "y_max": 0.2}},
            "text": "计算错误",
            "color": "#FF0000"
        }}
    ]
}}
```

## 批注类型
- `score`: 分数标注（放在答案区域旁边）
- `m_mark`: 方法分标注（M1/M0）
- `a_mark`: 答案分标注（A1/A0）
- `error_circle`: 错误圈选
- `comment`: 文字批注

## 颜色规范
- 绿色 #00AA00: 正确
- 红色 #FF0000: 错误
- 橙色 #FF8800: 部分正确

请仔细观察图片，给出精确的批注坐标。只输出 JSON，不要其他内容。
"""
    return prompt


def _generate_estimated_annotations(
    grading_history_id: str,
    student_key: str,
    page_index: int,
    questions: List[Dict[str, Any]],
    now: str,
) -> List[GradingAnnotation]:
    """
    生成估算位置的批注（当 VLM 不可用时的降级方案）
    
    基于题目数量均匀分布批注位置
    """
    annotations: List[GradingAnnotation] = []
    
    total_questions = len(questions)
    if total_questions == 0:
        return annotations
    
    # 计算每道题的垂直区域
    margin_top = 0.1
    margin_bottom = 0.1
    available_height = 1.0 - margin_top - margin_bottom
    height_per_question = available_height / max(total_questions, 1)
    
    for idx, q in enumerate(questions):
        qid = q.get("question_id") or q.get("questionId") or str(idx + 1)
        score = q.get("score", 0)
        max_score = q.get("max_score") or q.get("maxScore", 0)
        
        # 计算该题的 y 位置
        y_start = margin_top + idx * height_per_question
        y_center = y_start + height_per_question / 2
        
        # 添加分数标注（右侧）
        score_color = (
            "#00AA00" if score >= max_score * 0.8
            else "#FF8800" if score >= max_score * 0.5
            else "#FF0000"
        )
        annotations.append(
            GradingAnnotation(
                id=str(uuid.uuid4()),
                grading_history_id=grading_history_id,
                student_key=student_key,
                page_index=page_index,
                annotation_type="score",
                bounding_box={
                    "x_min": 0.85,
                    "y_min": y_center - 0.02,
                    "x_max": 0.95,
                    "y_max": y_center + 0.02,
                },
                text=f"{score}/{max_score}",
                color=score_color,
                question_id=qid,
                scoring_point_id="",
                created_by="ai",
                created_at=now,
                updated_at=now,
            )
        )
        
        # 添加得分点标注
        scoring_points = q.get("scoring_point_results") or q.get("scoringPointResults") or []
        for sp_idx, sp in enumerate(scoring_points[:4]):  # 最多显示 4 个得分点
            point_id = sp.get("point_id") or sp.get("pointId", f"{qid}.{sp_idx + 1}")
            awarded = sp.get("awarded", 0)
            max_pts = sp.get("max_points") or sp.get("maxPoints", 1)
            
            mark_type = sp.get("mark_type") or "M"
            mark_text = f"{mark_type}{1 if awarded > 0 else 0}"
            mark_color = "#00AA00" if awarded > 0 else "#FF0000"
            
            y_offset = y_start + (sp_idx + 1) * (height_per_question / (len(scoring_points) + 2))
            
            annotations.append(
                GradingAnnotation(
                    id=str(uuid.uuid4()),
                    grading_history_id=grading_history_id,
                    student_key=student_key,
                    page_index=page_index,
                    annotation_type="m_mark" if mark_type == "M" else "a_mark",
                    bounding_box={
                        "x_min": 0.78,
                        "y_min": y_offset - 0.015,
                        "x_max": 0.83,
                        "y_max": y_offset + 0.015,
                    },
                    text=mark_text,
                    color=mark_color,
                    question_id=qid,
                    scoring_point_id=point_id,
                    created_by="ai",
                    created_at=now,
                    updated_at=now,
                )
            )
    
    return annotations
