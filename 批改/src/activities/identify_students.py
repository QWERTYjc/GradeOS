"""学生身份识别 Activity - 从合卷文档中识别各学生"""

import logging
from typing import List, Dict, Any

from temporalio import activity

from src.services.student_identification import (
    StudentIdentificationService,
    BatchSegmentationResult,
    StudentInfo,
    PageStudentMapping
)


logger = logging.getLogger(__name__)


@activity.defn
async def identify_students_activity(
    images_data: List[bytes],
    identification_service: StudentIdentificationService = None
) -> Dict[str, Any]:
    """
    学生身份识别 Activity
    
    扫描多页文档，识别每页所属的学生。
    
    Args:
        images_data: 所有页面的图像数据
        identification_service: 学生识别服务实例
        
    Returns:
        dict: 包含分组结果的字典
            - student_groups: {student_key: [page_indices]}
            - student_info: {student_key: {name, student_id, class_name}}
            - unidentified_pages: [page_indices]
            - total_students: int
    """
    if identification_service is None:
        raise ValueError("identification_service 不能为 None")
    
    logger.info(f"开始学生身份识别: 共 {len(images_data)} 页")
    
    try:
        # 执行批量分割
        batch_result = await identification_service.segment_batch_document(
            images_data
        )
        
        # 按学生分组
        student_groups = identification_service.group_pages_by_student(
            batch_result
        )
        
        # 提取学生信息
        student_info = {}
        for mapping in batch_result.page_mappings:
            if mapping.student_info.confidence >= 0.3:
                key = (
                    mapping.student_info.student_id or
                    mapping.student_info.name
                )
                if key and key not in student_info:
                    student_info[key] = {
                        "name": mapping.student_info.name,
                        "student_id": mapping.student_info.student_id,
                        "class_name": mapping.student_info.class_name,
                        "confidence": mapping.student_info.confidence
                    }
        
        result = {
            "student_groups": student_groups,
            "student_info": student_info,
            "unidentified_pages": batch_result.unidentified_pages,
            "total_students": batch_result.student_count
        }
        
        logger.info(
            f"学生身份识别完成: "
            f"识别到 {batch_result.student_count} 名学生, "
            f"未识别 {len(batch_result.unidentified_pages)} 页"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"学生身份识别失败: {str(e)}", exc_info=True)
        raise
