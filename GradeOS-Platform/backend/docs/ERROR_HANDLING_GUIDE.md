# 错误处理指南

本文档描述了批改工作流优化中实现的完善错误处理机制。

## 概述

错误处理模块 (`src/utils/error_handling.py`) 提供了以下功能：

1. **指数退避重试** (Requirement 9.1)
2. **错误隔离** (Requirement 9.2)
3. **部分结果保存** (Requirement 9.4)
4. **详细错误日志** (Requirement 9.5)

## 功能详解

### 1. 指数退避重试

API 调用失败时使用指数退避策略重试最多3次。

#### 使用装饰器

```python
from src.utils.error_handling import with_retry

@with_retry(max_retries=3, initial_delay=1.0, max_delay=60.0)
async def call_gemini_api():
    # API 调用代码
    response = await client.ainvoke(...)
    return response
```

#### 手动调用

```python
from src.utils.error_handling import retry_with_exponential_backoff, RetryConfig

config = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
)

result = await retry_with_exponential_backoff(
    func=my_async_function,
    arg1, arg2,
    config=config,
    error_log_context={"batch_id": "123"},
)
```

#### 重试策略

- **初始延迟**: 1秒
- **指数基数**: 2（每次重试延迟翻倍）
- **最大延迟**: 60秒
- **随机抖动**: 避免雷鸣群效应
- **最大重试次数**: 3次

延迟计算公式：
```
delay = min(initial_delay * (2 ^ retry_count), max_delay) * random(0.5, 1.0)
```

示例延迟序列：
- 第1次重试: ~1秒
- 第2次重试: ~2秒
- 第3次重试: ~4秒

### 2. 错误隔离

单页失败不影响其他页面，记录错误并继续处理。

#### 隔离执行单个任务

```python
from src.utils.error_handling import execute_with_isolation

result = await execute_with_isolation(
    func=grade_page,
    page_image,
    index=page_index,
    error_log_context={"batch_id": "123"},
)

if result.is_success():
    page_result = result.get_result()
else:
    error = result.get_error()
    error_log = result.error_log
```

#### 批量隔离执行

```python
from src.utils.error_handling import execute_batch_with_isolation

async def process_page(page):
    # 处理单页
    return await grade_page(page)

results = await execute_batch_with_isolation(
    func=process_page,
    items=pages,
    error_log_context={"batch_id": "123"},
)

# 分离成功和失败结果
successful = [r.get_result() for r in results if r.is_success()]
failed = [r for r in results if r.is_failure()]
```

#### 错误隔离特性

- 单个任务失败不会中断整个批次
- 每个失败都会被记录到错误日志
- 返回统一的 `IsolatedResult` 对象
- 自动统计成功/失败数量

### 3. 部分结果保存

不可恢复错误时保存已完成的部分结果。

#### 基本使用

```python
from src.utils.error_handling import execute_with_partial_save

partial_results = await execute_with_partial_save(
    func=process_item,
    items=all_items,
    batch_id="batch_123",
    save_path="./exports/partial_results.json",
    error_log_context={"task": "grading"},
)

print(f"完成: {partial_results.completed_count}/{partial_results.total_items}")
print(f"失败: {partial_results.failed_count}")
```

#### 手动管理部分结果

```python
from src.utils.error_handling import PartialResults

partial = PartialResults(batch_id="batch_123", total_items=100)

for i, item in enumerate(items):
    try:
        result = await process_item(item)
        partial.add_result(result)
    except Exception as e:
        partial.add_failure(i, e, context={"item_id": item.id})

# 保存部分结果
partial.save_to_file("./exports/partial_results.json")

# 导出为字典
data = partial.to_dict()
```

#### 部分结果文件格式

```json
{
  "batch_id": "batch_123",
  "total_items": 100,
  "completed_count": 85,
  "failed_count": 15,
  "completion_rate": 0.85,
  "completed_results": [...],
  "failed_items": [
    {
      "index": 42,
      "error": "API timeout",
      "error_type": "TimeoutError",
      "timestamp": "2025-12-28T10:30:45.123456"
    }
  ],
  "error_logs": [...],
  "timestamp": "2025-12-28T10:35:00.000000"
}
```

