"""视觉提取节点 - 描述学生解答"""

from typing import Dict, Any
from ...models.state import GradingState
from ...services.gemini_reasoning import GeminiReasoningClient


async def vision_extraction_node(
    state: GradingState,
    reasoning_client: GeminiReasoningClient
) -> Dict[str, Any]:
    """
    视觉提取节点：调用 Gemini 3.0 Pro 描述学生解答
    
    Args:
        state: 当前批改状态
        reasoning_client: Gemini 推理客户端
        
    Returns:
        Dict: 更新的状态字段
    """
    try:
        # 调用 Gemini 进行视觉分析
        vision_analysis = await reasoning_client.vision_extraction(
            question_image_b64=state["question_image"],
            rubric=state["rubric"],
            standard_answer=state.get("standard_answer")
        )
        
        # 初始化推理轨迹
        reasoning_trace = state.get("reasoning_trace", [])
        reasoning_trace.append(f"[视觉提取] {vision_analysis[:200]}...")
        
        return {
            "vision_analysis": vision_analysis,
            "reasoning_trace": reasoning_trace
        }
    except Exception as e:
        # 错误处理
        return {
            "error": f"视觉提取失败: {str(e)}",
            "confidence": 0.0
        }
