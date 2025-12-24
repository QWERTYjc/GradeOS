# 根本原因分析与最终解决方案

## 问题根源

### 1. Windows 事件循环不兼容
```
Psycopg cannot use the 'ProactorEventLoop' to run in async mode
```

**原因**: 
- Windows 默认使用 `ProactorEventLoop`
- Psycopg（PostgreSQL 异步驱动）需要 `SelectorEventLoop`
- 事件循环策略设置太晚，数据库连接池已经初始化

### 2. 结果数据丢失的真正原因

不是代码逻辑问题，而是**异步任务执行异常**：

1. 数据库连接失败导致系统降级到离线模式
2. 离线模式下，结果应该保存在内存 `batch_states` 中
3. 但由于事件循环问题，`stream_langgraph_progress` 异步任务可能：
   - 提前终止
   - 异常被静默捕获
   - 事件流处理不完整

### 3. 为什么工作流程能完成？

- LangGraph 本身不依赖数据库
- LangGraph 使用自己的事件循环
- 批改逻辑（Gemini API 调用）正常执行
- 只是结果保存环节出问题

## 最终解决方案

### 方案 A: 完全禁用数据库（最简单）

既然数据库连接失败，而系统已经在离线模式下运行，直接禁用数据库尝试：

**步骤 1**: 修改 `src/utils/pool_manager.py`

```python
async def initialize(self):
    """初始化连接池"""
    # 检查是否强制离线模式
    if os.getenv("OFFLINE_MODE", "false").lower() == "true":
        logger.info("离线模式：跳过数据库连接")
        return
    
    # 原有的初始化逻辑...
```

**步骤 2**: 在 `.env` 中设置

```
OFFLINE_MODE=true
```

### 方案 B: 修复事件循环（正确方式）

问题是事件循环策略设置太晚。需要在 uvicorn 启动时就设置：

**方法 1**: 使用启动脚本

```python
# start_server.py
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8001
    )
```

然后运行: `python start_server.py`

**方法 2**: 修改 uvicorn 配置

```python
# uvicorn_config.py
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

然后运行: `uvicorn src.api.main:app --port 8001 --loop asyncio`

### 方案 C: 简化结果保存（绕过问题）

不依赖事件流，直接在完成后轮询状态：

```python
# 在 submit_batch 中
async def poll_and_save_results(batch_id: str, run_id: str):
    """轮询并保存结果"""
    while True:
        await asyncio.sleep(5)
        try:
            status = await orchestrator.get_status(run_id)
            if status.status == RunStatus.COMPLETED:
                # 从 orchestrator 获取最终状态
                # 注意：需要在 orchestrator 中实现 get_final_output 方法
                final_output = await orchestrator.get_final_output(run_id)
                
                batch_states[batch_id] = {
                    "status": "completed",
                    "final_state": final_output,
                    "completed_at": datetime.now().isoformat()
                }
                logger.info(f"结果已保存: batch_id={batch_id}")
                break
            elif status.status in [RunStatus.FAILED, RunStatus.CANCELLED]:
                break
        except Exception as e:
            logger.error(f"轮询失败: {e}")
            break

# 启动轮询任务
asyncio.create_task(poll_and_save_results(batch_id, run_id))
```

## 推荐方案

**立即实施方案 A**（完全禁用数据库），因为：
1. 最简单，风险最低
2. 系统已经在离线模式下运行
3. 可以快速验证是否解决问题

**长期实施方案 B**（修复事件循环），因为：
1. 这是正确的解决方案
2. 未来需要数据库时不会有问题
3. 符合最佳实践

**备选方案 C**（简化结果保存），如果方案 A 和 B 都不行：
1. 完全绕过事件流问题
2. 更可靠，但需要额外的轮询开销
3. 可以作为临时解决方案

## 验证步骤

实施方案后，验证以下内容：

1. **日志中无 Psycopg 错误**
2. **批改完成后 `results` 不为 `null`**
3. **可以通过 `/batch/results/{batch_id}` 获取结果**
4. **结果包含**:
   - 评分细则解析（19题/105分）
   - 学生识别结果
   - 真实评分（非0分）

## 下一步

1. 立即实施方案 A
2. 重新测试
3. 如果成功，记录结果
4. 如果失败，尝试方案 C
