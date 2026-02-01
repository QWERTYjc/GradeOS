# GradeOS 日志系统使用指南

## 概述

GradeOS 后端现已集成完整的日志系统，包括：
- ✅ AI 返回的完整 JSON 输出（Rubric 解析结果、批改结果）
- ✅ 所有 SQL 数据库操作的详细日志
- ✅ 所有 Redis 缓存操作的详细日志
- ✅ UTF-8 编码支持，中文显示正常

## 日志文件位置

```
GradeOS-Platform/backend/batch_grading.log
```

## 日志格式

### SQL 操作日志

**成功操作：**
```
[SQL] ✅ SELECT: {"operation": "SELECT", "query": "SELECT * FROM grading_history WHERE batch_id = %s", "params": ["batch_123"], "result_count": 1}
```

**失败操作：**
```
[SQL] ❌ INSERT 失败: {"operation": "INSERT", "query": "INSERT INTO ...", "params": [...], "error": "连接超时"}
```

### Redis 操作日志

**成功操作：**
```
[Redis] ✅ HSET: {"operation": "HSET", "key": "grading_run:record:batch_123", "value": "{'status': 'running'}", "result": "OK"}
```

**失败操作：**
```
[Redis] ❌ GET 失败: {"operation": "GET", "key": "grading_run:record:batch_999", "error": "连接被拒绝"}
```

### AI JSON 输出日志

**Rubric 解析结果：**
```
[AI] Rubric 解析完成，完整 JSON 输出:
{
  "rubric_items": [...],
  "total_score": 100,
  ...
}
```

**批改结果：**
```
[AI] 批改完成，完整 JSON 输出:
{
  "page_results": [...],
  "student_results": [...],
  ...
}
```

## 已集成日志的操作

### 数据库操作 (postgres_grading.py)

| 函数 | 操作类型 | 日志内容 |
|------|---------|---------|
| `save_grading_history` | INSERT/UPDATE | 完整 SQL + 参数 + 结果 |
| `get_grading_history` | SELECT | 查询条件 + 结果数量 |
| `list_grading_history` | SELECT | 查询条件 + 结果数量 |
| `save_student_result` | INSERT/UPDATE | 完整 SQL + 参数 + 结果 |
| `get_student_results` | SELECT | 查询条件 + 结果数量 |

### Redis 操作 (grading_run_control.py)

| 函数 | 操作类型 | 日志内容 |
|------|---------|---------|
| `register_run` | HSET/SADD/ZADD | Key + Value + 结果 |
| `update_run` | HSET | Key + 更新字段 + 结果 |
| `try_acquire_slot` | LUA_SCRIPT | 槽位获取逻辑 + 结果 |
| `release_slot` | ZREM | Key + 释放的 batch_id |
| `remove_from_queue` | ZREM | Key + 移除的 batch_id |
| `list_runs` | SMEMBERS/HGETALL | 查询的 run 数量 |
| `get_run` | HGETALL | Key + 字段数量 |

### AI 输出 (batch_grading.py)

| 位置 | 内容 |
|------|------|
| 第 ~790 行 | Rubric 解析后的完整 JSON |
| 第 ~2660 行 | 批改完成后的完整 JSON (page_results + student_results) |

## 使用工具函数

### SQL 日志记录器

```python
from src.utils.sql_logger import log_sql_operation

# 记录成功的查询
log_sql_operation(
    "SELECT",
    "SELECT * FROM grading_history WHERE batch_id = %s",
    params=("batch_123",),
    result_count=5
)

# 记录失败的操作
log_sql_operation(
    "INSERT",
    "INSERT INTO grading_history ...",
    params=(...),
    error=Exception("连接超时")
)
```

### Redis 日志记录器

```python
from src.utils.redis_logger import log_redis_operation

# 记录成功的操作
log_redis_operation(
    "HSET",
    "grading_run:record:batch_123",
    value={"status": "running"},
    result="OK"
)

# 记录失败的操作
log_redis_operation(
    "GET",
    "grading_run:record:batch_999",
    error=Exception("连接被拒绝")
)
```

## 测试日志功能

运行测试脚本验证日志功能：

```bash
cd GradeOS-Platform/backend
python test_logging.py
```

测试脚本会：
1. 测试 SQL 日志记录器（SELECT、INSERT、UPDATE、错误情况）
2. 测试 Redis 日志记录器（HSET、ZADD、SMEMBERS、长值截断、错误情况）
3. 将所有日志写入 `batch_grading.log`

## 日志级别

- **INFO**: 正常操作（✅ 成功）
- **ERROR**: 失败操作（❌ 失败）
- **DEBUG**: 详细调试信息

## 注意事项

1. **长值自动截断**: Redis 值超过 200 字符会自动截断，避免日志文件过大
2. **UTF-8 编码**: 日志文件使用 UTF-8 with BOM 编码，确保中文正常显示
3. **JSON 格式**: 所有日志数据使用 JSON 格式，便于解析和分析
4. **自动重载**: 后端使用 `--reload` 标志运行，代码修改后自动生效

## 故障排查

### 如果日志中文显示乱码

运行重置脚本：
```bash
python reset_log.py
```

### 如果日志文件过大

可以手动清空或归档：
```bash
# Windows
del batch_grading.log
# 或者归档
move batch_grading.log batch_grading_backup.log
```

### 查看最新日志

```bash
# Windows PowerShell
Get-Content batch_grading.log -Tail 50 -Encoding UTF8

# Linux/Mac
tail -f batch_grading.log
```

## 相关文件

- `src/utils/sql_logger.py` - SQL 日志工具
- `src/utils/redis_logger.py` - Redis 日志工具
- `src/db/postgres_grading.py` - 数据库操作（已集成日志）
- `src/services/grading_run_control.py` - Redis 操作（已集成日志）
- `src/graphs/batch_grading.py` - AI 输出日志（已集成）
- `test_logging.py` - 日志功能测试脚本
- `reset_log.py` - 日志文件重置脚本
