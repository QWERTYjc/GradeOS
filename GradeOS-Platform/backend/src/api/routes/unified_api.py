"""
GradeOS 统一 API 路由
整合所有子系统的 API 接口
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid
import base64
import os
from pathlib import Path

router = APIRouter()

# 存储路径配置
UPLOAD_DIR = Path("./storage/scans")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ============ 数据模型 ============

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    username: str
    name: str
    user_type: str  # student/teacher/admin
    class_ids: List[str] = []

class ClassCreate(BaseModel):
    name: str
    teacher_id: str

class ClassResponse(BaseModel):
    class_id: str
    class_name: str
    teacher_id: str
    invite_code: str
    student_count: int

class JoinClassRequest(BaseModel):
    code: str
    student_id: str

class HomeworkCreate(BaseModel):
    class_id: str
    title: str
    description: str
    deadline: str

class HomeworkResponse(BaseModel):
    homework_id: str
    class_id: str
    class_name: Optional[str]
    title: str
    description: str
    deadline: str
    created_at: str

class SubmissionCreate(BaseModel):
    homework_id: str
    student_id: str
    student_name: str
    content: str

class ScanSubmissionCreate(BaseModel):
    """扫描提交请求"""
    homework_id: str
    student_id: str
    student_name: str
    images: List[str]  # Base64 编码的图片列表

class SubmissionResponse(BaseModel):
    submission_id: str
    homework_id: str
    student_id: str
    student_name: str
    submitted_at: str
    status: str
    score: Optional[float]
    feedback: Optional[str]

class ErrorAnalysisRequest(BaseModel):
    subject: str
    question: str
    student_answer: str
    student_id: Optional[str] = None

class ErrorAnalysisResponse(BaseModel):
    analysis_id: str
    error_type: str
    error_severity: str
    root_cause: str
    knowledge_gaps: List[dict]
    detailed_analysis: dict
    recommendations: dict

class DiagnosisReportResponse(BaseModel):
    student_id: str
    report_period: str
    overall_assessment: dict
    progress_trend: List[dict]
    knowledge_map: List[dict]
    error_patterns: dict
    personalized_insights: List[str]


# ============ 认证接口 ============

@router.post("/auth/login", response_model=UserResponse, tags=["认证"])
async def login(request: LoginRequest):
    """用户登录"""
    # Mock 实现
    mock_users = {
        "teacher": {"user_id": "t-001", "name": "Demo Teacher", "user_type": "teacher", "class_ids": ["c-001"]},
        "student": {"user_id": "s-001", "name": "Demo Student", "user_type": "student", "class_ids": ["c-001"]},
    }
    
    if request.username in mock_users and request.password == "123456":
        user = mock_users[request.username]
        return UserResponse(username=request.username, **user)
    
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/user/info", response_model=UserResponse, tags=["认证"])
async def get_user_info(user_id: str):
    """获取用户信息"""
    return UserResponse(
        user_id=user_id,
        username="demo",
        name="Demo User",
        user_type="student",
        class_ids=["c-001"]
    )


# ============ 班级管理接口 ============

@router.get("/class/my", response_model=List[ClassResponse], tags=["班级管理"])
async def get_my_classes(student_id: str):
    """获取学生加入的班级"""
    return [
        ClassResponse(
            class_id="c-001",
            class_name="Advanced Physics 2024",
            teacher_id="t-001",
            invite_code="PHY24A",
            student_count=32
        )
    ]


@router.post("/class/join", tags=["班级管理"])
async def join_class(request: JoinClassRequest):
    """学生加入班级"""
    return {
        "success": True,
        "class": {
            "id": "c-001",
            "name": "Advanced Physics 2024"
        }
    }


@router.get("/teacher/classes", response_model=List[ClassResponse], tags=["班级管理"])
async def get_teacher_classes(teacher_id: str):
    """获取教师的班级列表"""
    return [
        ClassResponse(
            class_id="c-001",
            class_name="Advanced Physics 2024",
            teacher_id=teacher_id,
            invite_code="PHY24A",
            student_count=32
        ),
        ClassResponse(
            class_id="c-002",
            class_name="Mathematics Grade 11",
            teacher_id=teacher_id,
            invite_code="MTH11B",
            student_count=28
        )
    ]


@router.post("/teacher/classes", response_model=ClassResponse, tags=["班级管理"])
async def create_class(request: ClassCreate):
    """创建班级"""
    import random
    import string
    invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    return ClassResponse(
        class_id=str(uuid.uuid4())[:8],
        class_name=request.name,
        teacher_id=request.teacher_id,
        invite_code=invite_code,
        student_count=0
    )


@router.get("/class/students", tags=["班级管理"])
async def get_class_students(class_id: str):
    """获取班级学生列表"""
    return [
        {"id": "s-001", "name": "Alice Chen", "username": "alice"},
        {"id": "s-002", "name": "Bob Wang", "username": "bob"},
        {"id": "s-003", "name": "Carol Liu", "username": "carol"},
    ]


# ============ 作业管理接口 ============

@router.get("/homework/list", response_model=List[HomeworkResponse], tags=["作业管理"])
async def get_homework_list(class_id: Optional[str] = None, student_id: Optional[str] = None):
    """获取作业列表"""
    return [
        HomeworkResponse(
            homework_id="hw-001",
            class_id="c-001",
            class_name="Advanced Physics 2024",
            title="Newton's Laws Problem Set",
            description="Complete problems 1-10 from Chapter 5",
            deadline="2024-12-30",
            created_at=datetime.now().isoformat()
        ),
        HomeworkResponse(
            homework_id="hw-002",
            class_id="c-001",
            class_name="Advanced Physics 2024",
            title="Energy Conservation Quiz",
            description="Online quiz covering kinetic and potential energy",
            deadline="2024-12-28",
            created_at=datetime.now().isoformat()
        )
    ]


@router.get("/homework/detail/{homework_id}", response_model=HomeworkResponse, tags=["作业管理"])
async def get_homework_detail(homework_id: str):
    """获取作业详情"""
    return HomeworkResponse(
        homework_id=homework_id,
        class_id="c-001",
        class_name="Advanced Physics 2024",
        title="Newton's Laws Problem Set",
        description="Complete problems 1-10 from Chapter 5",
        deadline="2024-12-30",
        created_at=datetime.now().isoformat()
    )


@router.post("/homework/create", response_model=HomeworkResponse, tags=["作业管理"])
async def create_homework(request: HomeworkCreate):
    """创建作业"""
    return HomeworkResponse(
        homework_id=str(uuid.uuid4())[:8],
        class_id=request.class_id,
        class_name="Class Name",
        title=request.title,
        description=request.description,
        deadline=request.deadline,
        created_at=datetime.now().isoformat()
    )


@router.post("/homework/submit", response_model=SubmissionResponse, tags=["作业管理"])
async def submit_homework(request: SubmissionCreate):
    """提交作业（文本）"""
    # 模拟 AI 批改
    import random
    score = random.randint(75, 98)
    
    return SubmissionResponse(
        submission_id=str(uuid.uuid4())[:8],
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        submitted_at=datetime.now().isoformat(),
        status="graded",
        score=score,
        feedback=f"AI Analysis: Good understanding of core concepts. Score: {score}/100"
    )


@router.post("/homework/submit-scan", response_model=SubmissionResponse, tags=["作业管理"])
async def submit_scan_homework(request: ScanSubmissionCreate):
    """
    提交扫描作业（图片）
    
    接收 Base64 编码的图片列表，保存到本地存储，并触发 AI 批改
    """
    submission_id = str(uuid.uuid4())[:8]
    
    # 创建提交目录
    submission_dir = UPLOAD_DIR / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    
    # 保存图片
    for idx, img_data in enumerate(request.images):
        try:
            # 移除 data:image/xxx;base64, 前缀
            if ',' in img_data:
                img_data = img_data.split(',')[1]
            
            # 解码并保存
            img_bytes = base64.b64decode(img_data)
            file_path = submission_dir / f"page_{idx + 1}.jpg"
            
            with open(file_path, 'wb') as f:
                f.write(img_bytes)
            
            saved_paths.append(str(file_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"图片 {idx + 1} 处理失败: {str(e)}")
    
    # 模拟 AI 批改（实际应调用批改服务）
    import random
    score = random.randint(75, 98)
    
    feedback_templates = [
        "整体答题规范，书写清晰。",
        "解题思路正确，计算过程完整。",
        "部分步骤可以更简洁，建议复习相关公式。",
        "答案正确，但注意单位的书写规范。"
    ]
    
    return SubmissionResponse(
        submission_id=submission_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        submitted_at=datetime.now().isoformat(),
        status="graded",
        score=score,
        feedback=f"AI 批改完成 ({len(request.images)} 页)：{random.choice(feedback_templates)} 得分：{score}/100"
    )


@router.get("/homework/submissions", response_model=List[SubmissionResponse], tags=["作业管理"])
async def get_submissions(homework_id: str):
    """获取作业提交列表"""
    return [
        SubmissionResponse(
            submission_id="sub-001",
            homework_id=homework_id,
            student_id="s-001",
            student_name="Alice Chen",
            submitted_at=datetime.now().isoformat(),
            status="graded",
            score=92,
            feedback="Excellent work! Clear understanding of concepts."
        ),
        SubmissionResponse(
            submission_id="sub-002",
            homework_id=homework_id,
            student_id="s-002",
            student_name="Bob Wang",
            submitted_at=datetime.now().isoformat(),
            status="graded",
            score=78,
            feedback="Good effort. Review section 5.3 for improvement."
        )
    ]


# ============ 错题分析接口 (IntelliLearn) ============

@router.post("/v1/analysis/submit-error", response_model=ErrorAnalysisResponse, tags=["错题分析"])
async def analyze_error(request: ErrorAnalysisRequest):
    """提交错题进行 AI 分析"""
    analysis_id = str(uuid.uuid4())[:8]
    
    # 模拟 AI 分析结果
    return ErrorAnalysisResponse(
        analysis_id=analysis_id,
        error_type="概念错误",
        error_severity="medium",
        root_cause="对二次函数顶点式的理解存在偏差，特别是在符号判断方面",
        knowledge_gaps=[
            {"knowledge_point": "二次函数顶点式", "mastery_level": 0.65, "confidence": 0.85},
            {"knowledge_point": "配方法", "mastery_level": 0.72, "confidence": 0.90}
        ],
        detailed_analysis={
            "step_by_step_correction": [
                "首先确认二次函数的一般形式 y=ax²+bx+c",
                "使用配方法将其转换为顶点式 y=a(x-h)²+k",
                "注意 h 的符号：当 h>0 时，图像向右平移"
            ],
            "common_mistakes": "忽略 a 的正负影响开口方向",
            "correct_solution": "正确解法详细步骤..."
        },
        recommendations={
            "immediate_actions": ["复习配方法基础", "练习顶点式转换"],
            "practice_exercises": ["练习题1", "练习题2"],
            "learning_path": {"short_term": ["本周完成顶点式专项"], "long_term": ["下月掌握二次函数全部内容"]}
        }
    )


@router.get("/v1/diagnosis/report/{student_id}", response_model=DiagnosisReportResponse, tags=["错题分析"])
async def get_diagnosis_report(student_id: str):
    """获取学生诊断报告"""
    return DiagnosisReportResponse(
        student_id=student_id,
        report_period="2024年12月",
        overall_assessment={
            "mastery_score": 0.785,
            "improvement_rate": 0.045,
            "consistency_score": 82
        },
        progress_trend=[
            {"date": "12-01", "score": 0.72, "average": 0.70},
            {"date": "12-08", "score": 0.75, "average": 0.71},
            {"date": "12-15", "score": 0.78, "average": 0.72},
            {"date": "12-22", "score": 0.79, "average": 0.73}
        ],
        knowledge_map=[
            {"knowledge_area": "二次函数", "mastery_level": 0.75, "weak_points": ["顶点式"], "strengths": ["图像绘制"]},
            {"knowledge_area": "不等式", "mastery_level": 0.82, "weak_points": ["边界条件"], "strengths": ["基本运算"]},
            {"knowledge_area": "解析几何", "mastery_level": 0.68, "weak_points": ["圆与直线"], "strengths": ["直线方程"]}
        ],
        error_patterns={
            "most_common_error_types": [
                {"type": "概念错误", "count": 8, "percentage": 40},
                {"type": "计算错误", "count": 5, "percentage": 25},
                {"type": "审题错误", "count": 4, "percentage": 20}
            ]
        },
        personalized_insights=[
            "你在代数运算方面表现稳定，建议继续保持",
            "几何直觉需要加强，建议多做图形变换练习",
            "审题时注意关键条件的提取，避免遗漏"
        ]
    )


@router.get("/v1/class/wrong-problems", tags=["错题分析"])
async def get_class_wrong_problems(class_id: Optional[str] = None):
    """获取班级高频错题"""
    return {
        "problems": [
            {"id": "p-001", "question": "已知二次函数 y=x²-4x+3，求其顶点坐标", "errorRate": "32%", "tags": ["二次函数", "顶点式"]},
            {"id": "p-002", "question": "解不等式 2x-1 > 3x+2", "errorRate": "28%", "tags": ["不等式", "变号"]},
            {"id": "p-003", "question": "圆 x²+y²=4 与直线 y=x+k 相切，求 k 的值", "errorRate": "45%", "tags": ["圆", "切线"]}
        ]
    }


# ============ 统计接口 ============

@router.get("/teacher/statistics/class/{class_id}", tags=["统计分析"])
async def get_class_statistics(class_id: str, homework_id: Optional[str] = None):
    """获取班级统计数据"""
    return {
        "class_id": class_id,
        "total_students": 32,
        "submitted_count": 28,
        "graded_count": 28,
        "average_score": 82.5,
        "max_score": 98,
        "min_score": 65,
        "pass_rate": 0.875,
        "score_distribution": {
            "90-100": 8,
            "80-89": 12,
            "70-79": 5,
            "60-69": 3,
            "0-59": 0
        }
    }


@router.post("/teacher/statistics/merge", tags=["统计分析"])
async def merge_statistics(class_id: str, external_data: Optional[str] = None):
    """合并外部成绩数据"""
    return {
        "students": [
            {"id": "s-001", "name": "Alice Chen", "scores": {"Homework 1": 92, "Homework 2": 88, "Midterm": 85}},
            {"id": "s-002", "name": "Bob Wang", "scores": {"Homework 1": 78, "Homework 2": 82, "Midterm": 75}},
        ],
        "internalAssignments": ["Homework 1", "Homework 2"],
        "externalAssignments": ["Midterm"]
    }