### 4. 详细错误日志

记录错误类型、上下文、堆栈信息等详细信息。

#### 使用全局错误管理器

```python
from src.utils.error_handling import get_error_manager

error_manager = get_error_manager()

try:
    result = await risky_operation()
except Exception as e:
    # 记录错误
    error_log = error_manager.add_error(
        exc=e,
        context={
            "operation": "grade_page",
            "page_index": 42,
            "batch_id": "batch_123",
        },
        batch_id="batch_123",
        page_index=42,
        question_id="Q1",
        retry_count=2,
    )
```

#### 查询错误日志

```python
# 获取指定批次的所有错误
batch_errors = error_manager.get_errors_by_batch("batch_123")

# 获取指定页面的所有错误
page_errors = error_manager.get_errors_by_page(42)

# 获取所有未解决的错误
unresolved = error_manager.get_unresolved_errors()

# 标记错误已解决
error_manager.mark_resolved(error_log)
```

#### 导出错误日志

```python
# 导出到文件
error_manager.export_to_file("./exports/error_log.json")

# 导出为字典
error_data = error_manager.export_to_dict()
```

#### 错误日志格式

```json
{
  "timestamp": "2025-12-28T10:30:45.123456",
  "error_type": "TimeoutError",
  "error_message": "Request timeout after 30 seconds",
  "context": {
    "operation": "grade_page",
    "page_index": 42,
    "batch_id": "batch_123"
  },
  "stack_trace": "Traceback (most recent call last):\n  File ...",
  "batch_id": "batch_123",
  "page_index": 42,
  "question_id": "Q1",
  "retry_count": 2,
  "resolved": false
}
```

## 集成示例

### 在 LLMReasoningClient 中使用

```python
from src.utils.error_handling import with_retry, get_error_manager

class LLMReasoningClient:
    @with_retry(max_retries=3, initial_delay=1.0)
    async def _call_vision_api(self, image_b64: str, prompt: str) -> str:
        """调用视觉 API（带重试）"""
        try:
            message = HumanMessage(content=[...])
            response = await self.llm.ainvoke([message])
            return self._extract_text_from_response(response.content)
        except Exception as e:
            # 记录错误
            error_manager = get_error_manager()
            error_manager.add_error(
                exc=e,
                context={
                    "function": "_call_vision_api",
                    "prompt_length": len(prompt),
                }
            )
            raise
```

### 在批改节点中使用

```python
from src.utils.error_handling import execute_batch_with_isolation, get_error_manager

async def grade_batch_node(state):
    """批改批次节点（带错误隔离）"""
    
    async def grade_single_page(page_data):
        page_idx, image = page_data
        # 批改逻辑
        return await reasoning_client.grade_page(image, ...)
    
    # 使用错误隔离批量处理
    page_data_list = list(zip(page_indices, images))
    isolated_results = await execute_batch_with_isolation(
        func=grade_single_page,
        items=page_data_list,
        error_log_context={"batch_id": batch_id},
    )
    
    # 收集结果
    page_results = []
    for result in isolated_results:
        if result.is_success():
            page_results.append(result.get_result())
        else:
            # 失败页面也记录
            page_results.append({
                "status": "failed",
                "error": str(result.get_error()),
            })
    
    return {"grading_results": page_results}
```

### 在导出节点中使用

```python
async def export_node(state):
    """导出节点（带部分结果保存）"""
    
    # 检查失败页面
    failed_pages = [r for r in grading_results if r.get("status") == "failed"]
    has_failures = len(failed_pages) > 0
    
    if has_failures:
        # 保存部分结果
        filename = f"partial_result_{batch_id}_{timestamp}.json"
        logger.warning(f"保存部分结果: {filename}")
    
    # 导出错误日志
    error_manager = get_error_manager()
    batch_errors = error_manager.get_errors_by_batch(batch_id)
    if batch_errors:
        error_log_file = f"error_log_{batch_id}_{timestamp}.json"
        error_manager.export_to_file(error_log_file)
```

## 最佳实践

### 1. 重试策略

