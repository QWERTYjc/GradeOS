# LangGraph 架构整合方案

生成时间：2025-12-24

---

## 问题识别

发现仓库中存在**两套 LangGraph 架构**：

### 架构 A：现有架构（`src/graphs/`）
- `src/graphs/state.py` - 状态定义（GradingGraphState, BatchGradingGraphState, RuleUpgradeGraphState）
- `src/graphs/retry.py` - 重试策略（RetryConfig, with_retry, create_retryable_node）
- `src/graphs/nodes/segment.py` - 文档分割节点
- `src/graphs/nodes/grade.py` - 批改节点
- `src/graphs/nodes/persist.py` - 持久化节点
- `src/graphs/nodes/notify.py` - 通知节点

**特点**：
- 节点级重试已实现
- 状态定义完整
- 节点实现完整
- **缺少 Graph 编译和 Orchestrator 集成**

### 架构 B：新创建架构（Phase 1-2）
- `src/graphs/exam_paper_graph.py` - ExamPaperGraph（完整 Graph 定义 + 编译）
- `src/graphs/question_grading_graph.py` - QuestionGradingGraph（完整 Graph 定义 + 编译）
- `src/orchestration/langgraph_orchestrator.py` - LangGraph Orchestrator
- `alembic/versions/2025_12_24_1200-add_runs_table_for_langgraph.py` - runs 表

**特点**：
- 完整的 Graph 编译
- Orchestrator 实现
- 后台执行 + 状态查询
- Send API 并行扇出
- **与现有节点重复**

---

## 整合策略

### 方案：保留架构 A 的节点，补充架构 B 的 Graph 编译和 Orchestrator

**原则**：
1. **复用现有节点**：使用 `src/graphs/nodes/` 中的节点实现
2. **补充 Graph 定义**：创建 Graph 编译函数，组装现有节点
3. **保留 Orchestrator**：使用新创建的 `LangGraphOrchestrator`
4. **统一状态**：使用 `src/graphs/state.py` 中的状态定义

---

## 整合步骤

### Step 1: 删除重复的 Graph 文件

删除以下文件（与现有节点重复）：
- `src/graphs/exam_paper_graph.py`
- `src/graphs/question_grading_graph.py`

### Step 2: 创建 Graph 编译函数

创建 `src/graphs/exam_paper.py`（使用现有节点）：

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graphs.state import GradingGraphState
from src.graphs.nodes.segment import segment_node
from src.graphs.nodes.grade import grade_node
from src.graphs.nodes.persist import persist_node
from src.graphs.nodes.notify import notify_node


def create_exam_paper_graph(checkpointer: AsyncPostgresSaver) -> StateGraph:
    """创建试卷批改 Graph
    
    使用现有节点组装完整的批改流程。
    """
    graph = StateGraph(GradingGraphState)
    
    # 添加节点
    graph.add_node("segment", segment_node)
    graph.add_node("grade", grade_node)
    graph.add_node("persist", persist_node)
    graph.add_node("notify", notify_node)
    
    # 添加边
    graph.set_entry_point("segment")
    graph.add_edge("segment", "grade")
    graph.add_edge("grade", "persist")
    graph.add_edge("persist", "notify")
    graph.add_edge("notify", END)
    
    # 编译
    return graph.compile(checkpointer=checkpointer)
```

### Step 3: 更新 Orchestrator 注册

在 `src/orchestration/langgraph_orchestrator.py` 中注册 Graph：

```python
from src.graphs.exam_paper import create_exam_paper_graph

# 在初始化时注册
orchestrator = LangGraphOrchestrator(db_pool, checkpointer)
exam_paper_graph = create_exam_paper_graph(checkpointer)
orchestrator.register_graph("exam_paper", exam_paper_graph)
```

### Step 4: 增强现有节点（添加 Send API 并行）

修改 `src/graphs/nodes/grade.py`，添加并行批改能力：

```python
from langgraph.constants import Send

def create_grade_fanout_node():
    """创建批改扇出节点（使用 Send API）"""
    def fanout(state: GradingGraphState):
        segmentation_results = state.get("artifacts", {}).get("segmentation_results", [])
        
        # 为每个题目创建 Send 命令
        sends = []
        for page_result in segmentation_results:
            for region in page_result["regions"]:
                sends.append(Send("grade_single_question", {
                    "region": region,
                    "submission_id": state["submission_id"],
                    "rubric": state["rubric"]
                }))
        
        return sends
    
    return fanout
```

### Step 5: 更新 API 路由

修改 `src/api/routes/submissions.py`，使用 LangGraph Orchestrator：

```python
from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator

@router.post("/submissions")
async def create_submission(data: SubmissionCreate):
    # 使用 LangGraph Orchestrator
    orchestrator = get_langgraph_orchestrator()
    
    run_id = await orchestrator.start_run(
        graph_name="exam_paper",
        payload={
            "submission_id": submission_id,
            "exam_id": data.exam_id,
            "student_id": data.student_id,
            "file_paths": file_paths,
            "rubric": rubric
        }
    )
    
    return {"run_id": run_id, "status": "started"}
```

---

## 整合后的架构

```
src/
├── graphs/
│   ├── state.py                    # 状态定义（保留）
│   ├── retry.py                    # 重试策略（保留）
│   ├── nodes/                      # 节点实现（保留 + 增强）
│   │   ├── segment.py              # 文档分割节点
│   │   ├── grade.py                # 批改节点（增强：添加 Send API）
│   │   ├── persist.py              # 持久化节点
│   │   └── notify.py               # 通知节点
│   ├── exam_paper.py               # 新增：Graph 编译函数
│   ├── batch_grading.py            # 新增：批量批改 Graph
│   └── rule_upgrade.py             # 新增：规则升级 Graph
│
├── orchestration/
│   ├── base.py                     # Orchestrator 接口（保留）
│   ├── temporal_orchestrator.py    # Temporal 实现（保留，待删除）
│   └── langgraph_orchestrator.py   # LangGraph 实现（保留）
│
└── api/
    └── routes/
        └── submissions.py          # 修改：使用 LangGraph Orchestrator
```

---

## 迁移路径

### Phase 3（当前）：整合架构

1. ✅ **识别重复**：发现两套架构
2. ⏭️ **删除重复文件**：删除 `exam_paper_graph.py`, `question_grading_graph.py`
3. ⏭️ **创建 Graph 编译函数**：`src/graphs/exam_paper.py`
4. ⏭️ **增强现有节点**：添加 Send API 并行
5. ⏭️ **更新 API 路由**：切换到 LangGraph Orchestrator

### Phase 4：迁移批量 Workflow

6. ⏭️ **创建 BatchGradingGraph**：`src/graphs/batch_grading.py`
7. ⏭️ **集成 StudentBoundaryDetector**
8. ⏭️ **集成 StreamingService**

### Phase 5：清理 Temporal

9. ⏭️ **删除 Temporal 代码**
10. ⏭️ **验证清理完整性**

---

## 优势

1. **避免重复**：复用现有节点实现
2. **保持一致性**：统一使用 `GradingGraphState`
3. **渐进式迁移**：先整合，再扩展
4. **降低风险**：现有节点已测试，稳定性高

---

**下一步：执行整合步骤**
