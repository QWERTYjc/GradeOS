# 数据库层使用说明

## 概述

本模块实现了数据访问层（Repository Pattern），提供了对 PostgreSQL 数据库的抽象访问接口。

## 组件

### 1. Database 连接管理器 (`src/utils/database.py`)

提供异步数据库连接池管理。

```python
from src.utils.database import db

# 初始化连接池
await db.connect()

# 使用连接
async with db.connection() as conn:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM submissions")
        results = await cur.fetchall()

# 使用事务
async with db.transaction() as conn:
    async with conn.cursor() as cur:
        await cur.execute("INSERT INTO ...")
        await cur.execute("UPDATE ...")
        # 自动提交或回滚

# 关闭连接池
await db.disconnect()
```

### 2. SubmissionRepository

管理提交记录的 CRUD 操作。

```python
from src.utils.database import db
from src.repositories import SubmissionRepository
from src.models.enums import SubmissionStatus

repo = SubmissionRepository(db)

# 创建提交
submission = await repo.create(
    exam_id="exam-uuid",
    student_id="student-uuid",
    file_paths=["s3://bucket/file1.jpg", "s3://bucket/file2.jpg"]
)

# 获取提交
submission = await repo.get_by_id("submission-uuid")

# 更新状态
await repo.update_status("submission-uuid", SubmissionStatus.GRADING)

# 更新分数
await repo.update_scores("submission-uuid", total_score=85.5, max_total_score=100.0)

# 获取待审核列表
pending = await repo.get_pending_reviews(limit=50)
```

### 3. GradingResultRepository

管理批改结果，支持复合主键操作。

```python
from src.repositories import GradingResultRepository

repo = GradingResultRepository(db)

# 创建批改结果
result = await repo.create(
    submission_id="submission-uuid",
    question_id="q1",
    score=8.5,
    max_score=10.0,
    confidence_score=0.92,
    visual_annotations=[{"type": "error", "bbox": {...}}],
    agent_trace={"vision_analysis": "...", "reasoning_steps": [...]},
    student_feedback={"message": "解题思路正确"}
)

# 根据复合键获取
result = await repo.get_by_composite_key("submission-uuid", "q1")

# 获取提交的所有结果
results = await repo.get_by_submission("submission-uuid")

# 获取低置信度结果
low_conf = await repo.get_low_confidence_results(threshold=0.75, limit=50)
```

### 4. RubricRepository

管理评分细则，支持 exam_id + question_id 查询。

```python
from src.repositories import RubricRepository

repo = RubricRepository(db)

# 创建评分细则
rubric = await repo.create(
    exam_id="exam-uuid",
    question_id="q1",
    rubric_text="1. 正确列出公式（3分）\n2. 计算过程正确（5分）",
    max_score=10.0,
    scoring_points=[
        {"description": "正确列出公式", "score": 3.0, "required": True},
        {"description": "计算过程正确", "score": 5.0, "required": True}
    ],
    standard_answer="使用牛顿第二定律..."
)

# 根据考试和题目获取
rubric = await repo.get_by_exam_and_question("exam-uuid", "q1")

# 检查是否存在
exists = await repo.exists("exam-uuid", "q1")

# 更新评分细则
await repo.update(
    rubric_id="rubric-uuid",
    rubric_text="更新后的评分细则",
    max_score=12.0
)
```

## 环境变量配置

在 `.env` 文件中配置数据库连接：

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_grading
DB_USER=postgres
DB_PASSWORD=postgres
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10
```

## 数据库迁移

使用 Alembic 管理数据库 schema：

```bash
# 运行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1

# 查看迁移历史
alembic history

# 创建新迁移
alembic revision -m "description"
```

## 注意事项

1. **UUID 类型**：所有 ID 字段在数据库中存储为 UUID 类型，在 Python 中使用字符串表示
2. **JSONB 字段**：`file_paths`、`visual_annotations`、`agent_trace`、`student_feedback`、`scoring_points` 等字段使用 JSONB 存储
3. **时间戳**：所有时间戳字段使用 UTC 时区
4. **连接池**：使用异步连接池，需要在应用启动时调用 `await db.connect()`
5. **事务管理**：使用 `db.transaction()` 上下文管理器确保事务的原子性
