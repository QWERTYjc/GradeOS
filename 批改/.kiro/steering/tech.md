# Tech Stack

## 核心框架

- **Python 3.11+**：主要开发语言
- **FastAPI**：API 网关和 HTTP 服务
- **LangGraph**：智能体推理框架（图结构循环推理）+ 工作流编排引擎
- **LangChain**：LLM 集成层

## AI 模型

- **Gemini 3 Flash Preview** (`gemini-3-flash-preview`)：统一使用的模型，用于所有 AI 任务（页面布局分析、题目分割、深度推理与评分）

### 模型配置

模型配置集中在 `src/config/models.py`，所有任务统一使用 `gemini-3-flash-preview`

## 数据存储

- **PostgreSQL**：主数据库，使用 JSONB 存储非结构化批改结果和 LangGraph Checkpoint
- **Redis**：语义缓存、分布式锁、API 限流

## 基础设施

- **Kubernetes**：容器编排
- **KEDA**：基于队列深度的自动扩缩容
- **S3/MinIO**：对象存储（试卷图像）

## 关键依赖

```
langgraph
langgraph-checkpoint-postgres
langchain-google-genai
fastapi
pydantic
psycopg[pool]
asyncpg
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

# 启动 LangGraph Worker
python -m src.workers.langgraph_worker

# 运行测试
pytest tests/ -v

# 运行属性测试
pytest tests/ -v --hypothesis-show-statistics

# 数据库迁移
alembic upgrade head
```

## 编排器配置

通过环境变量 `ORCHESTRATOR_MODE` 切换编排器：

```bash
# 使用 LangGraph（推荐）
export ORCHESTRATOR_MODE=langgraph

# 自动选择（优先 LangGraph）
export ORCHESTRATOR_MODE=auto
```
