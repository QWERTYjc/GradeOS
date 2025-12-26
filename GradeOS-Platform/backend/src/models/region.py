"""页面区域相关数据模型"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class BoundingBox(BaseModel):
    """边界框坐标"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ymin": 100,
                "xmin": 50,
                "ymax": 300,
                "xmax": 400
            }
        }
    )
    
    ymin: int = Field(..., description="最小 Y 坐标（像素）", ge=0)
    xmin: int = Field(..., description="最小 X 坐标（像素）", ge=0)
    ymax: int = Field(..., description="最大 Y 坐标（像素）", ge=0)
    xmax: int = Field(..., description="最大 X 坐标（像素）", ge=0)

    @field_validator('ymax')
    @classmethod
    def validate_ymax(cls, v: int, info) -> int:
        """验证 ymax > ymin"""
        if 'ymin' in info.data and v <= info.data['ymin']:
            raise ValueError('ymax 必须大于 ymin')
        return v

    @field_validator('xmax')
    @classmethod
    def validate_xmax(cls, v: int, info) -> int:
        """验证 xmax > xmin"""
        if 'xmin' in info.data and v <= info.data['xmin']:
            raise ValueError('xmax 必须大于 xmin')
        return v


class QuestionRegion(BaseModel):
    """题目区域"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "q1",
                "page_index": 0,
                "bounding_box": {
                    "ymin": 100,
                    "xmin": 50,
                    "ymax": 300,
                    "xmax": 400
                },
                "image_data": "base64_encoded_image"
            }
        }
    )
    
    question_id: str = Field(..., description="题目 ID")
    page_index: int = Field(..., description="页面索引", ge=0)
    bounding_box: BoundingBox = Field(..., description="边界框坐标")
    image_data: Optional[str] = Field(None, description="裁剪后的图像数据（Base64）")


class SegmentationResult(BaseModel):
    """文档分割结果"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "submission_id": "sub_001",
                "total_pages": 2,
                "regions": [
                    {
                        "question_id": "q1",
                        "page_index": 0,
                        "bounding_box": {
                            "ymin": 100,
                            "xmin": 50,
                            "ymax": 300,
                            "xmax": 400
                        }
                    }
                ]
            }
        }
    )
    
    submission_id: str = Field(..., description="提交 ID")
    total_pages: int = Field(..., description="总页数", ge=1)
    regions: List[QuestionRegion] = Field(..., description="识别的题目区域列表")
