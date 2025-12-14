"""文档分割 Activity - 使用 LayoutAnalysisService 识别题目边界"""

import logging
from typing import List

from temporalio import activity

from src.models.region import SegmentationResult
from src.services.layout_analysis import LayoutAnalysisService


logger = logging.getLogger(__name__)


@activity.defn
async def segment_document_activity(
    submission_id: str,
    image_data: bytes,
    page_index: int = 0,
    layout_service: LayoutAnalysisService = None
) -> SegmentationResult:
    """
    文档分割 Activity
    
    使用 LayoutAnalysisService 调用 Gemini 2.5 Flash Lite 识别试卷中的题目边界。
    
    Args:
        submission_id: 提交 ID
        image_data: 页面图像数据（字节）
        page_index: 页面索引
        layout_service: 布局分析服务实例
        
    Returns:
        SegmentationResult: 包含识别的题目区域列表
        
    Raises:
        ValueError: 当模型未能识别任何题目区域时
        
    验证：需求 2.1, 2.2
    """
    if layout_service is None:
        raise ValueError("layout_service 不能为 None")
    
    logger.info(
        f"开始文档分割: submission_id={submission_id}, "
        f"page_index={page_index}, image_size={len(image_data)} bytes"
    )
    
    try:
        # 调用布局分析服务
        result = await layout_service.segment_document(
            image_data=image_data,
            submission_id=submission_id,
            page_index=page_index
        )
        
        logger.info(
            f"文档分割成功: submission_id={submission_id}, "
            f"识别题目数={len(result.regions)}"
        )
        
        return result
        
    except ValueError as e:
        # 无法识别题目区域
        logger.warning(f"文档分割失败（无法识别题目）: {str(e)}")
        raise
        
    except Exception as e:
        logger.error(f"文档分割发生错误: {str(e)}", exc_info=True)
        raise
