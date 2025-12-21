# Tech Stack

## 核心框架

- **Python 3.11+**：主要开发语言
- **FastAPI**：API 网关和 HTTP 服务
- **Temporal**：分布式工作流编排引擎
- **LangGraph**：智能体推理框架（图结构循环推理）
- **LangChain**：LLM 集成层

## AI 模型

- **Gemini 2.5 Flash** (`gemini-2.5-flash`)：默认使用的稳定版模型，用于页面布局分析、题目分割、深度推理与评分

### 可用模型

| 模型名称 | 模型 ID | 说明 |
|---------|---------|------|
| Gemini 3 Flash Preview | `gemini-3-flash-preview` | 最新预览版，增强能力 |
| Gemini 2.5 Flash | `gemini-2.5-flash` | 稳定版，推荐生产环境 |
| Gemini 2.5 Flash Preview | `gemini-2.5-flash-preview-09-2025` | 预览版，早期访问新功能 |
| Gemini 2.5 Flash Lite | `gemini-2.5-flash-lite` | 轻量级，适合简单任务 |
| Gemini 2.0 Flash | `gemini-2.0-flash` | 旧版本，仍可使用 |

### 模型配置

模型配置集中在 `src/config/models.py`，支持通过环境变量覆盖：

- `GEMINI_MODEL`: 默认模型（用于批改、评分标准解析等）
- `GEMINI_LITE_MODEL`: 轻量模型（用于学生识别、布局分析等）
- `GEMINI_CACHE_MODEL`: 缓存模型（用于 Context Caching）

切换模型示例：
```bash
# 使用 Gemini 3 Flash Preview
export GEMINI_MODEL=gemini-3-flash-preview

# 使用 Gemini 2.5 Flash（默认）
export GEMINI_MODEL=gemini-2.5-flash
```

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
