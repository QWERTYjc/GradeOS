# AI 批改系统

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

生产级纯视觉（Vision-Native）自动评估引擎，专为教育技术（EdTech）领域设计。

## 核心特性

- **🎯 纯视觉批改**：摒弃 OCR，直接利用多模态大模型（VLM）进行端到端语义理解
- **🧠 深度推理**：基于 LangGraph 智能体实现循环推理和自我反思
- **⚡ 持久化执行**：Temporal 工作流引擎确保长周期任务的可靠性
- **👥 人机协作**：支持低置信度结果的人工审核介入（Human-in-the-Loop）
- **💰 成本优化**：Context Caching 技术节省约 25% Token 成本
- **📊 批量处理**：支持多学生合卷上传，自动识别学生边界

## 技术栈

### 核心框架
- **Python 3.11+**：主要开发语言
- **FastAPI**：API 网关和 HTTP 服务
- **Temporal**：分布式工作流编排引擎
- **LangGraph**：智能体推理框架（图结构循环推理）
- **LangChain**：LLM 集成层

### AI 模型
- **Gemini 2.5 Flash Lite**：页面布局分析与题目分割（高吞吐、低成本）
- **Gemini 3.0 Pro**：深度推理与评分（Agentic 能力）

### 数据存储
- **PostgreSQL**：主数据库，使用 JSONB 存储非结构化批改结果和 LangGraph Checkpoint
- **Redis**：语义缓存、分布式锁、API 限流

### 基础设施
- **Kubernetes**：容器编排
- **KEDA**：基于 Temporal 队列深度的自动扩缩容
- **S3/MinIO**：对象存储（试卷图像）

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Temporal Server（可选，用于生产环境）

### 安装依赖

```bash
# 使用 uv 安装依赖（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置以下关键参数：
# - GEMINI_API_KEY: Gemini API 密钥
# - DATABASE_URL: PostgreSQL 连接字符串
# - REDIS_URL: Redis 连接字符串
```

### 数据库迁移

```bash
# 运行数据库迁移
alembic upgrade head
```

### 启动服务

```bash
# 启动 API 服务
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# 启动 Temporal Worker（编排）
python -m src.workers.orchestration_worker

# 启动 Temporal Worker（认知计算）
python -m src.workers.cognitive_worker
```

### 访问 API 文档

启动服务后，访问以下地址查看交互式 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 接口文档

### 1. 提交相关接口

#### 1.1 上传并提交批改

**端点**: `POST /api/v1/submissions`

**描述**: 上传试卷文件并提交批改任务

**请求参数**:
- `exam_id` (string, required): 考试 ID
- `student_id` (string, required): 学生 ID
- `file` (file, required): 试卷文件（支持 PDF、JPEG、PNG、WEBP）

**响应示例**:
```json
{
  "submission_id": "sub_123456",
  "exam_id": "exam_001",
  "student_id": "stu_001",
  "status": "UPLOADED",
  "estimated_completion_time": "2024-12-13T15:30:00Z"
}
```

#### 1.2 获取提交状态

**端点**: `GET /api/v1/submissions/{submission_id}`

**描述**: 查询提交的当前状态和基本信息

**响应示例**:
```json
{
  "submission_id": "sub_123456",
  "exam_id": "exam_001",
  "student_id": "stu_001",
  "status": "COMPLETED",
  "total_score": 85.5,
  "max_total_score": 100.0,
  "created_at": "2024-12-13T14:00:00Z",
  "updated_at": "2024-12-13T14:30:00Z"
}
```

#### 1.3 获取批改结果

**端点**: `GET /api/v1/submissions/{submission_id}/results`

**描述**: 获取完整的批改结果，包括各题目的详细评分和反馈

**响应示例**:
```json
{
  "submission_id": "sub_123456",
  "exam_id": "exam_001",
  "student_id": "stu_001",
  "total_score": 85.5,
  "max_total_score": 100.0,
  "question_results": [
    {
      "question_id": "q1",
      "score": 8.5,
      "max_score": 10.0,
      "confidence": 0.92,
      "feedback": "答案基本正确，但缺少关键步骤...",
      "visual_annotations": [],
      "agent_trace": {}
    }
  ]
}
```

