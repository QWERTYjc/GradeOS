"""学生边界检测相关 Activities

提供学生边界检测的 Activity 实现。
"""

import logging
from typing import List, Dict, Any

from temporalio import activity

from src.services.student_boundary_detector import StudentBoundaryDetector
from src.services.student_identification import StudentIdentificationService


logger = logging.getLogger(__name__)


@activity.defn
async def detect_student_boundaries_activity(
    grading_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    检测学生边界 Activity
    
    Args:
        grading_results: 批改结果列表
        
    Returns:
        边界检测结果: {
            "boundaries": List[Dict],
            "total_students": int,
            "unassigned_pages": List[int],
            "total_pages": int
        }
    """
    try:
        # 初始化服务
        student_identification_service = StudentIdentificationService()
        boundary_detector = StudentBoundaryDetector(
            student_identification_service=student_identification_service
        )
        
        # 执行边界检测
        result = await boundary_detector.detect_boundaries(grading_results)
        
        # 转换为字典格式
        boundaries_dict = []
        for boundary in result.boundaries:
            boundaries_dict.append({
                "student_key": boundary.student_key,
                "start_page": boundary.start_page,
                "end_page": boundary.end_page,
                "confidence": boundary.confidence,
                "needs_confirmation": boundary.needs_confirmation,
                "detection_method": boundary.detection_method
            })
        
        return {
            "boundaries": boundaries_dict,
            "total_students": result.total_students,
            "unassigned_pages": result.unassigned_pages,
            "total_pages": result.total_pages
        }
        
    except Exception as e:
        logger.error(f"学生边界检测失败: {e}")
        # 返回空结果而不是抛出异常
        return {
            "boundaries": [],
            "total_students": 0,
            "unassigned_pages": list(range(len(grading_results))),
            "total_pages": len(grading_results)
        }
