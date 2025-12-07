"""评分映射节点 - 将评分点映射到证据"""

from typing import Dict, Any
from ...models.state import GradingState
from ...services.gemini_reasoning import GeminiReasoningClient


async def rubric_mapping_node(
    state: GradingState,
    reasoning_client: GeminiReasoningClient
) -> Dict[str, Any]:
    """
    评分映射节点：将评分点映射到证据
    
    Args:
        state: 当前批改状态
        reasoning_client: Gemini 推理客户端
        
    Returns:
        Dict: 更新的状态字段
    """
    try:
        # 调用 Gemini 进行评分映射
        result = await reasoning_client.rubric_mapping(
            vision_analysis=state["vision_analysis"],
            rubric=state["rubric"],
            max_score=state["max_score"],
            standard_answer=state.get("standard_answer"),
            critique_feedback=state.get("critique_feedback")
        )
        
        # 更新推理轨迹
        reasoning_trace = state.get("reasoning_trace", [])
        reasoning_trace.append(
            f"[评分映射] 初始评分: {result['initial_score']}/{state['max_score']}"
        )
        
        return {
            "rubric_mapping": result["rubric_mapping"],
            "initial_score": result["initial_score"],
            "reasoning_trace": reasoning_trace
        }
    except Exception as e:
        # 错误处理
        return {
            "error": f"评分映射失败: {str(e)}",
            "confidence": 0.0
        }
