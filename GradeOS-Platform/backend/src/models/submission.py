"""提交相关数据模型"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from .enums import FileType, SubmissionStatus


class SubmissionRequest(BaseModel):
    """提交请求"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exam_id": "exam_001",
                "student_id": "student_001",
                "file_type": "pdf",
                "file_data": b"base64_encoded_data",
            }
        }
    )

    exam_id: str = Field(..., description="考试 ID")
    student_id: str = Field(..., description="学生 ID")
    file_type: FileType = Field(..., description="文件类型")
    file_data: bytes = Field(..., description="文件数据（Base64 编码）")


class SubmissionResponse(BaseModel):
    """提交响应"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "submission_id": "sub_001",
                "status": "UPLOADED",
                "estimated_completion_time": 120,
            }
        }
    )

    submission_id: str = Field(..., description="提交 ID")
    status: SubmissionStatus = Field(..., description="提交状态")
    estimated_completion_time: int = Field(..., description="预计完成时间（秒）")


class SubmissionStatusResponse(BaseModel):
    """提交状态查询响应"""

    submission_id: str = Field(..., description="提交 ID")
    exam_id: str = Field(..., description="考试 ID")
    student_id: str = Field(..., description="学生 ID")
    status: SubmissionStatus = Field(..., description="当前状态")
    total_score: Optional[float] = Field(None, description="总分")
    max_total_score: Optional[float] = Field(None, description="满分")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