#### 1.4 分页查询提交列表

**端点**: `GET /api/v1/submissions`

**描述**: 支持分页、排序和过滤的提交列表查询

**查询参数**:
- `page` (int, default: 1): 页码
- `page_size` (int, default: 20): 每页数量
- `sort_by` (string, optional): 排序字段
- `sort_order` (string, default: "desc"): 排序方向（asc/desc）
- `status` (string, optional): 按状态过滤
- `exam_id` (string, optional): 按考试 ID 过滤
- `student_id` (string, optional): 按学生 ID 过滤

**响应示例**:
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

#### 1.5 字段选择查询

**端点**: `GET /api/v1/submissions/{submission_id}/fields`

**描述**: 仅返回指定的字段，减少数据传输

**查询参数**:
- `fields` (string, required): 逗号分隔的字段列表，例如 "submission_id,status,total_score"

**响应示例**:
```json
{
  "submission_id": "sub_123456",
  "status": "COMPLETED",
  "total_score": 85.5
}
```

### 2. 评分细则接口

#### 2.1 创建评分细则

**端点**: `POST /api/v1/rubrics`

**描述**: 创建新的评分细则

**请求体**:
```json
{
  "exam_id": "exam_001",
  "question_id": "q1",
  "rubric_text": "评分细则描述...",
  "max_score": 10.0,
  "scoring_points": [
    {
      "description": "正确写出公式",
      "score": 3.0
    },
    {
      "description": "计算过程正确",
      "score": 5.0
    },
    {
      "description": "结果正确",
      "score": 2.0
    }
  ],
  "standard_answer": "标准答案..."
}
```

**响应示例**:
```json
{
  "rubric_id": "rub_123456",
  "exam_id": "exam_001",
  "question_id": "q1",
  "rubric_text": "评分细则描述...",
  "max_score": 10.0,
  "scoring_points": [...],
  "standard_answer": "标准答案...",
  "created_at": "2024-12-13T14:00:00Z",
  "updated_at": "2024-12-13T14:00:00Z"
}
```

#### 2.2 获取评分细则

**端点**: `GET /api/v1/rubrics/{exam_id}/{question_id}`

**描述**: 获取指定题目的评分细则

#### 2.3 更新评分细则

**端点**: `PUT /api/v1/rubrics/{rubric_id}`

**描述**: 更新现有的评分细则

**请求体**:
```json
{
  "rubric_text": "更新后的评分细则...",
  "max_score": 12.0,
  "scoring_points": [...]
}
```

### 3. 人工审核接口

#### 3.1 发送审核信号

**端点**: `POST /api/v1/reviews/{submission_id}/signal`

**描述**: 发送审核信号（批准、覆盖或拒绝）

**请求体**:
```json
{
  "submission_id": "sub_123456",
  "action": "OVERRIDE",
  "question_id": "q1",
  "override_score": 9.0,
  "override_feedback": "人工审核后调整评分",
  "review_comment": "学生答案有创新性"
}
```

**支持的操作**:
- `APPROVE`: 批准 AI 评分结果
- `OVERRIDE`: 覆盖 AI 评分，使用人工评分
- `REJECT`: 拒绝该提交

**响应示例**:
```json
{
  "message": "审核已完成，使用人工覆盖评分",
  "submission_id": "sub_123456",
  "action": "OVERRIDE",
  "override_score": 9.0
}
```

#### 3.2 获取待审核项

**端点**: `GET /api/v1/reviews/{submission_id}/pending`

**描述**: 获取该提交中所有需要人工审核的题目列表（置信度 < 0.75）

**响应示例**:
```json
[
  {
    "submission_id": "sub_123456",
    "exam_id": "exam_001",
    "student_id": "stu_001",
    "question_id": "q3",
    "ai_score": 7.5,
    "confidence": 0.68,
    "reason": "置信度低于阈值 0.75 (当前: 0.68)",
    "created_at": "2024-12-13T14:30:00Z"
  }
]
```

