# 智能缓存预热服务

## 概述

`CacheWarmupService` 提供智能缓存预热功能，包括启动预热、评分细则哈希预计算和异步批量预热。

## 核心功能

### 1. 启动预热

从 PostgreSQL 加载最近 N 天的高置信度批改结果，异步加载到 Redis。

**特性：**
- 可配置预热天数（默认 7 天）
- 可配置高置信度阈值（默认 0.9）
- 批量处理，避免阻塞
- 详细的预热统计

**使用示例：**

```python
from src.services.cache_warmup import CacheWarmupService

# 创建服务
warmup_service = CacheWarmupService(
    pool_manager=pool_manager,
    cache_service=cache_service,
    high_confidence_threshold=0.9,
    warmup_days=7,
    batch_size=100
)

# 执行启动预热
result = await warmup_service.warmup_on_startup()

print(f"加载: {result['loaded_count']}")
print(f"缓存: {result['cached_count']}")
print(f"失败: {result['failed_count']}")
print(f"耗时: {result['elapsed_seconds']:.2f}秒")
```

### 2. 评分细则哈希预计算

创建评分细则时预计算哈希值并缓存，后续查询可以直接从缓存获取。

**特性：**
- 自动计算 SHA-256 哈希
- 缓存 7 天
- 支持缓存失效

**使用示例：**

```python
# 预计算哈希
rubric_hash = await warmup_service.precompute_rubric_hash(
    rubric_id="rubric_001",
    rubric_text="评分细则内容...",
    exam_id="exam_001",
    question_id="q1"
)

# 从缓存获取哈希
cached_hash = await warmup_service.get_cached_rubric_hash(
    exam_id="exam_001",
    question_id="q1"
)

# 使缓存失效
await warmup_service.invalidate_rubric_hash_cache(
    exam_id="exam_001",
    question_id="q1"
)
```

### 3. 异步批量预热

批量导入时异步预热，不阻塞主流程。

**特性：**
- 后台异步执行
- 不阻塞主流程
- 自动批量处理

**使用示例：**

```python
# 启动异步预热任务
submission_ids = ["sub_001", "sub_002", "sub_003"]
warmup_task = await warmup_service.async_batch_warmup(submission_ids)

# 可选：等待任务完成
await warmup_task
```

## 集成到评分细则服务

`RubricService` 已集成缓存预热功能：

```python
from src.services.rubric import RubricService
from src.services.cache_warmup import CacheWarmupService

# 创建服务
warmup_service = CacheWarmupService(...)
rubric_service = RubricService(
    rubric_repository=rubric_repo,
    cache_service=cache_service,
    warmup_service=warmup_service  # 注入预热服务
)

# 创建评分细则时自动预计算哈希
rubric = await rubric_service.create_rubric(request)
# 哈希已自动预计算并缓存

# 更新评分细则时自动更新哈希
rubric = await rubric_service.update_rubric(rubric_id, request)
# 旧哈希已失效，新哈希已预计算

# 删除评分细则时自动清理哈希
await rubric_service.delete_rubric(rubric_id)
# 哈希缓存已清理
```

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `high_confidence_threshold` | float | 0.9 | 高置信度阈值 |
| `warmup_days` | int | 7 | 预热天数 |
| `batch_size` | int | 100 | 批量处理大小 |

## 预热统计

通过 `warmup_stats` 属性获取预热统计信息：

```python
stats = warmup_service.warmup_stats

print(f"总加载数: {stats['total_loaded']}")
print(f"总缓存数: {stats['total_cached']}")
print(f"总失败数: {stats['total_failed']}")
print(f"最后预热时间: {stats['last_warmup_at']}")
```

## 最佳实践

### 1. 应用启动时预热

```python
async def startup_event():
    """应用启动事件"""
    # 初始化连接池
    await pool_manager.initialize(...)
    
    # 启动缓存服务
    await cache_service.start()
    
    # 执行启动预热
    await warmup_service.warmup_on_startup()
```

### 2. 评分细则 CRUD 集成

```python
# 创建时预计算
rubric = await rubric_service.create_rubric(request)

# 更新时重新计算
rubric = await rubric_service.update_rubric(rubric_id, request)

# 删除时清理缓存
await rubric_service.delete_rubric(rubric_id)
```

### 3. 批量导入时异步预热

```python
# 批量导入提交
for submission in submissions:
    await submission_service.create(submission)

# 异步预热（不阻塞）
submission_ids = [s.id for s in submissions]
await warmup_service.async_batch_warmup(submission_ids)
```

## 性能考虑

### 启动预热

- **优点**：减少冷启动延迟，提高缓存命中率
- **成本**：启动时间增加，数据库查询开销
- **建议**：
  - 生产环境：启用，预热 7 天数据
  - 开发环境：可选，预热 1-3 天数据
  - 测试环境：禁用

### 哈希预计算

- **优点**：加速缓存键生成，减少重复计算
- **成本**：Redis 存储空间（每个哈希约 100 字节）
- **建议**：始终启用

### 异步批量预热

- **优点**：不阻塞主流程，提高用户体验
- **成本**：后台资源消耗
- **建议**：批量操作时使用

## 监控指标

建议监控以下指标：

```python
# 预热统计
warmup_stats = warmup_service.warmup_stats

# 缓存统计
cache_stats = cache_service.get_stats_dict()

# 关键指标
metrics = {
    "warmup_loaded": warmup_stats["total_loaded"],
    "warmup_cached": warmup_stats["total_cached"],
    "warmup_failed": warmup_stats["total_failed"],
    "cache_hit_rate": cache_stats["redis_hit_rate"],
    "fallback_mode": cache_stats["fallback_mode"]
}
```

## 故障处理

### Redis 不可用

预热服务会优雅降级：
- 预热操作失败但不影响应用启动
- 记录警告日志
- 返回失败统计

### 数据库查询超时

- 使用连接池超时机制
- 记录错误日志
- 返回部分预热结果

### 内存不足

- 使用批量处理避免一次性加载过多数据
- 配置合理的 `batch_size`
- 监控 Redis 内存使用

## 相关文档

- [多层缓存服务](./README_CACHE.md)
- [统一连接池管理器](../utils/README_POOL_MANAGER.md)
- [评分细则服务](./README_RUBRIC.md)

## 验证需求

- ✅ 需求 6.1：启动预热
- ✅ 需求 6.2：评分细则哈希预计算
- ✅ 需求 6.4：异步批量预热
