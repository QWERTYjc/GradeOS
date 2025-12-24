# 编排器模块

提供工作流编排的抽象层和 LangGraph 实现。

## 文件结构

- `base.py` - 编排器抽象接口
- `langgraph_orchestrator.py` - LangGraph 编排器实现

## 使用方式

```python
from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator
from src.graphs import create_exam_paper_graph

# 创建编排器
orchestrator = LangGraphOrchestrator(db_pool=db_pool)

# 注册 Graph
orchestrator.register_graph("exam_paper", create_exam_paper_graph())

# 启动 run
run_id = await orchestrator.start_run(
    graph_name="exam_paper",
    payload={"submission_id": "xxx", ...}
)

# 查询状态
status = await orchestrator.get_status(run_id)

# 发送事件（用于人工审核）
await orchestrator.send_event(run_id, "review", {"action": "APPROVE"})
```

## 核心接口

- `start_run(graph_name, payload)` - 启动 Graph 执行
- `get_status(run_id)` - 查询执行状态
- `cancel(run_id)` - 取消执行
- `retry(run_id)` - 重试失败的执行
- `send_event(run_id, event_type, data)` - 发送事件（用于 resume）