### 4. 批量提交接口

#### 4.1 批量提交试卷

**端点**: `POST /batch/submit`

**描述**: 上传包含多个学生作业的文件（如整班扫描的 PDF），系统会自动识别每页所属的学生并分别批改

**请求参数**:
- `exam_id` (string, required): 考试 ID
- `rubric_file` (file, required): 评分标准 PDF
- `answer_file` (file, required): 学生作答 PDF
- `api_key` (string, required): Gemini API Key
- `auto_identify` (bool, default: true): 是否自动识别学生身份

**响应示例**:
```json
{
  "batch_id": "batch_123456",
  "status": "UPLOADED",
  "total_pages": 50,
  "estimated_completion_time": 1500
}
```

#### 4.2 同步批改（测试用）

**端点**: `POST /batch/grade-sync`

**描述**: 同步执行完整的批改流程，适用于测试和小规模批改

**请求参数**:
- `rubric_file` (file, required): 评分标准 PDF
- `answer_file` (file, required): 学生作答 PDF
- `api_key` (string, required): Gemini API Key
- `total_score` (int, default: 105): 总分
- `total_questions` (int, default: 19): 总题数

**响应示例**:
```json
{
  "status": "completed",
  "total_students": 3,
  "students": [
    {
      "name": "张三",
      "page_range": {"start": 1, "end": 5},
      "total_score": 92.5,
      "max_score": 105.0,
      "percentage": 88.1,
      "questions_graded": 19,
      "details": [...]
    }
  ]
}
```

#### 4.3 优化批改（使用缓存）

**端点**: `POST /batch/grade-cached`

**描述**: 使用 Context Caching 技术优化批改，节省约 25% Token 成本

**特点**:
- 评分标准只计费一次
- 后续学生批改免费使用缓存
- 适用于批改多个学生（2+ 个学生）

**请求参数**: 同 `/batch/grade-sync`

**响应示例**:
```json
{
  "status": "completed",
  "total_students": 3,
  "optimization": {
    "method": "context_caching",
    "cache_info": {
      "cache_name": "rubric_cache_xxx",
      "ttl": 3600
    },
    "token_savings": {
      "description": "使用 Context Caching 节省约 25% Token",
      "estimated_savings_per_student": "约 15,000-20,000 tokens",
      "cost_savings_per_student": "约 $0.04-0.05"
    }
  },
  "students": [...]
}
```

#### 4.4 查询批量状态

**端点**: `GET /batch/status/{batch_id}`

**描述**: 查询批量批改的状态和进度

#### 4.5 获取批量结果

**端点**: `GET /batch/results/{batch_id}`

**描述**: 获取批量批改的完整结果

### 5. WebSocket 实时推送

#### 5.1 提交状态推送

**端点**: `WS /ws/submissions/{submission_id}`

**描述**: 订阅指定提交的状态变更，实时推送更新

**消息格式**:
```json
{
  "type": "status_update",
  "submission_id": "sub_123456",
  "status": "GRADING",
  "progress": 45,
  "message": "正在批改第 3 题..."
}
```

#### 5.2 批量批改进度推送

**端点**: `WS /batch/ws/{batch_id}`

**描述**: 实时推送批量批改进度

**消息类型**:
- `progress`: 批改进度更新
- `completed`: 批改完成
- `error`: 批改出错

**消息示例**:
```json
{
  "type": "progress",
  "stage": "grading",
  "current_student": 2,
  "total_students": 5,
  "student_name": "张三",
  "percentage": 40
}
```

### 6. 管理接口

#### 6.1 获取慢查询记录

**端点**: `GET /api/v1/admin/slow-queries`

**描述**: 获取最近的慢查询记录，用于性能监控

**查询参数**:
- `limit` (int, default: 100): 返回记录数
- `min_duration_ms` (int, optional): 最小持续时间（毫秒）

#### 6.2 获取 API 统计信息

**端点**: `GET /api/v1/admin/stats`

