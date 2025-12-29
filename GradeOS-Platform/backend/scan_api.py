"""
轻量级扫描提交 API
独立运行，支持 PostgreSQL 存储
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import base64
from pathlib import Path
import random
import os
import json

# PostgreSQL
import psycopg
from psycopg.rows import dict_row

app = FastAPI(title="BookScan API", version="1.0.0")

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/gradeos")

async def get_db_connection():
    """获取数据库连接"""
    try:
        conn = await psycopg.AsyncConnection.connect(
            DATABASE_URL,
            row_factory=dict_row
        )
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

async def init_db():
    """初始化数据库表"""
    conn = await get_db_connection()
    if not conn:
        print("⚠️ 数据库不可用，使用本地存储模式")
        return False
    
    try:
        async with conn.cursor() as cur:
            # 创建扫描提交表
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS scan_submissions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    submission_id VARCHAR(50) UNIQUE NOT NULL,
                    homework_id VARCHAR(100) NOT NULL,
                    student_id VARCHAR(100) NOT NULL,
                    student_name VARCHAR(200),
                    image_count INTEGER DEFAULT 0,
                    file_paths JSONB,
                    status VARCHAR(50) DEFAULT 'uploaded',
                    score DECIMAL(5,2),
                    feedback TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # 创建索引
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_scan_student ON scan_submissions(student_id)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_scan_homework ON scan_submissions(homework_id)
            """)
            
            await conn.commit()
        print("✓ 数据库表初始化成功")
        await conn.close()
        return True
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        await conn.close()
        return False

# 全局变量标记数据库是否可用
DB_AVAILABLE = False

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储路径
UPLOAD_DIR = Path("./storage/scans")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# 数据模型
class ScanSubmissionCreate(BaseModel):
    homework_id: str
    student_id: str
    student_name: str
    images: List[str]  # Base64 图片


class SubmissionResponse(BaseModel):
    submission_id: str
    homework_id: str
    student_id: str
    student_name: str
    submitted_at: str
    status: str
    score: Optional[float]
    feedback: Optional[str]


class HomeworkResponse(BaseModel):
    homework_id: str
    class_id: str
    class_name: Optional[str]
    title: str
    description: str
    deadline: str
    created_at: str


# API 端点
@app.get("/")
async def root():
    return {"message": "BookScan API", "status": "running"}


@app.get("/api/homework/list", response_model=List[HomeworkResponse])
async def get_homework_list(student_id: Optional[str] = None):
    """获取作业列表"""
    return [
        HomeworkResponse(
            homework_id="hw-001",
            class_id="c-001",
            class_name="高等数学",
            title="第三章 - 微分方程",
            description="完成课后习题 1-10",
            deadline="2025-01-05",
            created_at=datetime.now().isoformat()
        ),
        HomeworkResponse(
            homework_id="hw-002",
            class_id="c-001",
            class_name="大学物理",
            title="力学实验报告",
            description="撰写单摆实验报告",
            deadline="2025-01-08",
            created_at=datetime.now().isoformat()
        ),
        HomeworkResponse(
            homework_id="hw-003",
            class_id="c-002",
            class_name="线性代数",
            title="矩阵运算练习",
            description="完成矩阵乘法和求逆练习",
            deadline="2025-01-10",
            created_at=datetime.now().isoformat()
        )
    ]


@app.post("/api/homework/submit-scan", response_model=SubmissionResponse)
async def submit_scan_homework(request: ScanSubmissionCreate):
    """
    提交扫描作业 - 保存到 PostgreSQL
    """
    submission_id = str(uuid.uuid4())[:8]
    
    # 创建目录保存图片
    submission_dir = UPLOAD_DIR / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    saved_count = 0
    
    # 保存图片到文件系统
    for idx, img_data in enumerate(request.images):
        try:
            if ',' in img_data:
                img_data = img_data.split(',')[1]
            
            img_bytes = base64.b64decode(img_data)
            file_path = submission_dir / f"page_{idx + 1}.jpg"
            
            with open(file_path, 'wb') as f:
                f.write(img_bytes)
            
            saved_paths.append(str(file_path))
            saved_count += 1
            print(f"✓ 保存图片: {file_path} ({len(img_bytes)} bytes)")
        except Exception as e:
            print(f"✗ 图片 {idx + 1} 处理失败: {e}")
            raise HTTPException(status_code=400, detail=f"图片 {idx + 1} 处理失败: {str(e)}")
    
    # 模拟 AI 批改
    score = random.randint(78, 98)
    
    feedbacks = [
        "整体答题规范，书写清晰。解题思路正确，计算过程完整。",
        "答案正确，步骤清晰。建议注意单位的书写规范。",
        "解题方法得当，但部分步骤可以更简洁。继续保持！",
        "表现优秀！逻辑清晰，计算准确，格式规范。"
    ]
    feedback = f"AI 批改完成 ({saved_count} 页)：{random.choice(feedbacks)} 得分：{score}/100"
    
    # 保存到 PostgreSQL
    if DB_AVAILABLE:
        try:
            conn = await get_db_connection()
            if conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        INSERT INTO scan_submissions 
                        (submission_id, homework_id, student_id, student_name, image_count, file_paths, status, score, feedback)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        submission_id,
                        request.homework_id,
                        request.student_id,
                        request.student_name,
                        saved_count,
                        json.dumps(saved_paths),
                        'graded',
                        score,
                        feedback
                    ))
                    await conn.commit()
                await conn.close()
                print(f"✓ 已保存到 PostgreSQL: {submission_id}")
        except Exception as e:
            print(f"⚠️ PostgreSQL 保存失败: {e}")
    
    print(f"✓ 提交成功: {submission_id}, {saved_count} 张图片, 得分: {score}")
    
    return SubmissionResponse(
        submission_id=submission_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        submitted_at=datetime.now().isoformat(),
        status="graded",
        score=score,
        feedback=feedback
    )


@app.get("/api/submissions/history")
async def get_submission_history(student_id: str):
    """获取学生提交历史"""
    if not DB_AVAILABLE:
        return {"submissions": [], "message": "数据库不可用"}
    
    try:
        conn = await get_db_connection()
        if conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT submission_id, homework_id, student_name, image_count, 
                           status, score, feedback, created_at
                    FROM scan_submissions 
                    WHERE student_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 20
                """, (student_id,))
                rows = await cur.fetchall()
            await conn.close()
            return {"submissions": rows}
    except Exception as e:
        return {"submissions": [], "error": str(e)}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    import asyncio
    
    async def startup():
        global DB_AVAILABLE
        print("🚀 启动 BookScan API 服务...")
        print("📁 图片存储路径:", UPLOAD_DIR.absolute())
        print("🔗 数据库:", DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL)
        
        # 初始化数据库
        DB_AVAILABLE = await init_db()
        if DB_AVAILABLE:
            print("✓ PostgreSQL 已连接")
        else:
            print("⚠️ PostgreSQL 不可用，仅使用本地文件存储")
    
    asyncio.run(startup())
    uvicorn.run(app, host="0.0.0.0", port=8001)
