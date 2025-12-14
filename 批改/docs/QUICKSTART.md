# AI 批改系统快速启动指南

## 环境配置

### 1. API Key 配置

系统已配置 Gemini API Key，存储在 `.env` 文件中：

```bash
GEMINI_API_KEY=AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE
```

### 2. 使用的模型

系统使用两个 Gemini 模型：

- **Gemini 2.5 Flash Lite** (`gemini-2.5-flash-lite`)
  - 用途：页面布局分析和题目分割
  - 特点：高吞吐、低成本、快速响应
  - 位置：`src/services/layout_analysis.py`

- **Gemini 3.0 Pro Preview** (`gemini-3-pro-preview`)
  - 用途：深度推理批改
  - 特点：最新一代推理能力、更强的理解力、更高准确度
  - 位置：`src/services/gemini_reasoning.py`

## 快速启动

### 1. 安装依赖

```bash
# 使用 uv 安装依赖
uv sync
```

### 2. 启动基础设施

```bash
# 启动 PostgreSQL、Redis、Temporal、MinIO
docker-compose up -d
```

### 3. 运行数据库迁移

```bash
# 创建数据库表
alembic upgrade head
```

### 4. 启动服务

#### 启动 API 服务

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

#### 启动 Temporal Workers

在不同的终端窗口中：

```bash
# 编排 Worker（处理工作流编排）
python -m src.workers.orchestration_worker

# 认知 Worker（处理 AI 批改任务）
python -m src.workers.cognitive_worker
```

## 测试 API

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

### 2. 提交试卷批改

```bash
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{
    "exam_id": "exam_001",
    "student_id": "student_001",
    "file_type": "image",
    "file_data": "<base64_encoded_image>"
  }'
```

### 3. 查询批改状态

```bash
curl http://localhost:8000/api/v1/submissions/{submission_id}
```

### 4. 获取批改结果

```bash
curl http://localhost:8000/api/v1/submissions/{submission_id}/results
```

## 运行测试

### 运行所有测试

```bash
pytest tests/ -v
```

### 运行单元测试

```bash
pytest tests/unit/ -v
```

### 运行属性测试

```bash
pytest tests/property/ -v --hypothesis-show-statistics
```

### 运行集成测试

```bash
pytest tests/integration/ -v
```

### 查看测试覆盖率

```bash
pytest tests/ --cov=src --cov-report=html
# 在浏览器中打开 htmlcov/index.html
```

## 系统架构

```
┌─────────────────┐
│   API Gateway   │  FastAPI (端口 8000)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Temporal Cluster│  工作流编排
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│编排Worker│ │认知Worker│
└────────┘ └────────┘
    │         │
    │         ▼
    │    ┌─────────────┐
    │    │ LangGraph   │  智能体推理
    │    │ + Gemini    │
    │    └─────────────┘
    │
    ▼
┌─────────────────┐
│  PostgreSQL     │  数据持久化
│  + Redis        │  缓存 + 限流
└─────────────────┘
```

## 核心功能

### 1. 纯视觉批改

- 无需 OCR，直接使用 VLM 理解试卷图像
- Gemini 2.5 Flash Lite 进行页面分割
- Gemini 2.5 Pro 进行深度推理批改

### 2. 智能体推理

- LangGraph 构建的多步推理流程
- 视觉提取 → 评分映射 → 自我反思 → 最终化
- 支持最多 3 次修正循环

### 3. 持久化执行

- Temporal 工作流引擎保证任务可靠性
- 支持断点恢复和重试
- 检查点持久化到 PostgreSQL

### 4. 人工审核

- 低置信度结果自动触发人工审核
- 支持批准、覆盖、拒绝三种操作
- 工作流等待人工介入时不消耗资源

### 5. 语义缓存

- 使用感知哈希识别相似题目
- 高置信度结果自动缓存 30 天
- 缓存失败不影响批改流程

## 监控和调试

### 查看 Temporal UI

```bash
# 访问 Temporal Web UI
http://localhost:8233
```

### 查看日志

```bash
# API 服务日志
tail -f logs/api.log

# Worker 日志
tail -f logs/worker.log
```

### Redis 监控

```bash
# 连接 Redis CLI
redis-cli

# 查看缓存键
KEYS grade_cache:*

# 查看限流状态
KEYS rate_limit:*
```

## 常见问题

### Q: Gemini API 调用失败？

A: 检查以下几点：
1. API Key 是否正确配置在 `.env` 文件中
2. 网络连接是否正常
3. API 配额是否充足
4. 模型名称是否正确（`gemini-2.5-flash-lite` 和 `gemini-2.5-pro`）

### Q: 数据库连接失败？

A: 确保 PostgreSQL 容器正在运行：
```bash
docker-compose ps
docker-compose logs postgres
```

### Q: Temporal Worker 无法连接？

A: 确保 Temporal 服务正在运行：
```bash
docker-compose ps temporal
docker-compose logs temporal
```

### Q: 测试失败？

A: 运行测试前确保：
1. 所有依赖已安装：`uv sync`
2. 环境变量已配置：`.env` 文件存在
3. 基础设施服务正在运行（如果运行集成测试）

## 下一步

1. **配置评分细则**：使用 API 为每道题目配置评分标准
2. **上传试卷**：提交试卷图像进行批改
3. **监控性能**：查看 Temporal UI 了解工作流执行情况
4. **调整参数**：根据实际情况调整置信度阈值、缓存 TTL 等参数
5. **扩展部署**：使用 Kubernetes 部署到生产环境

## 技术支持

- 查看详细文档：`DEPLOYMENT.md`
- 查看 API 文档：http://localhost:8000/docs
- 查看设计文档：`.kiro/specs/ai-grading-agent/design.md`
