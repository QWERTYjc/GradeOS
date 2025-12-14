# 评分细则服务 (Rubric Service)

## 概述

评分细则服务提供评分细则的完整业务逻辑，包括 CRUD 操作、缓存失效管理和缺失评分细则检测。

## 功能特性

### 1. CRUD 操作

- **创建评分细则** (`create_rubric`)
  - 将评分细则链接到 exam_id 和 question_id
  - 自动检查重复
  - 验证：需求 9.1

- **获取评分细则** (`get_rubric`, `get_rubric_by_id`, `get_exam_rubrics`)
  - 支持按 exam_id + question_id 查询
  - 支持按 rubric_id 查询
  - 支持获取考试的所有评分细则
  - 验证：需求 9.2

- **更新评分细则** (`update_rubric`)
  - 支持部分更新
  - 自动使相关缓存失效
  - 验证：需求 9.2, 9.4

- **删除评分细则** (`delete_rubric`)
  - 删除前自动使缓存失效
  - 验证：需求 9.2

### 2. 缓存失效管理

- **自动缓存失效**
  - 更新评分细则时自动使旧缓存失效
  - 如果评分细则文本更新，同时使新旧文本的缓存失效
  - 删除评分细则时自动使缓存失效
  - 验证：需求 9.4

### 3. 缺失评分细则检测

- **验证评分细则** (`validate_rubric_for_grading`)
  - 检查题目是否有评分细则可用于批改
  - 如果缺失，返回描述性错误消息
  - 验证：需求 9.5

- **检查存在性** (`check_rubric_exists`)
  - 快速检查评分细则是否存在
  - 验证：需求 9.5

## 使用示例

### 初始化服务

```python
from src.services.rubric import RubricService
from src.repositories.rubric import RubricRepository
from src.services.cache import CacheService
from src.utils.database import Database
import redis.asyncio as redis

# 初始化依赖
db = Database(connection_string="postgresql://...")
redis_client = redis.Redis(host="localhost", port=6379)

# 创建服务实例
rubric_repository = RubricRepository(db)
cache_service = CacheService(redis_client)
rubric_service = RubricService(rubric_repository, cache_service)
```

### 创建评分细则

```python
from src.models.rubric import RubricCreateRequest, ScoringPoint

request = RubricCreateRequest(
    exam_id="exam-001",
    question_id="q1",
    rubric_text="1. 正确列出公式（3分）\n2. 计算过程正确（5分）",
    max_score=8.0,
    scoring_points=[
        ScoringPoint(description="正确列出公式", score=3.0, required=True),
        ScoringPoint(description="计算过程正确", score=5.0, required=True)
    ],
    standard_answer="F=ma"
)

rubric = await rubric_service.create_rubric(request)
print(f"创建成功: {rubric.rubric_id}")
```

### 获取评分细则

```python
# 按 exam_id 和 question_id 获取
rubric = await rubric_service.get_rubric("exam-001", "q1")

# 按 rubric_id 获取
rubric = await rubric_service.get_rubric_by_id("rubric-123")

# 获取考试的所有评分细则
rubrics = await rubric_service.get_exam_rubrics("exam-001")
```

### 更新评分细则

```python
from src.models.rubric import RubricUpdateRequest

update_request = RubricUpdateRequest(
    max_score=10.0,
    rubric_text="更新后的评分细则"
)

updated_rubric = await rubric_service.update_rubric("rubric-123", update_request)
# 相关缓存会自动失效
```

### 验证评分细则

```python
# 在批改前验证评分细则是否存在
is_valid, error_msg = await rubric_service.validate_rubric_for_grading(
    "exam-001", "q1"
)

if not is_valid:
    print(f"无法批改: {error_msg}")
    # 题目缺失评分细则，需要手动配置
else:
    # 继续批改流程
    pass
```

### 删除评分细则

```python
success = await rubric_service.delete_rubric("rubric-123")
# 相关缓存会自动失效
```

## 错误处理

### ValueError 异常

- **创建时已存在**: 尝试创建已存在的评分细则
- **更新时不存在**: 尝试更新不存在的评分细则

```python
try:
    rubric = await rubric_service.create_rubric(request)
except ValueError as e:
    print(f"创建失败: {e}")
```

## 缓存失效机制

评分细则服务与缓存服务紧密集成：

1. **更新评分细则时**
   - 自动使旧评分细则文本的所有缓存失效
   - 如果评分细则文本更新，同时使新文本的缓存失效

2. **删除评分细则时**
   - 自动使该评分细则的所有缓存失效

3. **缓存键格式**
   ```
   grade_cache:v1:{rubric_hash}:{image_hash}
   ```

## 依赖关系

```
RubricService
├── RubricRepository (数据访问)
└── CacheService (缓存管理)
```

## 测试

运行评分细则服务的测试：

```bash
pytest tests/unit/test_rubric_service.py -v
```

## 相关文档

- [评分细则仓储](../repositories/README.md)
- [缓存服务](./README.md)
- [需求文档](../../.kiro/specs/ai-grading-agent/requirements.md)
- [设计文档](../../.kiro/specs/ai-grading-agent/design.md)
