"""最终化节点 - 格式化最终输出"""

from typing import Dict, Any, List
from ...models.state import GradingState


async def finalization_node(state: GradingState) -> Dict[str, Any]:
    """
    最终化节点：格式化最终输出
    
    Args:
        state: 当前批改状态
        
    Returns:
        Dict: 更新的状态字段
    """
    try:
        # 使用 initial_score 作为 final_score
        final_score = state.get("initial_score", 0.0)
        
        # 生成学生反馈
        student_feedback = _generate_student_feedback(
            rubric_mapping=state.get("rubric_mapping", []),
            final_score=final_score,
            max_score=state.get("max_score", 0.0)
        )
        
        # 生成视觉标注（用于前端高亮错误）
        visual_annotations = _generate_visual_annotations(
            rubric_mapping=state.get("rubric_mapping", [])
        )
        
        # 更新推理轨迹
        reasoning_trace = state.get("reasoning_trace", [])
        reasoning_trace.append(
            f"[最终化] 最终得分: {final_score}/{state.get('max_score', 0.0)}, "
            f"置信度: {state.get('confidence', 0.0):.2f}"
        )
        
        return {
            "final_score": final_score,
            "student_feedback": student_feedback,
            "visual_annotations": visual_annotations,
            "reasoning_trace": reasoning_trace,
            "is_finalized": True
        }
    except Exception as e:
        # 错误处理
        return {
            "error": f"最终化失败: {str(e)}",
            "confidence": 0.0,
            "is_finalized": True
        }


def _generate_student_feedback(
    rubric_mapping: List[Dict[str, Any]],
    final_score: float,
    max_score: float
) -> str:
    """
    生成给学生的反馈
    
    Args:
        rubric_mapping: 评分点映射
        final_score: 最终得分
        max_score: 满分
        
    Returns:
        str: 学生反馈文本
    """
    feedback_parts = [f"你的得分：{final_score}/{max_score}\n"]
    
    for item in rubric_mapping:
        rubric_point = item.get("rubric_point", "")
        evidence = item.get("evidence", "")
        score_awarded = item.get("score_awarded", 0)
        item_max_score = item.get("max_score", 0)
        
        if score_awarded == item_max_score:
            feedback_parts.append(f"✓ {rubric_point} ({score_awarded}/{item_max_score}分)")
        else:
            feedback_parts.append(
                f"✗ {rubric_point} ({score_awarded}/{item_max_score}分)\n"
                f"  说明: {evidence}"
            )
    
    return "\n".join(feedback_parts)


def _generate_visual_annotations(
    rubric_mapping: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    生成视觉标注（用于前端高亮）
    
    Args:
        rubric_mapping: 评分点映射
        
    Returns:
        List[Dict]: 视觉标注列表
    """
    annotations = []
    
    for item in rubric_mapping:
        score_awarded = item.get("score_awarded", 0)
        item_max_score = item.get("max_score", 0)
        
        # 如果未得满分，添加标注
        if score_awarded < item_max_score:
            annotations.append({
                "type": "error",
                "rubric_point": item.get("rubric_point", ""),
                "evidence": item.get("evidence", ""),
                "score_lost": item_max_score - score_awarded
            })
    
    return annotations
