# AI 批改智能体工作流系统

生产级纯视觉（Vision-Native）AI 批改系统，专为教育技术（EdTech）领域设计。

## 核心特性

- **纯视觉优先**：摒弃传统 OCR，直接利用 VLM 进行端到端语义理解
- **持久化执行**：基于 Temporal 工作流引擎，确保长周期批改任务的可靠性
- **智能体推理**：通过 LangGraph 实现循环推理和自我反思
- **人机协作**：支持低置信度结果的人工审核介入

## 技术栈

- **Python 3.11+**
- **FastAPI** - API 网关
- **Temporal** - 分布式工作流编排
- **LangGraph** - 智能体推理框架
- **Gemini 2.5 Flash Lite** - 页面布局分析
- **Gemini 3.0 Pro** - 深度推理与评分
- **PostgreSQL** - 主数据库（JSONB）
- **Redis** - 缓存与限流

## 快速开始

### 安装依赖

```bash
# 使用 uv 安装依赖
uv sync

# 或使用 pip
pip install -e .
```

### 运行服务

```bash
# 启动 API 服务
uvicorn src.api.main:app --reload

# 启动 Temporal Worker（编排）
python -m src.workers.orchestration_worker

# 启动 Temporal Worker（认知计算）
python -m src.workers.cognitive_worker
```

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行属性测试
pytest tests/property/ -v --hypothesis-show-statistics

# 运行单元测试
pytest tests/unit/ -v
```

### 数据库迁移

```bash
# 运行迁移
alembic upgrade head

# 创建新迁移
alembic revision --autogenerate -m "描述"
```

## 项目结构

```
src/
├── api/                    # FastAPI 应用
├── models/                 # Pydantic 数据模型
├── services/               # 业务服务层
├── agents/                 # LangGraph 智能体
├── workflows/              # Temporal 工作流
├── activities/             # Temporal Activities
├── workers/                # Temporal Worker 入口
├── repositories/           # 数据访问层
└── utils/                  # 工具函数
```

## 文档

详细文档请参考 `.kiro/specs/ai-grading-agent/` 目录：

- `requirements.md` - 需求规范
- `design.md` - 设计文档
- `tasks.md` - 实现计划

## 许可证

MIT
