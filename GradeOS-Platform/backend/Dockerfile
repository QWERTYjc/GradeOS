# GradeOS Backend Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖 - 分步安装以减少内存峰值
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini .

# 创建上传目录
RUN mkdir -p /app/uploads

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 启动脚本：先运行迁移，再启动服务
CMD alembic upgrade head && uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8001}
