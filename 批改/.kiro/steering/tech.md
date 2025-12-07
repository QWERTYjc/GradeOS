# Tech Stack

## 核心框架

- **Python 3.11+**：主要开发语言
- **FastAPI**：API 网关和 HTTP 服务
- **Temporal**：分布式工作流编排引擎
- **LangGraph**：智能体推理框架（图结构循环推理）
- **LangChain**：LLM 集成层

## AI 模型

- **Gemini 2.5 Flash Lite**：页面布局分析与题目分割（高吞吐、低成本）
- **Gemini 3.0 Pro**：深度推理与评分（Agentic 能力）

## 数据存储

- **PostgreSQL**：主数据库，使用 JSONB 存储非结构化批改结果和 LangGraph Checkpoint
- **Redis**：语义缓存、分布式锁、API 限流

## 基础设施

- **Kubernetes**：容器编排
- **KEDA**：基于 Temporal 队列深度的自动扩缩容
- **S3/MinIO**：对象存储（试卷图像）

## 关键依赖

```
temporalio
langgraph
langchain-google-genai
fastapi
pydantic
psycopg[pool]
redis
pdf2image
imagehash
```

## 常用命令

```bash
# 安装依赖
uv sync

# 运行 API 服务
uvicorn src.api.main:app --reload

# 启动 Temporal Worker（编排）
python -m src.workers.orchestration_worker

# 启动 Temporal Worker（认知计算）
python -m src.workers.cognitive_worker

# 运行测试
pytest tests/ -v

# 运行属性测试
pytest tests/ -v --hypothesis-show-statistics

# 数据库迁移
alembic upgrade head
```
