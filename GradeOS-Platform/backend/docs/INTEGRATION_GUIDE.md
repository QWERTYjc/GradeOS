# 架构深度融合集成指南

本文档说明如何使用更新后的组件，这些组件已集成了增强型连接池、检查点器、缓存和 API 服务。

## 更新概述

### 1. GradingAgent（批改智能体）

**更新内容：**
- 使用 `EnhancedPostgresCheckpointer` 替代原有的 PostgresSaver
- 支持 Temporal Activity 心跳回调
- 支持增量状态存储和数据压缩

**使用示例：**

```python
from src.agents.grading_agent import GradingAgent
from src.services.llm_reasoning import LLMReasoningClient
from src.utils.enhanced_checkpointer import EnhancedPostgresCheckpointer
from src.utils.pool_manager import UnifiedPoolManager

# 初始化连接池管理器
pool_manager = await UnifiedPoolManager.get_instance()
await pool_manager.initialize()

# 创建增强型检查点器（带心跳回调）
def heartbeat_callback(stage: str, progress: float):
    print(f"心跳: {stage} - {progress * 100}%")

checkpointer = EnhancedPostgresCheckpointer(
    pool_manager=pool_manager,
    heartbeat_callback=heartbeat_callback
)

# 创建批改智能体
reasoning_client = LLMReasoningClient(api_key="your-api-key")
agent = GradingAgent(
    reasoning_client=reasoning_client,
    checkpointer=checkpointer,
    heartbeat_callback=heartbeat_callback
)

# 运行批改
result = await agent.run(
    question_image="base64_image_data",
    rubric="评分细则",
    max_score=10.0,
    thread_id="workflow_run_id"  # 使用 workflow_run_id 作为 thread_id
)
```

### 2. ExamPaperWorkflow（试卷工作流）

**更新内容：**
- 继承 `EnhancedWorkflowMixin`
- 支持进度查询（Temporal Query）
- 在关键步骤自动更新进度

**使用示例：**

```python
from temporalio.client import Client

# 连接到 Temporal
client = await Client.connect("localhost:7233")

# 启动工作流
handle = await client.start_workflow(
    ExamPaperWorkflow.run,
    input_data,
    id=f"exam_paper_{submission_id}",
    task_queue="default-queue"
)

# 查询进度
progress = await handle.query(ExamPaperWorkflow.get_progress)
print(f"当前阶段: {progress['stage']}, 进度: {progress['percentage']}%")

# 查询 LangGraph 状态
langgraph_state = await handle.query(ExamPaperWorkflow.get_langgraph_state)
print(f"LangGraph 状态: {langgraph_state}")

# 等待完成
result = await handle.result()
```

### 3. CacheService（缓存服务）

**更新内容：**
- 使用 `MultiLayerCacheService` 作为底层实现
- 支持 Write-Through 策略
- 支持自动降级到 PostgreSQL
- 支持 Pub/Sub 缓存失效通知

**使用示例：**

```python
from src.services.cache import CacheService
from src.utils.pool_manager import UnifiedPoolManager

# 初始化连接池管理器
pool_manager = await UnifiedPoolManager.get_instance()
await pool_manager.initialize()

# 创建缓存服务（使用多层缓存）
cache_service = CacheService(
    pool_manager=pool_manager,
    use_multi_layer=True
)

# 查询缓存
result = await cache_service.get_cached_result(
    rubric_text="评分细则",
    image_data=image_bytes
)

# 缓存结果（Write-Through）
success = await cache_service.cache_result(
    rubric_text="评分细则",
    image_data=image_bytes,
    result=grading_result
)

# 失效缓存（带 Pub/Sub 通知）
deleted_count = await cache_service.invalidate_by_rubric("评分细则")
```

### 4. API 端点（增强服务）

**更新内容：**
- 添加 WebSocket 实时推送端点
- 添加分页查询端点
- 添加字段选择查询端点
- 添加慢查询监控端点

**使用示例：**

#### WebSocket 实时推送

```javascript
// 客户端代码
const ws = new WebSocket('ws://localhost:8000/ws/submissions/submission_id');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('状态更新:', data);
};

// 发送心跳
setInterval(() => {
    ws.send('ping');
}, 30000);
```

#### 分页查询

```bash
# 查询提交列表（分页、排序、过滤）
curl "http://localhost:8000/api/v1/submissions?page=1&page_size=20&sort_by=created_at&sort_order=desc&status=COMPLETED"
```

#### 字段选择查询

```bash
# 仅返回指定字段
curl "http://localhost:8000/api/v1/submissions/submission_id/fields?fields=submission_id,status,total_score"
```