**描述**: 获取 API 服务的统计信息

**响应示例**:
```json
{
  "total_queries": 1234,
  "slow_queries": 5,
  "active_websocket_connections": 12,
  "subscribed_submissions": ["sub_123", "sub_456"],
  "cache_hit_rate": 0.85
}
```

#### 6.3 健康检查

**端点**: `GET /health`

**描述**: 服务健康检查

**响应示例**:
```json
{
  "status": "healthy",
  "service": "ai-grading-api",
  "version": "1.0.0"
}
```

## 项目结构

```
.
├── src/
│   ├── api/                    # FastAPI 应用
│   │   ├── main.py             # 应用入口
│   │   ├── routes/             # API 路由
│   │   │   ├── submissions.py  # 提交相关接口
│   │   │   ├── rubrics.py      # 评分细则接口
│   │   │   ├── reviews.py      # 人工审核接口
│   │   │   └── batch.py        # 批量提交接口
│   │   └── middleware/         # 中间件（限流等）
│   │
│   ├── models/                 # Pydantic 数据模型
│   ├── services/               # 业务服务层
│   ├── agents/                 # LangGraph 智能体
│   ├── workflows/              # Temporal 工作流
│   ├── activities/             # Temporal Activities
│   ├── workers/                # Temporal Worker 入口
│   ├── repositories/           # 数据访问层
│   └── utils/                  # 工具函数
│
├── tests/                      # 测试目录
│   ├── unit/                   # 单元测试
│   ├── property/               # 属性测试（Hypothesis）
│   ├── integration/            # 集成测试
│   └── fixtures/               # 测试数据
│
├── docs/                       # 文档目录
├── examples/                   # 示例代码
├── alembic/                    # 数据库迁移
├── k8s/                        # Kubernetes 配置
├── frontend/                   # 前端应用
└── .kiro/                      # Kiro AI 配置
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit/ -v

# 运行属性测试
pytest tests/property/ -v --hypothesis-show-statistics

# 运行集成测试
pytest tests/integration/ -v

# 生成测试覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

## 部署

### Docker 部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### Kubernetes 部署

```bash
# 应用配置
kubectl apply -f k8s/

# 查看部署状态
kubectl get pods -n ai-grading

# 查看服务
kubectl get svc -n ai-grading
```

详细部署说明请参考 [DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 文档

- [快速开始](docs/QUICKSTART.md)
- [API 密钥设置](docs/API_KEY_SETUP.md)
- [批量 API 指南](docs/BATCH_API_GUIDE.md)
- [缓存快速入门](docs/CACHE_QUICKSTART.md)
- [Context Caching 指南](docs/CONTEXT_CACHING_GUIDE.md)
- [集成指南](docs/INTEGRATION_GUIDE.md)
- [部署指南](docs/DEPLOYMENT.md)
- [Token 优化完整指南](docs/TOKEN_OPTIMIZATION_COMPLETE.md)

## 性能指标

- 日均处理能力：千万级请求
- 单题批改延迟：< 30 秒
- 评分准确度：与人工标注的 Pearson 相关系数 > 0.9
- Token 成本优化：使用 Context Caching 节省约 25%

## 常见问题

### 如何配置 Gemini API Key？

参考 [API_KEY_SETUP.md](docs/API_KEY_SETUP.md)

### 如何优化批改成本？

使用 `/batch/grade-cached` 端点，启用 Context Caching 技术，可节省约 25% Token 成本。

### 如何处理低置信度结果？

系统会自动将置信度 < 0.75 的结果标记为待审核，可通过 `/api/v1/reviews/{submission_id}/pending` 接口查询，并使用 `/api/v1/reviews/{submission_id}/signal` 接口进行人工审核。

### 如何监控系统性能？

使用 `/api/v1/admin/slow-queries` 和 `/api/v1/admin/stats` 接口监控系统性能。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 联系方式

- 项目主页：[GitHub](https://github.com/your-org/ai-grading-system)
- 问题反馈：[Issues](https://github.com/your-org/ai-grading-system/issues)
