"""批量学生识别集成测试

测试多学生合卷场景下的学生身份识别和页面分组功能。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO
from PIL import Image

from src.services.student_identification import (
    StudentIdentificationService,
    StudentInfo,
    BatchSegmentationResult
)


def create_mock_exam_page(student_name: str, student_id: str, width: int = 800, height: int = 1000) -> bytes:
    """创建模拟试卷页面图像"""
    img = Image.new('RGB', (width, height), color='white')
    # 实际应用中这里会有学生信息和题目内容
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


@pytest.mark.asyncio
async def test_identify_single_student():
    """测试识别单个学生信息"""
    
    # 创建模拟服务
    service = StudentIdentificationService(api_key="test-key")
    
    # Mock LLM 响应
    mock_response = MagicMock()
    mock_response.content = """```json
{
    "found": true,
    "student_info": {
        "name": "张三",
        "student_id": "2024001",
        "class_name": "高三(1)班",
        "confidence": 0.95,
        "bounding_box": [50, 100, 150, 600]
    }
}
```"""
    
    with patch.object(service.llm, 'ainvoke', return_value=mock_response):
        image_data = create_mock_exam_page("张三", "2024001")
        result = await service.identify_student(image_data, page_index=0)
        
        assert result.name == "张三"
        assert result.student_id == "2024001"
        assert result.class_name == "高三(1)班"
        assert result.confidence == 0.95
        assert result.bounding_box is not None


@pytest.mark.asyncio
async def test_identify_no_student_info():
    """测试无学生信息的页面"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    mock_response = MagicMock()
    mock_response.content = """```json
{
    "found": false,
    "student_info": {}
}
```"""
    
    with patch.object(service.llm, 'ainvoke', return_value=mock_response):
        image_data = create_mock_exam_page("", "")
        result = await service.identify_student(image_data, page_index=0)
        
        assert result.confidence == 0.0
        assert result.name is None
        assert result.student_id is None


@pytest.mark.asyncio
async def test_segment_batch_document_multiple_students():
    """测试批量分割：多个学生的合卷"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    # 模拟 20 个学生，每人 2 页试卷
    students = [
        {"name": f"学生{i}", "id": f"2024{i:03d}", "confidence": 0.9}
        for i in range(1, 21)
    ]
    
    # 创建 40 页图像数据
    images_data = []
    for student in students:
        # 每个学生 2 页
        images_data.append(create_mock_exam_page(student["name"], student["id"]))
        images_data.append(create_mock_exam_page(student["name"], student["id"]))
    
    # Mock LLM 响应
    call_count = 0
    
    async def mock_ainvoke(messages):
        nonlocal call_count
        page_idx = call_count
        call_count += 1
        
        # 每个学生的第一页有学生信息，第二页没有
        student_idx = page_idx // 2
        is_first_page = page_idx % 2 == 0
        
        if is_first_page and student_idx < len(students):
            student = students[student_idx]
            content = f"""```json
{{
    "found": true,
    "student_info": {{
        "name": "{student['name']}",
        "student_id": "{student['id']}",
        "class_name": "高三(1)班",
        "confidence": {student['confidence']},
        "bounding_box": [50, 100, 150, 600]
    }}
}}
```"""
        else:
            # 第二页没有学生信息
            content = """```json
{
    "found": false,
    "student_info": {}
}
```"""
        
        response = MagicMock()
        response.content = content
        return response
    
    with patch.object(service.llm, 'ainvoke', side_effect=mock_ainvoke):
        result = await service.segment_batch_document(images_data)
        
        # 验证结果
        assert result.total_pages == 40
        assert result.student_count == 20
        assert len(result.page_mappings) == 40
        
        # 验证每个学生有 2 页
        groups = service.group_pages_by_student(result)
        assert len(groups) == 20
        
        for student_key, page_indices in groups.items():
            assert len(page_indices) == 2, f"学生 {student_key} 应该有 2 页"


@pytest.mark.asyncio
async def test_segment_batch_with_unidentified_pages():
    """测试批量分割：包含无法识别的页面"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    # 6 页：学生A(2页) + 未识别(1页) + 学生B(2页) + 未识别(1页)
    images_data = [create_mock_exam_page("", "") for _ in range(6)]
    
    responses = [
        # 学生 A 第一页
        """```json
{
    "found": true,
    "student_info": {
        "name": "学生A",
        "student_id": "2024001",
        "confidence": 0.9,
        "bounding_box": [50, 100, 150, 600]
    }
}
```""",
        # 学生 A 第二页（无信息，但会归属于 A）
        """```json
{"found": false, "student_info": {}}
```""",
        # 未识别页面
        """```json
{"found": false, "student_info": {}}
```""",
        # 学生 B 第一页
        """```json
{
    "found": true,
    "student_info": {
        "name": "学生B",
        "student_id": "2024002",
        "confidence": 0.85,
        "bounding_box": [50, 100, 150, 600]
    }
}
```""",
        # 学生 B 第二页
        """```json
{"found": false, "student_info": {}}
```""",
        # 未识别页面
        """```json
{"found": false, "student_info": {}}
```"""
    ]
    
    call_count = 0
    
    async def mock_ainvoke(messages):
        nonlocal call_count
        response = MagicMock()
        response.content = responses[call_count]
        call_count += 1
        return response
    
    with patch.object(service.llm, 'ainvoke', side_effect=mock_ainvoke):
        result = await service.segment_batch_document(images_data)
        
        assert result.total_pages == 6
        assert result.student_count == 2
        
        # 页面 2 和 5 应该被标记为未识别
        # （因为它们前面没有高置信度的学生信息）
        assert 2 in result.unidentified_pages or len(result.unidentified_pages) >= 1


@pytest.mark.asyncio
async def test_group_pages_by_student():
    """测试按学生分组页面"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    # 创建模拟的批量分割结果
    from src.services.student_identification import PageStudentMapping
    
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
    ]
    
    batch_result = BatchSegmentationResult(
        total_pages=4,
        student_count=2,
        page_mappings=mappings,
        unidentified_pages=[]
    )
    
    groups = service.group_pages_by_student(batch_result)
    
    assert len(groups) == 2
    assert "2024001" in groups
    assert "2024002" in groups
    assert groups["2024001"] == [0, 1]
    assert groups["2024002"] == [2, 3]


@pytest.mark.asyncio
async def test_low_confidence_handling():
    """测试低置信度识别的处理"""
    
    service = StudentIdentificationService(api_key="test-key")
    
    mock_response = MagicMock()
    mock_response.content = """```json
{
    "found": true,
    "student_info": {
        "name": "模糊字迹",
        "student_id": null,
        "confidence": 0.4,
        "bounding_box": [50, 100, 150, 600]
    }
}
```"""
    
    with patch.object(service.llm, 'ainvoke', return_value=mock_response):
        image_data = create_mock_exam_page("模糊", "")
        result = await service.identify_student(image_data, page_index=0)
        
        # 低置信度结果仍然返回，但置信度较低
        assert result.name == "模糊字迹"
        assert result.confidence == 0.4
        assert result.student_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
