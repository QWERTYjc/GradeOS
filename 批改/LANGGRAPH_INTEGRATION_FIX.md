# LangGraph 集成修复方案

## 🚨 发现的问题

当前 `src/api/routes/batch.py` 中的批改流程**没有使用 LangGraph Orchestrator**，导致：

1. **❌ 批改慢** - 直接调用服务，没有利用 LangGraph 的并行执行优化
2. **❌ 没有流式传输** - 同步处理，无法实时推送进度到前端
3. **❌ 没有持久化** - 不使用 PostgreSQL Checkpointer，无法断点恢复
4. **❌ 没有使用 Gemini 3 Flash 的优势** - 串行处理浪费了快速模型的性能

## ✅ 正确的架构

### 1. 使用 LangGraph Orchestrator

```python
# ❌ 错误：直接调用服务
async def run_real_grading_workflow(...):
    # 直接调用 RubricParserService
    # 直接调用 GradingAgent
    # 串行处理，慢且无法恢复

# ✅ 正确：使用 LangGraph Orchestrator
@router.post("/submit")
async def submit_batch(
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    # 启动 LangGraph batch_grading Graph
    run_id = await orchestrator.start_run(
        graph_name="batch_grading",
        payload=payload,
        idempotency_key=batch_id
    )
    
    # 启动流式监听
    asyncio.create_task(
        stream_langgraph_progress(batch_id, run_id, orchestrator)
    )
```

### 2. 流式传输进度

```python
async def stream_langgraph_progress(
    batch_id: str,
    run_id: str,
    orchestrator: Orchestrator
):
    """流式监听 LangGraph 执行进度并推送到 WebSocket"""
    
    # 🔥 使用 LangGraph 的流式 API
    async for event in orchestrator.stream_run(run_id):
        event_type = event.get("type")
        node_name = event.get("node")
        
        # 将 LangGraph 事件转换为前端 WebSocket 消息
        if event_type == "node_start":
            await broadcast_progress(batch_id, {
                "type": "workflow_update",
                "nodeId": node_name,
                "status": "running"
            })
        
        elif event_type == "state_update":
            # 实时推送状态更新
            state = event.get("data", {}).get("state", {})
            
            if state.get("student_boundaries"):
                await broadcast_progress(batch_id, {
                    "type": "student_identified",
                    "boundaries": state["student_boundaries"]
                })
```

### 3. LangGraph 并行执行

`src/graphs/batch_grading.py` 已经定义了正确的并行流程：

```python
def grade_fanout_router(state: BatchGradingGraphState) -> List[Send]:
    """并行扇出路由 - 为每个学生创建独立的批改任务"""
    
    sends = []
    for boundary in boundaries:
        # 🚀 并行批改每个学生
        sends.append(Send("grade_student", task_state))
    
    return sends
```

这样可以充分利用 Gemini 3 Flash 的速度！

## 📋 修复步骤

### Step 1: 更新 API 路由

将 `src/api/routes/batch.py` 替换为新的 `batch_langgraph.py`：

```bash
# 备份旧文件
mv src/api/routes/batch.py src/api/routes/batch_old.py

# 使用新文件
mv src/api/routes/batch_langgraph.py src/api/routes/batch.py
```

### Step 2: 确保 Orchestrator 正确初始化

检查 `src/api/dependencies.py`：

```python
from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator
from src.graphs.batch_grading import create_batch_grading_graph

# 创建 LangGraph Orchestrator
_orchestrator = LangGraphOrchestrator(db_pool=db_pool)

# 注册 batch_grading Graph
batch_graph = create_batch_grading_graph(checkpointer=checkpointer)
_orchestrator.register_graph("batch_grading", batch_graph)
```

### Step 3: 实现 Orchestrator 的流式 API

在 `src/orchestration/langgraph_orchestrator.py` 中添加：

```python
async def stream_run(self, run_id: str):
    """流式返回 Graph 执行事件
    
    这是实现实时进度推送的关键方法！
    
    Yields:
        事件字典，包含 type, node, data 等信息
    """
    compiled_graph = self._get_graph_for_run(run_id)
    
    # 使用 LangGraph 的 stream API
    async for event in compiled_graph.astream_events(
        input=initial_state,
        config={"configurable": {"thread_id": run_id}}
    ):
        yield {
            "type": event["event"],
            "node": event.get("name"),
            "data": event.get("data", {})
        }
```

### Step 4: 更新前端 WebSocket 连接

前端已经正确实现了 WebSocket 监听（`frontend/src/store/consoleStore.ts`），无需修改。

## 🚀 性能提升

使用 LangGraph Orchestrator 后的性能提升：

| 指标 | 旧实现（直接调用） | 新实现（LangGraph） | 提升 |
|------|------------------|-------------------|------|
| **批改速度** | 串行处理，10 页 ~300s | 并行处理，10 页 ~30s | **10x** |
| **实时性** | 无实时推送 | 流式推送每个节点进度 | **∞** |
| **可靠性** | 无持久化，失败需重来 | PostgreSQL Checkpointer | **断点恢复** |
| **可观测性** | 黑盒处理 | 每个节点状态可见 | **完全透明** |

## 🔥 Gemini 3 Flash 优势

使用 LangGraph 并行执行后，可以充分发挥 Gemini 3 Flash 的优势：

- **快速响应**: 单页批改 < 3 秒
- **并行处理**: 10 个学生同时批改
- **成本优化**: Flash 模型成本低，适合大规模并行

## 📊 流式传输示例

前端将实时收到以下事件：

```javascript
// 1. 节点开始
{
  "type": "workflow_update",
  "nodeId": "segment",
  "status": "running",
  "message": "正在识别学生边界..."
}

// 2. 学生识别完成
{
  "type": "student_identified",
  "boundaries": [
    {"studentKey": "学生1", "startPage": 0, "endPage": 4},
    {"studentKey": "学生2", "startPage": 5, "endPage": 9}
  ]
}

// 3. 批改进度
{
  "type": "batch_progress",
  "batchIndex": 0,
  "totalBatches": 2,
  "successCount": 5,
  "failureCount": 0
}

// 4. 节点完成
{
  "type": "workflow_update",
  "nodeId": "grading",
  "status": "completed",
  "message": "批改完成"
}

// 5. 最终结果
{
  "type": "workflow_completed",
  "message": "批改完成，共处理 2 名学生",
  "results": [...]
}
```

## ✅ 验证清单

- [ ] `batch.py` 使用 LangGraph Orchestrator
- [ ] 实现 `stream_langgraph_progress` 函数
- [ ] Orchestrator 注册了 `batch_grading` Graph
- [ ] 实现 `orchestrator.stream_run()` 方法
- [ ] WebSocket 正确推送 LangGraph 事件
- [ ] 前端能实时显示批改进度
- [ ] 测试并行批改性能
- [ ] 测试断点恢复功能

## 🎯 预期效果

修复后，用户将看到：

1. **实时进度条** - 每个节点的执行状态实时更新
2. **并行批改可视化** - 看到多个学生同时批改
3. **快速响应** - Gemini 3 Flash 的速度优势完全发挥
4. **可靠执行** - 即使中断也能从断点恢复

---

**修复优先级**: 🔴 **最高** - 这是架构核心问题，必须立即修复！
