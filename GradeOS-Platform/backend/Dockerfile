# GradeOS Backend Dockerfile
# 使用包含构建工具的基础镜像以避免 Railway 内存限制问题

FROM python:3.11-slim-bookworm

WORKDIR /app

# 安装系统依赖 - 单个 RUN 命令减少层数和内存使用
# 使用 --no-install-recommends 减少安装包大小
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

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
