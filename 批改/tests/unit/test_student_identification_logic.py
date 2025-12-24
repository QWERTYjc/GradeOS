"""学生识别逻辑单元测试 - 不依赖 LLM"""

import pytest
from src.services.student_identification import (
    StudentInfo,
    PageStudentMapping,
    BatchSegmentationResult,
    StudentIdentificationService
)


def test_group_pages_by_student_basic():
    """测试基本的页面分组功能"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    # 模拟 3 个学生，每人 2 页
    mappings = [
        PageStudentMapping(
            page_index=0,
            student_info=StudentInfo(name="张三", student_id="2024001", confidence=0.9),
            is_first_page=True
        ),
        PageStudentMapping(
            page_index=1,
            student_info=StudentInfo(name="张三", student_id="2024001", confidence=0.9),
            is_first_page=False
        ),
        PageStudentMapping(
            page_index=2,
            student_info=StudentInfo(name="李四", student_id="2024002", confidence=0.85),
            is_first_page=True
        ),
        PageStudentMapping(
            page_index=3,
            student_info=StudentInfo(name="李四", student_id="2024002", confidence=0.85),
            is_first_page=False
        ),
        PageStudentMapping(
            page_index=4,
            student_info=StudentInfo(name="王五", student_id="2024003", confidence=0.92),
            is_first_page=True
        ),
        PageStudentMapping(
            page_index=5,
            student_info=StudentInfo(name="王五", student_id="2024003", confidence=0.92),
            is_first_page=False
        ),
    ]
    
    batch_result = BatchSegmentationResult(
        total_pages=6,
        student_count=3,
        page_mappings=mappings,
        unidentified_pages=[]
    )
    
    groups = service.group_pages_by_student(batch_result)
    
    # 验证分组结果
    assert len(groups) == 3
    assert "2024001" in groups
    assert "2024002" in groups
    assert "2024003" in groups
    
    assert groups["2024001"] == [0, 1]
    assert groups["2024002"] == [2, 3]
    assert groups["2024003"] == [4, 5]


def test_group_pages_with_low_confidence():
    """测试低置信度页面被分组到 unknown"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    mappings = [
        PageStudentMapping(
            page_index=0,
            student_info=StudentInfo(name="张三", student_id="2024001", confidence=0.9),
            is_first_page=True
        ),
        PageStudentMapping(
            page_index=1,
            student_info=StudentInfo(confidence=0.2),  # 低置信度
            is_first_page=False
        ),
        PageStudentMapping(
            page_index=2,
            student_info=StudentInfo(name="李四", student_id="2024002", confidence=0.85),
            is_first_page=True
        ),
    ]
    
    batch_result = BatchSegmentationResult(
        total_pages=3,
        student_count=2,
        page_mappings=mappings,
        unidentified_pages=[1]
    )
    
    groups = service.group_pages_by_student(batch_result)
    
    # 低置信度页面被分组到 unknown_1
    assert len(groups) == 3
    assert "2024001" in groups
    assert "2024002" in groups
    assert "unknown_1" in groups
    assert groups["2024001"] == [0]
    assert groups["2024002"] == [2]
    assert groups["unknown_1"] == [1]


def test_group_pages_20_students():
    """测试 20 个学生的分组场景"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    # 模拟 20 个学生，每人 2 页
    mappings = []
    for i in range(20):
        student_id = f"2024{i+1:03d}"
        student_name = f"学生{i+1}"
        
        # 第一页
        mappings.append(PageStudentMapping(
            page_index=i*2,
            student_info=StudentInfo(
                name=student_name,
                student_id=student_id,
                confidence=0.9
            ),
            is_first_page=True
        ))
        
        # 第二页（无学生信息，但归属于同一学生）
        mappings.append(PageStudentMapping(
            page_index=i*2+1,
            student_info=StudentInfo(
                name=student_name,
                student_id=student_id,
                confidence=0.9
            ),
            is_first_page=False
        ))
    
    batch_result = BatchSegmentationResult(
        total_pages=40,
        student_count=20,
        page_mappings=mappings,
        unidentified_pages=[]
    )
    
    groups = service.group_pages_by_student(batch_result)
    
    # 验证结果
    assert len(groups) == 20, f"应该有 20 个学生，实际 {len(groups)}"
    
    for i in range(20):
        student_id = f"2024{i+1:03d}"
        assert student_id in groups, f"缺少学生 {student_id}"
        assert len(groups[student_id]) == 2, f"学生 {student_id} 应该有 2 页"
        assert groups[student_id] == [i*2, i*2+1]


def test_student_info_dataclass():
    """测试 StudentInfo 数据类"""
    
    info = StudentInfo(
        name="张三",
        student_id="2024001",
        class_name="高三(1)班",
        confidence=0.95
    )
    
    assert info.name == "张三"
    assert info.student_id == "2024001"
    assert info.class_name == "高三(1)班"
    assert info.confidence == 0.95
    assert info.bounding_box is None


def test_batch_segmentation_result():
    """测试批量分割结果数据类"""
    
    result = BatchSegmentationResult(
        total_pages=10,
        student_count=5,
        page_mappings=[],
        unidentified_pages=[3, 7]
    )
    
    assert result.total_pages == 10
    assert result.student_count == 5
    assert len(result.unidentified_pages) == 2
    assert 3 in result.unidentified_pages
    assert 7 in result.unidentified_pages


def test_group_pages_with_name_only():
    """测试只有姓名没有学号的情况"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    mappings = [
        PageStudentMapping(
            page_index=0,
            student_info=StudentInfo(name="张三", confidence=0.9),  # 只有姓名
            is_first_page=True
        ),
        PageStudentMapping(
            page_index=1,
            student_info=StudentInfo(name="张三", confidence=0.9),
            is_first_page=False
        ),
    ]
    
    batch_result = BatchSegmentationResult(
        total_pages=2,
        student_count=1,
        page_mappings=mappings,
        unidentified_pages=[]
    )
    
    groups = service.group_pages_by_student(batch_result)
    
    # 应该使用姓名作为 key
    assert len(groups) == 1
    assert "张三" in groups
    assert groups["张三"] == [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