- **API 调用**: 使用 `@with_retry` 装饰器，最多重试3次
- **数据库操作**: 使用较短的重试延迟（initial_delay=0.5）
- **文件操作**: 通常不需要重试，直接失败

### 2. 错误隔离

- **批量操作**: 始终使用 `execute_batch_with_isolation`
- **关键路径**: 不要隔离关键初始化步骤
- **日志记录**: 每个隔离的错误都应记录到错误管理器

### 3. 部分结果保存

- **长时间任务**: 定期保存中间结果
- **大批量处理**: 每处理N个项目保存一次
- **失败检测**: 检测到失败时立即保存部分结果

### 4. 错误日志

- **上下文信息**: 记录足够的上下文以便调试
- **敏感信息**: 不要在日志中记录密钥、密码等敏感信息
- **定期清理**: 定期清理已解决的错误日志
- **导出频率**: 每个批次结束时导出错误日志

## 配置

### 环境变量

```bash
# 导出目录
EXPORT_DIR=./exports

# 重试配置
GRADING_MAX_RETRIES=3
GRADING_RETRY_DELAY=1.0

# 批次配置
GRADING_BATCH_SIZE=10
GRADING_MAX_WORKERS=5
```

### 代码配置

```python
from src.utils.error_handling import RetryConfig

# 自定义重试配置
custom_config = RetryConfig(
    max_retries=5,
    initial_delay=0.5,
    max_delay=30.0,
    exponential_base=1.5,
    jitter=True,
)
```

## 监控和调试

### 查看错误统计

```python
error_manager = get_error_manager()

# 总错误数
total_errors = len(error_manager.error_logs)

# 未解决错误数
unresolved_count = len(error_manager.get_unresolved_errors())

# 按批次统计
batch_errors = error_manager.get_errors_by_batch("batch_123")
print(f"批次 batch_123 有 {len(batch_errors)} 个错误")
```

### 分析错误类型

```python
from collections import Counter

error_types = Counter(log.error_type for log in error_manager.error_logs)
print("错误类型分布:", error_types)

# 输出示例:
# 错误类型分布: Counter({
#     'TimeoutError': 15,
#     'JSONDecodeError': 8,
#     'ValueError': 3
# })
```

### 导出完整报告

```python
# 导出所有错误日志
error_manager.export_to_file("./reports/all_errors.json")

# 导出特定批次的错误
batch_errors = error_manager.get_errors_by_batch("batch_123")
import json
with open("./reports/batch_123_errors.json", "w") as f:
    json.dump([log.to_dict() for log in batch_errors], f, indent=2)
```

## 故障排查

### 问题：重试次数过多

**症状**: API 调用重试多次仍然失败

**解决方案**:
1. 检查 API 密钥是否有效
2. 检查网络连接
3. 增加重试延迟: `initial_delay=2.0`
4. 检查 API 配额限制

### 问题：错误日志过大

**症状**: 错误日志文件占用大量磁盘空间

**解决方案**:
1. 定期清理已解决的错误: `error_manager.clear()`
2. 只记录关键错误
3. 限制堆栈跟踪长度
4. 使用日志轮转

### 问题：部分结果丢失

**症状**: 批次失败后部分结果未保存

**解决方案**:
1. 确保使用 `execute_with_partial_save`
2. 检查导出目录权限
3. 增加保存频率
4. 使用事务性保存

## 性能考虑

### 重试开销

- 每次重试增加延迟（指数增长）
- 3次重试最多增加约7秒延迟
- 对于大批量任务，考虑减少重试次数

### 错误日志开销

- 每个错误记录约1-2KB内存
- 1000个错误约占用1-2MB内存
- 定期导出和清理以释放内存

### 隔离执行开销

- 每个隔离任务有轻微的包装开销
- 对于大批量任务（>1000），开销可忽略
- 并发执行可以抵消部分开销

## 参考

- [Design Document](../../.kiro/specs/grading-workflow-optimization/design.md)
- [Requirements Document](../../.kiro/specs/grading-workflow-optimization/requirements.md)
- [Tasks Document](../../.kiro/specs/grading-workflow-optimization/tasks.md)
