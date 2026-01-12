# 无数据库模式部署指南

## 概述

GradeOS 批改系统支持两种部署模式：

1. **数据库模式**：完整功能，需要 PostgreSQL 和 Redis
2. **无数据库模式**：轻量级部署，仅使用内存缓存和 LLM API

无数据库模式适用于：
- 快速测试和演示
- 个人使用或小规模批改
- 不需要持久化历史记录的场景
- 降低部署复杂度和成本

## 功能对比

| 功能 | 数据库模式 | 无数据库模式 |
|------|-----------|-------------|
| AI 批改 | ✅ | ✅ |
| 数据持久化 | ✅ | ❌ |
| 历史记录 | ✅ | ❌ |
| 数据分析 | ✅ | ❌ |
| Redis 缓存 | ✅ | ❌（使用内存缓存）|
| WebSocket 实时推送 | ✅ | ❌ |
| 结果导出 JSON | ✅ | ✅ |

## 快速启动

### 方式 1：不设置 DATABASE_URL

最简单的方式是不设置 `DATABASE_URL` 环境变量：

```bash
# 只需要设置 Gemini API Key
export GEMINI_API_KEY="your-api-key"

# 启动服务
uvicorn src.api.main:app --host 0.0.0.0 --port 8001
```

### 方式 2：设置空的 DATABASE_URL

```bash
export DATABASE_URL=""
export GEMINI_API_KEY="your-api-key"

uvicorn src.api.main:app --host 0.0.0.0 --port 8001
```

### 方式 3：使用 .env 文件

创建 `.env` 文件：

```env
# 无数据库模式：不设置或留空 DATABASE_URL
DATABASE_URL=

# 必需：Gemini API Key
GEMINI_API_KEY=your-api-key-here

# 可选配置
LOG_LEVEL=INFO
```

然后启动：

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8001
```

## 启动日志

成功启动无数据库模式时，你会看到类似的日志：

```
INFO - 初始化应用...
INFO - 检测到无数据库模式：DATABASE_URL 未设置
INFO - 系统将使用内存缓存和 LLM API 运行
INFO - 部署模式: no_database
INFO - 功能可用性: {'grading': True, 'persistence': False, 'history': False, 'analytics': False, 'caching': True, 'websocket': False, 'mode': 'no_database'}
INFO - 无数据库模式：跳过数据库和 Redis 初始化
INFO - 系统将使用内存缓存和 LLM API 运行
INFO - LangGraph 编排器已初始化
INFO - 应用启动完成
```

## 使用示例

### 1. 检查系统状态

```bash
curl http://localhost:8001/health
```

响应示例：

```json
{
  "status": "healthy",
  "service": "ai-grading-api",
  "version": "1.0.0",
  "deployment_mode": "no_database",
  "database_available": false,
  "degraded_mode": true,
  "features": {
    "grading": true,
    "persistence": false,
    "history": false,
    "analytics": false,
    "caching": true,
    "websocket": false,
    "mode": "no_database"
  }
}
```

### 2. 提交批改任务

无数据库模式下，批改功能完全可用：

```bash
curl -X POST http://localhost:8001/api/batch/grade \
  -H "Content-Type: multipart/form-data" \
  -F "pdf_file=@student_answers.pdf" \
  -F "rubric_file=@rubric.pdf"
```

### 3. 导出结果

批改完成后，结果会以 JSON 格式返回，你可以保存到本地：

```bash
curl http://localhost:8001/api/batch/results/{batch_id} > results.json
```

## 数据库降级

如果你配置了 `DATABASE_URL` 但数据库连接失败，系统会自动降级到无数据库模式：

```
INFO - 部署模式: database
INFO - 数据库连接: postgresql://***@localhost:5432/ai_grading
ERROR - 数据库连接超时，降级到无数据库模式
WARNING - 系统将使用内存缓存继续运行
WARNING - 数据库连接失败，已降级到无数据库模式
```

这确保了系统的高可用性：即使数据库不可用，批改功能仍然可以正常工作。

## 评分标准管理

### 内存缓存

无数据库模式下，评分标准存储在内存中：

```python
from src.services.rubric_registry import get_global_registry
from src.models.grading_models import QuestionRubric, ScoringPoint

# 获取全局注册中心
registry = get_global_registry()

# 注册评分标准
rubric = QuestionRubric(
    question_id="1",
    max_score=10.0,
    question_text="计算题",
    standard_answer="答案：42",
    scoring_points=[
        ScoringPoint(description="计算过程", score=6.0, is_required=True),
        ScoringPoint(description="最终答案", score=4.0, is_required=True),
    ],
    alternative_solutions=[],
    grading_notes=""
)
registry.register_rubric(rubric)
```

### 持久化到文件

你可以将评分标准保存到文件：

```python
# 保存
registry.save_to_file("rubrics.json")

# 加载
from src.services.rubric_registry import RubricRegistry
registry = RubricRegistry.load_from_file("rubrics.json")
```

## 限制和注意事项

### 1. 数据不持久化

- 服务重启后，所有数据（评分标准、批改结果）都会丢失
- 建议及时导出重要结果

### 2. 无历史记录

- 无法查询历史批改记录
- 无法进行数据分析和统计

### 3. 无实时推送

- WebSocket 功能不可用
- 需要轮询获取批改进度

### 4. 内存限制

- 所有数据存储在内存中
- 大规模批改可能受内存限制

## 从无数据库模式迁移到数据库模式

如果你想从无数据库模式迁移到数据库模式：

1. 安装并启动 PostgreSQL 和 Redis

2. 更新 `.env` 文件：

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_grading
REDIS_URL=redis://localhost:6379
GEMINI_API_KEY=your-api-key-here
```

3. 运行数据库迁移：

```bash
alembic upgrade head
```

4. 重启服务：

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8001
```

系统会自动检测到数据库配置并启用完整功能。

## 故障排查

### 问题：系统仍然尝试连接数据库

**解决方案**：确保 `DATABASE_URL` 环境变量未设置或为空字符串。

```bash
# 检查环境变量
echo $DATABASE_URL

# 如果有值，取消设置
unset DATABASE_URL
```

### 问题：批改功能不可用

**解决方案**：检查 Gemini API Key 是否正确设置。

```bash
# 检查 API Key
echo $GEMINI_API_KEY

# 测试 API 连接
curl http://localhost:8001/health
```

### 问题：内存不足

**解决方案**：
1. 减少并行批改的批次大小
2. 及时清理不需要的数据
3. 考虑升级到数据库模式

## 性能优化建议

### 1. 调整批次大小

```python
# 在批改配置中调整
batch_size = 5  # 减少批次大小以降低内存使用
```

### 2. 及时清理缓存

```python
from src.services.rubric_registry import get_global_registry

registry = get_global_registry()
registry.clear()  # 清空评分标准缓存
```

### 3. 导出结果后释放内存

批改完成后，及时导出结果并释放相关资源。

## 总结

无数据库模式提供了一种轻量级的部署方式，适合快速测试、演示和小规模使用。虽然功能有限，但核心的 AI 批改能力完全可用，并且部署简单、成本低。

对于生产环境或需要完整功能的场景，建议使用数据库模式。
