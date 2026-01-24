# GradeOS Backend Dockerfile
# 使用包含构建工具的完整镜像，避免 apt-get 安装问题

FROM python:3.11-bookworm

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖 - 使用 --no-cache-dir 减少镜像大小
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
