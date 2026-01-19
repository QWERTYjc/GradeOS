"""Vision extraction node."""

from typing import Dict, Any
from ...models.state import GradingState
from ...services.llm_reasoning import LLMReasoningClient


async def vision_extraction_node(
    state: GradingState,
    reasoning_client: LLMReasoningClient
) -> Dict[str, Any]:
    """Extract vision analysis from LLM."""
    try:
        # 调用 LLM 进行视觉分析
        vision_analysis = await reasoning_client.vision_extraction(
            question_image_b64=state["question_image"],
            rubric=state["rubric"],
            standard_answer=state.get("standard_answer")
        )
        
        # 初始化推理轨?
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
