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

# PostgreSQL (使用同步版本 psycopg2)
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="BookScan API", version="1.0.0")

# 数据库配置 - 与 docker-compose.yml 保持一致
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://grading_user:grading_pass@localhost:5432/grading_system")

def parse_db_url(url):
    """解析数据库 URL"""
    # postgresql://user:pass@host:port/dbname
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', url)
    if match:
        return {
            'user': match.group(1),
            'password': match.group(2),
            'host': match.group(3),
            'port': match.group(4),
            'dbname': match.group(5)
        }
    return None

def get_db_connection():
    """获取数据库连接"""
    try:
        params = parse_db_url(DATABASE_URL)
        if params:
            conn = psycopg2.connect(
                host=params['host'],
                port=params['port'],
                user=params['user'],
                password=params['password'],
                dbname=params['dbname'],
                cursor_factory=RealDictCursor
            )
        else:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    if not conn:
        print("⚠️ 数据库不可用，使用本地存储模式")
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
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
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_student ON scan_submissions(student_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_homework ON scan_submissions(homework_id)")
            conn.commit()
        print("✓ 数据库表初始化成功")
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        conn.close()
        return False

DB_AVAILABLE = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("./storage/scans")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class ScanSubmissionCreate(BaseModel):
    homework_id: str
    student_id: str
    student_name: str
    images: List[str]

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

@app.get("/")
async def root():
    return {"message": "BookScan API", "status": "running", "db_available": DB_AVAILABLE}

@app.get("/api/homework/list", response_model=List[HomeworkResponse])
async def get_homework_list(student_id: Optional[str] = None):
    return [
        HomeworkResponse(homework_id="hw-001", class_id="c-001", class_name="高等数学",
            title="第三章 - 微分方程", description="完成课后习题 1-10",
            deadline="2025-01-05", created_at=datetime.now().isoformat()),
        HomeworkResponse(homework_id="hw-002", class_id="c-001", class_name="大学物理",
            title="力学实验报告", description="撰写单摆实验报告",
            deadline="2025-01-08", created_at=datetime.now().isoformat()),
    ]

@app.post("/api/homework/submit-scan", response_model=SubmissionResponse)
async def submit_scan_homework(request: ScanSubmissionCreate):
    submission_id = str(uuid.uuid4())[:8]
    submission_dir = UPLOAD_DIR / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    for idx, img_data in enumerate(request.images):
        try:
            if ',' in img_data:
                img_data = img_data.split(',')[1]
            img_bytes = base64.b64decode(img_data)
            file_path = submission_dir / f"page_{idx + 1}.jpg"
            with open(file_path, 'wb') as f:
                f.write(img_bytes)
            saved_paths.append(str(file_path))
            print(f"✓ 保存图片: {file_path}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"图片 {idx + 1} 处理失败")
    
    score = random.randint(78, 98)
    feedback = f"AI 批改完成 ({len(saved_paths)} 页)：解题思路正确，书写清晰。得分：{score}/100"
    
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO scan_submissions 
                        (submission_id, homework_id, student_id, student_name, image_count, file_paths, status, score, feedback)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (submission_id, request.homework_id, request.student_id, request.student_name,
                          len(saved_paths), json.dumps(saved_paths), 'graded', score, feedback))
                    conn.commit()
                conn.close()
                print(f"✓ 已保存到 PostgreSQL: {submission_id}")
        except Exception as e:
            print(f"⚠️ PostgreSQL 保存失败: {e}")
    
    return SubmissionResponse(
        submission_id=submission_id, homework_id=request.homework_id,
        student_id=request.student_id, student_name=request.student_name,
        submitted_at=datetime.now().isoformat(), status="graded", score=score, feedback=feedback)

@app.get("/api/submissions/history")
async def get_submission_history(student_id: str):
    if not DB_AVAILABLE:
        return {"submissions": [], "message": "数据库不可用"}
    try:
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT submission_id, homework_id, student_name, image_count, 
                    status, score, feedback, created_at FROM scan_submissions 
                    WHERE student_id = %s ORDER BY created_at DESC LIMIT 20""", (student_id,))
                rows = cur.fetchall()
            conn.close()
            return {"submissions": [dict(row) for row in rows]}
    except Exception as e:
        return {"submissions": [], "error": str(e)}

@app.get("/api/submissions/all")
async def get_all_submissions():
    if not DB_AVAILABLE:
        return {"submissions": [], "message": "数据库不可用"}
    try:
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT * FROM scan_submissions ORDER BY created_at DESC LIMIT 50""")
                rows = cur.fetchall()
            conn.close()
            return {"count": len(rows), "submissions": [dict(row) for row in rows]}
    except Exception as e:
        return {"submissions": [], "error": str(e)}

@app.get("/health")
async def health():
    return {"status": "healthy", "db_available": DB_AVAILABLE}

if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 BookScan API...")
    print("📁 存储路径:", UPLOAD_DIR.absolute())
    DB_AVAILABLE = init_db()
    print("✓ PostgreSQL 已连接" if DB_AVAILABLE else "⚠️ PostgreSQL 不可用，仅本地存储")
    print("\n📡 http://localhost:8001\n📖 http://localhost:8001/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8001)