#### 慢查询监控

```bash
# 查看慢查询记录
curl "http://localhost:8000/api/v1/admin/slow-queries?limit=100&min_duration_ms=500"

# 查看 API 统计
curl "http://localhost:8000/api/v1/admin/stats"
```

### 5. 数据库连接（统一连接池）

**更新内容：**
- 支持统一连接池管理器
- 自动回退到传统连接池
- 共享连接池资源

**使用示例：**

```python
from src.utils.database import db, init_db_pool

# 初始化（使用统一连接池）
await init_db_pool(use_unified_pool=True)

# 获取连接
async with db.connection() as conn:
    result = await conn.execute("SELECT * FROM submissions")
    rows = await result.fetchall()

# 使用事务
async with db.transaction() as conn:
    await conn.execute("INSERT INTO ...")
    await conn.execute("UPDATE ...")
    # 自动提交或回滚
```

## 配置环境变量

```bash
# PostgreSQL 配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_grading
DB_USER=postgres
DB_PASSWORD=postgres
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
DB_CONNECTION_TIMEOUT=5.0
DB_IDLE_TIMEOUT=300.0

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50
REDIS_CONNECTION_TIMEOUT=5.0

# 连接池配置
POOL_SHUTDOWN_TIMEOUT=30.0
```

## 健康检查

```python
from src.utils.pool_manager import UnifiedPoolManager

# 获取连接池管理器
pool_manager = await UnifiedPoolManager.get_instance()

# 执行健康检查
health = await pool_manager.health_check()
print(health)
# {
#     "healthy": True,
#     "postgresql": {"status": "healthy", "details": {...}},
#     "redis": {"status": "healthy", "details": {...}}
# }

# 获取连接池统计
stats = pool_manager.get_pool_stats()
print(stats)
```

## 迁移指南

### 从旧版本迁移

1. **更新 GradingAgent 初始化：**
   ```python
   # 旧版本
   agent = GradingAgent(reasoning_client, checkpointer=PostgresSaver(...))
   
   # 新版本
   agent = GradingAgent(
       reasoning_client, 
       checkpointer=EnhancedPostgresCheckpointer(...),
       heartbeat_callback=callback
   )
   ```

2. **更新 ExamPaperWorkflow：**
   ```python
   # 旧版本
   class ExamPaperWorkflow:
       pass
   
   # 新版本
   class ExamPaperWorkflow(EnhancedWorkflowMixin):
       def __init__(self):
           EnhancedWorkflowMixin.__init__(self)
   ```

3. **更新 CacheService 初始化：**
   ```python
   # 旧版本
   cache = CacheService(redis_client)
   
   # 新版本
   cache = CacheService(
       pool_manager=pool_manager,
       use_multi_layer=True
   )
   ```

4. **更新数据库初始化：**
   ```python
   # 旧版本
   await init_db_pool()
   
   # 新版本
   await init_db_pool(use_unified_pool=True)
   ```

## 注意事项

1. **向后兼容性：** 所有更新都保持向后兼容，可以选择性启用新功能。

2. **性能优化：** 使用统一连接池可以减少连接开销，提高并发性能。

3. **监控告警：** 启用慢查询监控和性能告警，及时发现性能问题。

4. **优雅降级：** Redis 故障时自动降级到 PostgreSQL，保证服务可用性。

5. **进度查询：** 使用 Temporal Query 实时查询工作流进度，提升用户体验。

## 故障排查

### 连接池初始化失败

```python
# 检查连接池状态
pool_manager = await UnifiedPoolManager.get_instance()
if not pool_manager.is_initialized:
    print("连接池未初始化")
    await pool_manager.initialize()
```

### Redis 连接失败

```python
# 检查 Redis 健康状态
health = await pool_manager.health_check()
if health["redis"]["status"] != "healthy":
    print(f"Redis 不健康: {health['redis']['details']}")
```

### 慢查询问题

```bash
# 查看慢查询记录
curl "http://localhost:8000/api/v1/admin/slow-queries"

# 分析慢查询原因
# 1. 检查数据库索引
# 2. 优化查询语句
# 3. 增加缓存
```

## 下一步

1. 运行集成测试验证功能
2. 配置监控和告警
3. 优化性能参数
4. 部署到生产环境

更多信息请参考：
- [设计文档](.kiro/specs/architecture-deep-integration/design.md)
- [需求文档](.kiro/specs/architecture-deep-integration/requirements.md)
- [任务列表](.kiro/specs/architecture-deep-integration/tasks.md)
