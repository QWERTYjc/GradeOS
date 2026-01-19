"""Document segmentation node for LangGraph."""

import logging
from typing import Dict, Any
from datetime import datetime

from src.graphs.state import GradingGraphState
from src.graphs.retry import RetryConfig, create_retryable_node
from src.services.layout_analysis import LayoutAnalysisService
from src.models.region import SegmentationResult


logger = logging.getLogger(__name__)


async def _segment_node_impl(state: GradingGraphState) -> GradingGraphState:
    """Run document segmentation via LayoutAnalysisService."""
    submission_id = state["submission_id"]
    file_paths = state.get("file_paths", [])
    
    logger.info(
        f"开始文档分割节�? submission_id={submission_id}, "
        f"文件�?{len(file_paths)}"
    )
    
    # 获取布局分析服务实例
    layout_service = LayoutAnalysisService()
    
    # 存储所有页面的分割结果
    all_segments = []
    
    try:
        # 遍历所有文�?页面
        for page_index, file_path in enumerate(file_paths):
            logger.debug(
                f"处理页面: submission_id={submission_id}, "
                f"page_index={page_index}, file_path={file_path}"
            )
            
            # 读取图像数据
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            # 调用布局分析服务
            result: SegmentationResult = await layout_service.segment_document(
                image_data=image_data,
                submission_id=submission_id,
                page_index=page_index
            )
            
            # 将结果添加到列表
            all_segments.append({
                "page_index": page_index,
                "file_path": file_path,
                "regions": [region.dict() for region in result.regions],
                "metadata": result.metadata
            })
            
            logger.info(
                f"页面分割完成: submission_id={submission_id}, "
                f"page_index={page_index}, 识别题目�?{len(result.regions)}"
            )
        
        # 更新状�?
        total_questions = sum(len(seg["regions"]) for seg in all_segments)
        
        updated_state = {
            **state,
            "artifacts": {
                **state.get("artifacts", {}),
                "segmentation_results": all_segments
            },
            "progress": {
                **state.get("progress", {}),
                "segmentation_completed": True,
                "total_questions": total_questions
            },
            "current_stage": "segmentation_completed",
            "percentage": 20.0,  # 分割完成�?20%
            "timestamps": {
                **state.get("timestamps", {}),
                "segmentation_completed_at": datetime.now()
            }
        }
        
        logger.info(
            f"文档分割节点完成: submission_id={submission_id}, "
            f"总题目数={total_questions}"
        )
        
        return updated_state
        
    except ValueError as e:
        # 无法识别题目区域
        logger.warning(
            f"文档分割失败（无法识别题目）: submission_id={submission_id}, "
            f"error={str(e)}"
        )
        
        # 记录错误到状�?
        errors = state.get("errors", [])
        errors.append({
            "node": "segment",
            "error_type": "no_regions_detected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            **state,
            "errors": errors,
            "current_stage": "segmentation_failed"
        }
        
    except Exception as e:
        logger.error(
            f"文档分割节点发生错误: submission_id={submission_id}, "
            f"error={str(e)}",
            exc_info=True
        )
        raise


# 配置重试策略
segment_retry_config = RetryConfig(
    initial_interval=2.0,
    backoff_coefficient=2.0,
    maximum_interval=60.0,
    maximum_attempts=3,
    non_retryable_errors=[ValueError]  # 无法识别题目不重�?
)


async def segment_fallback(state: GradingGraphState, error: Exception) -> GradingGraphState:
    """
    分割失败的降级处�?
    
    当重试耗尽时，记录错误并标记为需要人工介�?
    """
    logger.warning(
        f"文档分割重试耗尽，执行降�? submission_id={state['submission_id']}, "
        f"error={str(error)}"
    )
    
    errors = state.get("errors", [])
    errors.append({
        "node": "segment",
        "error_type": "retry_exhausted",
        "error": str(error),
        "timestamp": datetime.now().isoformat(),
        "fallback_triggered": True
    })
    
    return {
        **state,
        "errors": errors,
        "current_stage": "segmentation_failed",
        "needs_review": True  # 标记需要人工介�?
    }


# 创建带重试的节点
segment_node = create_retryable_node(
    _segment_node_impl,
    segment_retry_config,
    segment_fallback
)
