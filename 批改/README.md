# AI 批改系统

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**生产级纯视觉（Vision-Native）自动评估引擎**，专为教育技术（EdTech）领域设计。

## 核心特性

| 特性 | 描述 |
|------|------|
| 🎯 纯视觉批改 | 摒弃 OCR，直接利用多模态大模型（VLM）进行端到端语义理解 |
| 🧠 动态智能体 | SupervisorAgent 根据题型动态派生专业批改智能体 |
| ⚡ 持久化执行 | Temporal 工作流引擎确保长周期任务可靠性 |
| 👥 人机协作 | 低置信度结果自动触发人工审核介入（Human-in-the-Loop） |
| 💰 成本优化 | Context Caching 技术节省约 25% Token 成本 |
| 📊 批量处理 | 多学生合卷上传，自动识别学生边界 |

## 技术栈

### 后端

- **Python 3.11+** - 主语言
- **FastAPI** - API 网关 + WebSocket 实时推送
- **Temporal** - 分布式工作流编排
- **LangGraph** - 智能体推理框架（图结构循环推理）
- **PostgreSQL** - 主数据库（使用 JSONB 存储）
- **Redis** - 语义缓存 / 分布式锁 / API 限流
- **Gemini 3.0 Flash** - 统一用于页面布局分析、深度推理与评分（高吞吐、低成本、Agentic）

### 前端

- **Next.js 16** - React 全栈框架
- **React 19** - UI 库
- **Three.js + R3F** - 3D 背景渲染
- **ReactFlow** - 工作流可视化
- **Zustand** - 状态管理
- **Tailwind CSS 4** - 样式

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- Gemini API Key

### 安装

```bash
# 后端依赖
uv sync

# 前端依赖
cd frontend && npm install

# 配置环境变量
cp .env.example .env
# 编辑 .env 设置 GEMINI_API_KEY, DATABASE_URL, REDIS_URL

# 数据库迁移
alembic upgrade head
```

### 启动服务

```bash
# API 服务
uvicorn src.api.main:app --reload --port 8001

# Temporal Workers
python -m src.workers.orchestration_worker
python -m src.workers.cognitive_worker

# 前端开发
cd frontend && npm run dev
```

### 访问

- **API 文档**: http://localhost:8001/docs
- **前端界面**: http://localhost:3000

## 项目结构

```
.
├── src/                        # 后端源码
│   ├── api/                    # FastAPI 应用
│   │   ├── main.py             # 入口
│   │   └── routes/             # 路由 (batch/submissions/rubrics/reviews)
│   ├── agents/                 # LangGraph 智能体
│   │   ├── supervisor.py       # SupervisorAgent 总控
│   │   ├── pool.py             # AgentPool 智能体池
│   │   └── specialized/        # 专业智能体 (objective/stepwise/essay)
│   ├── services/               # 业务服务层 (21个)
│   ├── workflows/              # Temporal 工作流
│   └── workers/                # Worker 入口
│
├── frontend/                   # 前端应用 (Next.js)
│   └── src/
│       ├── app/                # 页面 (Landing + Console)
│       └── components/         # 组件 (WorkflowGraph/NodeInspector)
│
├── tests/                      # 测试
├── docs/                       # 文档
├── k8s/                        # Kubernetes 配置
└── alembic/                    # 数据库迁移
```

## API 概览

| 端点 | 方法 | 描述 |
|------|------|------|
| `/batch/grade-cached` | POST | 批量批改（Context Caching 优化） |
| `/batch/ws/{batch_id}` | WS | 实时进度推送 |
| `/api/v1/submissions` | POST | 单份提交 |
| `/api/v1/submissions/{id}` | GET | 提交状态 |
| `/api/v1/reviews/{id}/signal` | POST | 审核信号 |
| `/health` | GET | 健康检查 |

### 批改示例

```bash
curl -X POST "http://localhost:8001/batch/grade-cached" \
  -F "rubric_file=@评分标准.pdf" \
  -F "answer_file=@学生作答.pdf" \
  -F "api_key=YOUR_GEMINI_API_KEY"
```

## 部署

### Docker

```bash
docker-compose up -d
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

详细部署说明请参考 [DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 属性测试
pytest tests/property/ -v --hypothesis-show-statistics

# 覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

## 文档

- [完整 Wiki](docs/WIKI.md) - 详细架构和模块说明
- [快速开始](docs/QUICKSTART.md)
- [API 参考](docs/API_REFERENCE.md)
- [批量 API 指南](docs/BATCH_API_GUIDE.md)
- [部署指南](docs/DEPLOYMENT.md)
- [Token 优化指南](docs/TOKEN_OPTIMIZATION_COMPLETE.md)

## 性能指标

| 指标 | 目标 | 实测 |
|------|------|------|
| 单题批改延迟 | < 30s | 15-20s |
| 评分准确度 | Pearson > 0.9 | ✅ |
| Token 成本优化 | 25% | ✅ |

## 许可证

MIT License

## 联系方式

- 问题反馈：[Issues](https://github.com/your-org/ai-grading-system/issues)
