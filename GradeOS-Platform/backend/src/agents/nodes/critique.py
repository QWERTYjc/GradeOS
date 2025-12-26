"""自我反思节点 - 审查评分并生成反馈"""

from typing import Dict, Any
from ...models.state import GradingState
from ...services.gemini_reasoning import GeminiReasoningClient


async def critique_node(
    state: GradingState,
    reasoning_client: GeminiReasoningClient
) -> Dict[str, Any]:
    """
    自我反思节点：审查评分并生成反馈
    
    Args:
        state: 当前批改状态
        reasoning_client: Gemini 推理客户端
        
    Returns:
        Dict: 更新的状态字段
    """
    try:
        # 调用 Gemini 进行自我反思
        result = await reasoning_client.critique(
            vision_analysis=state["vision_analysis"],
            rubric=state["rubric"],
            rubric_mapping=state["rubric_mapping"],
            initial_score=state["initial_score"],
            max_score=state["max_score"],
            standard_answer=state.get("standard_answer")
        )
        
        # 更新推理轨迹
        reasoning_trace = state.get("reasoning_trace", [])
        if result.get("needs_revision"):
            reasoning_trace.append(
                f"[反思] 发现问题，需要修正: {result['critique_feedback'][:100]}..."
            )
        else:
            reasoning_trace.append("[反思] 评分合理，无需修正")
        
        # 增加修正计数
        revision_count = state.get("revision_count", 0)
        if result.get("needs_revision"):
            revision_count += 1
        
        return {
            "critique_feedback": result.get("critique_feedback"),
            "confidence": result.get("confidence", 0.5),
            "reasoning_trace": reasoning_trace,
            "revision_count": revision_count
        }
    except Exception as e:
        # 错误处理
        return {
            "error": f"反思节点失败: {str(e)}",
            "confidence": 0.0
        }
