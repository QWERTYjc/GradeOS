# Temporal → LangGraph 迁移映射表

生成时间：2025-12-24

---

## 1. 核心概念映射

| Temporal 概念 | LangGraph 等效实现 | 实现方式 | 备注 |
|--------------|-------------------|---------|------|
| **Workflow** | **Graph** | `StateGraph` + `compile()` | 工作流定义变为图定义 |
| **Activity** | **Node** | 图节点函数 | 纯函数或工具调用 |
| **Worker** | **Graph Runner** | `graph.invoke()` / `graph.stream()` | 后台执行器 |
| **Signal** | **interrupt() + resume()** | `interrupt()` 暂停，`Command.resume()` 恢复 | 人工介入点 |
| **Query** | **读取持久化 State** | `checkpointer.get()` | 查询检查点状态 |
| **Retry** | **节点级重试 + 失败分流** | 节点内部 try-catch + 重试计数 | 重试耗尽后走补偿分支 |
| **Timeout** | **节点内部超时控制** | `asyncio.wait_for()` | 超时后抛出异常或走降级分支 |
| **Parallel** | **fanout 子图 + 聚合节点** | `Send` API 或并行节点 | 并行执行多个分支 |
| **Schedule** | **cron 触发 + start_run** | 系统 cron 或 LangSmith Deployment cron | 定时触发图执行 |
| **History/Audit** | **checkpoints + run/attempt 表** | PostgreSQL 存储检查点和执行记录 | 审计追踪 |
| **task_queue** | **无需** | 直接调用，无队列概念 | LangGraph 无队列 |
| **namespace** | **无需** | 通过 `thread_id` 隔离 | 每个 run 独立 thread_id |
| **workflow_id** | **thread_id** | 唯一标识符 | 用于检查点持久化 |
| **run_id** | **thread_id** | 唯一标识符 | 与 workflow_id 一致 |
| **Child Workflow** | **子图调用** | `graph.invoke()` 嵌套调用 | 或使用 `Send` API |
| **Heartbeat** | **无需** | LangGraph 无心跳机制 | 依赖检查点持久化 |

---

## 2. Workflow → Graph 映射

### 2.1 ExamPaperWorkflow

**Temporal 实现**:
```python
@workflow.defn
class ExamPaperWorkflow(EnhancedWorkflowMixin):
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> ExamPaperResult:
        # 1. 文档分割
        result = await workflow.execute_activity("segment_document_activity", ...)
        
        # 2. 扇出子工作流
        handles = []
        for region in all_regions:
            handle = await workflow.start_child_workflow(QuestionGradingChildWorkflow, ...)
            handles.append(handle)
        
        # 3. 扇入聚合
        results = [await h.result() for h in handles]
        
        # 4. 人工审核（Signal）
        if needs_review:
            await workflow.wait_condition(lambda: self._review_received)
        
        # 5. 持久化
        await workflow.execute_activity("persist_results_activity", ...)
        
        return exam_result
```

**LangGraph 实现**:
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

class ExamPaperState(TypedDict):
    submission_id: str
    file_paths: List[str]
    segmentation_results: List[SegmentationResult]
    grading_results: List[GradingResult]
    needs_review: bool
    review_action: Optional[str]
    final_result: Optional[ExamPaperResult]
    progress: Dict[str, Any]
    errors: List[str]

def segment_node(state: ExamPaperState) -> ExamPaperState:
    """文档分割节点"""
    # 调用 LayoutAnalysisService
    segmentation_results = []
    for file_path in state["file_paths"]:
        result = layout_service.segment(file_path)
        segmentation_results.append(result)
    
    return {
        **state,
        "segmentation_results": segmentation_results,
        "progress": {"stage": "segmentation_complete", "percentage": 20.0}
    }

def grade_fanout_node(state: ExamPaperState) -> ExamPaperState:
    """批改扇出节点（并行）"""
    # 使用 Send API 并行批改所有题目
    from langgraph.constants import Send
    
    regions = []
    for seg_result in state["segmentation_results"]:
        regions.extend(seg_result.regions)
    
    # 返回 Send 命令列表
    return [
        Send("grade_question_node", {"region": region})
        for region in regions
    ]

def grade_question_node(state: Dict) -> Dict:
    """单题批改节点"""
    region = state["region"]
    # 调用 GradingAgent
    result = grading_agent.run(
        question_image=region.image_data,
        rubric=state.get("rubric", ""),
        max_score=region.max_score
    )
    return {"grading_result": result}

def aggregate_node(state: ExamPaperState) -> ExamPaperState:
    """聚合节点"""
    # 收集所有批改结果
    total_score = sum(r.score for r in state["grading_results"])
    min_confidence = min(r.confidence for r in state["grading_results"])
    
    needs_review = min_confidence < 0.75
    
    return {
        **state,
        "needs_review": needs_review,
        "progress": {"stage": "aggregation_complete", "percentage": 75.0}
    }

def review_interrupt_node(state: ExamPaperState) -> ExamPaperState:
    """人工审核中断节点"""
    if state["needs_review"]:
        # 触发中断，等待外部输入
        from langgraph.types import interrupt
        review_data = interrupt("需要人工审核")
        
        # 恢复后，review_data 包含审核结果
        return {
            **state,
            "review_action": review_data.get("action"),
            "progress": {"stage": "review_complete", "percentage": 85.0}
        }
    
    return state

def persist_node(state: ExamPaperState) -> ExamPaperState:
    """持久化节点"""
    # 调用 Repository 保存结果
    grading_result_repo.save(state["grading_results"])
    
    final_result = ExamPaperResult(
        submission_id=state["submission_id"],
        total_score=sum(r.score for r in state["grading_results"]),
        question_results=state["grading_results"]
    )
    
    return {
        **state,
        "final_result": final_result,
        "progress": {"stage": "completed", "percentage": 100.0}
    }

# 构建图
graph = StateGraph(ExamPaperState)

# 添加节点
graph.add_node("segment", segment_node)
graph.add_node("grade_fanout", grade_fanout_node)
graph.add_node("grade_question", grade_question_node)
graph.add_node("aggregate", aggregate_node)
graph.add_node("review_interrupt", review_interrupt_node)
graph.add_node("persist", persist_node)

# 添加边
graph.set_entry_point("segment")
graph.add_edge("segment", "grade_fanout")
graph.add_conditional_edges(
    "grade_fanout",
    lambda state: "aggregate" if all_done(state) else "grade_question"
)
graph.add_edge("grade_question", "aggregate")
graph.add_edge("aggregate", "review_interrupt")
graph.add_edge("review_interrupt", "persist")
graph.add_edge("persist", END)

# 编译图（带检查点）
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
compiled_graph = graph.compile(checkpointer=checkpointer)
```

**关键差异**:
1. **无装饰器**: LangGraph 不需要 `@workflow.defn`，直接定义函数
2. **State 驱动**: 所有节点通过 State 传递数据
3. **interrupt() 替代 Signal**: 人工介入用 `interrupt()` + `resume()`
4. **Checkpointer 替代 History**: 持久化状态到 PostgreSQL

---

### 2.2 BatchGradingWorkflow

**映射策略**:
- **学生识别** → 独立节点
- **子工作流扇出** → `Send` API 并行调用 ExamPaperGraph
- **结果聚合** → 聚合节点

**LangGraph 实现**:
```python
class BatchGradingState(TypedDict):
    batch_id: str
    file_paths: List[str]
    student_groups: Dict[str, List[int]]
    student_results: Dict[str, ExamPaperResult]
    errors: List[str]

def identify_students_node(state: BatchGradingState) -> BatchGradingState:
    """学生识别节点"""
    student_groups = student_identification_service.identify(state["file_paths"])
    return {**state, "student_groups": student_groups}

def grade_students_fanout_node(state: BatchGradingState):
    """学生批改扇出节点"""
    from langgraph.constants import Send
    
    return [
        Send("grade_student_node", {
            "student_key": student_key,
            "page_indices": page_indices,
            "file_paths": state["file_paths"]
        })
        for student_key, page_indices in state["student_groups"].items()
    ]

def grade_student_node(state: Dict) -> Dict:
    """单学生批改节点（调用 ExamPaperGraph）"""
    student_file_paths = [state["file_paths"][i] for i in state["page_indices"]]
    
    # 调用 ExamPaperGraph
    result = exam_paper_graph.invoke({
        "submission_id": f"{state['batch_id']}_{state['student_key']}",
        "file_paths": student_file_paths
    })
    
    return {"student_key": state["student_key"], "result": result}

# 构建图
batch_graph = StateGraph(BatchGradingState)
batch_graph.add_node("identify_students", identify_students_node)
batch_graph.add_node("grade_students_fanout", grade_students_fanout_node)
batch_graph.add_node("grade_student", grade_student_node)
batch_graph.add_node("aggregate", aggregate_batch_results_node)

batch_graph.set_entry_point("identify_students")
batch_graph.add_edge("identify_students", "grade_students_fanout")
batch_graph.add_conditional_edges("grade_students_fanout", ...)
batch_graph.add_edge("grade_student", "aggregate")
batch_graph.add_edge("aggregate", END)

compiled_batch_graph = batch_graph.compile(checkpointer=checkpointer)
```

---

### 2.3 RuleUpgradeWorkflow

**映射策略**:
- **规则挖掘** → 节点
- **补丁生成** → 节点（循环处理多个 pattern）
- **回归测试** → 节点（循环处理多个 patch）
- **灰度发布** → 节点
- **监控** → 节点（定时检查）
- **回滚/全量** → 条件分支

**LangGraph 实现**:
```python
class RuleUpgradeState(TypedDict):
    upgrade_id: str
    patterns: List[Dict]
    patches: List[Dict]
    tested_patches: List[Dict]
    deployed_patches: List[Dict]
    errors: List[str]

def mine_patterns_node(state: RuleUpgradeState) -> RuleUpgradeState:
    """规则挖掘节点"""
    patterns = rule_miner.analyze_overrides(...)
    return {**state, "patterns": patterns}

def generate_patches_node(state: RuleUpgradeState) -> RuleUpgradeState:
    """补丁生成节点"""
    patches = []
    for pattern in state["patterns"]:
        patch = patch_generator.generate_patch(pattern)
        if patch:
            patches.append(patch)
    return {**state, "patches": patches}

def test_patches_node(state: RuleUpgradeState) -> RuleUpgradeState:
    """回归测试节点"""
    tested_patches = []
    for patch in state["patches"]:
        result = regression_tester.run_regression(patch, eval_set_id)
        if regression_tester.is_improvement(result):
            tested_patches.append({"patch": patch, "result": result})
    return {**state, "tested_patches": tested_patches}

def deploy_patches_node(state: RuleUpgradeState) -> RuleUpgradeState:
    """灰度发布节点"""
    deployed_patches = []
    for item in state["tested_patches"]:
        deployment_id = patch_deployer.deploy_canary(item["patch"], traffic_percentage=0.1)
        if deployment_id:
            deployed_patches.append({"patch": item["patch"], "deployment_id": deployment_id})
    return {**state, "deployed_patches": deployed_patches}

# 构建图
rule_upgrade_graph = StateGraph(RuleUpgradeState)
rule_upgrade_graph.add_node("mine_patterns", mine_patterns_node)
rule_upgrade_graph.add_node("generate_patches", generate_patches_node)
rule_upgrade_graph.add_node("test_patches", test_patches_node)
rule_upgrade_graph.add_node("deploy_patches", deploy_patches_node)

rule_upgrade_graph.set_entry_point("mine_patterns")
rule_upgrade_graph.add_edge("mine_patterns", "generate_patches")
rule_upgrade_graph.add_edge("generate_patches", "test_patches")
rule_upgrade_graph.add_edge("test_patches", "deploy_patches")
rule_upgrade_graph.add_edge("deploy_patches", END)

compiled_rule_upgrade_graph = rule_upgrade_graph.compile(checkpointer=checkpointer)
```

---

## 3. Activity → Node 映射

| Temporal Activity | LangGraph Node | 实现方式 |
|------------------|----------------|---------|
| `segment_document_activity` | `segment_node` | 调用 `LayoutAnalysisService` |
| `grade_question_activity` | `grade_question_node` | 调用 `GradingAgent.run()` |
| `notify_teacher_activity` | `notify_node` | 调用通知服务 |
| `persist_results_activity` | `persist_node` | 调用 Repository |
| `detect_student_boundaries_activity` | `detect_boundaries_node` | 调用 `StudentBoundaryDetector` |
| `push_stream_event_activity` | `push_event_node` | 调用 `StreamingService` |
| `mine_failure_patterns_activity` | `mine_patterns_node` | 调用 `RuleMiner` |
| `generate_patch_activity` | `generate_patch_node` | 调用 `PatchGenerator` |
| `run_regression_test_activity` | `test_patch_node` | 调用 `RegressionTester` |
| `deploy_patch_canary_activity` | `deploy_patch_node` | 调用 `PatchDeployer` |

**关键差异**:
- **无装饰器**: LangGraph 节点是普通函数，无需 `@activity.defn`
- **无依赖注入**: 节点内部直接实例化服务（或通过闭包传递）
- **无重试配置**: 重试逻辑在节点内部实现

---

## 4. Signal/Query → interrupt/resume + State 查询

### 4.1 Signal 映射

| Temporal Signal | LangGraph 等效 | 实现方式 |
|----------------|---------------|---------|
| `review_signal(action, override_data)` | `interrupt("review") + resume({"action": ..., "override_data": ...})` | 中断节点 + 外部调用 `graph.invoke(..., config={"configurable": {"thread_id": ...}})` 恢复 |
| `external_event(event)` | `interrupt("external_event") + resume(event)` | 同上 |
| `update_langgraph_state(state)` | 直接更新 State | 通过 `graph.update_state(...)` |

**示例**:
```python
# Temporal Signal
await handle.signal("review_signal", {"action": "APPROVE"})

# LangGraph 等效
# 1. 图执行到 interrupt 点
result = graph.invoke(input_data, config={"configurable": {"thread_id": run_id}})
# result 包含 interrupt 信息

# 2. 外部调用 resume
from langgraph.types import Command
graph.invoke(
    Command(resume={"action": "APPROVE"}),
    config={"configurable": {"thread_id": run_id}}
)
```

### 4.2 Query 映射

| Temporal Query | LangGraph 等效 | 实现方式 |
|---------------|---------------|---------|
| `get_progress()` | 读取 State | `checkpointer.get({"configurable": {"thread_id": run_id}})` |
| `get_langgraph_state()` | 读取 State | 同上 |
| `get_external_events()` | 读取 State | 同上 |

**示例**:
```python
# Temporal Query
progress = await handle.query("get_progress")

# LangGraph 等效
checkpoint = checkpointer.get({"configurable": {"thread_id": run_id}})
progress = checkpoint["channel_values"].get("progress", {})
```

---

## 5. Retry/Timeout → 节点级重试 + 失败分流

### 5.1 重试策略映射

**Temporal 实现**:
```python
await workflow.execute_activity(
    "grade_question_activity",
    ...,
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(minutes=1),
        maximum_attempts=3
    )
)
```

**LangGraph 实现**:
```python
def grade_question_node_with_retry(state: ExamPaperState) -> ExamPaperState:
    """带重试的批改节点"""
    max_attempts = 3
    attempt = 0
    backoff = 1.0
    
    while attempt < max_attempts:
        try:
            result = grading_agent.run(...)
            return {**state, "grading_result": result}
        except Exception as e:
            attempt += 1
            if attempt >= max_attempts:
                # 重试耗尽，走降级分支
                return {
                    **state,
                    "grading_result": None,
                    "errors": state.get("errors", []) + [str(e)],
                    "needs_fallback": True
                }
            
            # 指数退避
            time.sleep(backoff)
            backoff *= 2.0
            backoff = min(backoff, 60.0)
```

### 5.2 超时控制映射

**Temporal 实现**:
```python
await workflow.execute_activity(
    "grade_question_activity",
    ...,
    start_to_close_timeout=timedelta(minutes=2)
)
```

**LangGraph 实现**:
```python
import asyncio

async def grade_question_node_with_timeout(state: ExamPaperState) -> ExamPaperState:
    """带超时的批改节点"""
    try:
        result = await asyncio.wait_for(
            grading_agent.run(...),
            timeout=120.0  # 2 分钟
        )
        return {**state, "grading_result": result}
    except asyncio.TimeoutError:
        # 超时，走降级分支
        return {
            **state,
            "grading_result": None,
            "errors": state.get("errors", []) + ["Timeout"],
            "needs_fallback": True
        }
```

---

## 6. Parallel → fanout 子图 + Send API

### 6.1 子工作流并行映射

**Temporal 实现**:
```python
handles = []
for region in all_regions:
    handle = await workflow.start_child_workflow(
        QuestionGradingChildWorkflow,
        child_input,
        id=f"{submission_id}_{region.question_id}",
        task_queue="vision-compute-queue"
    )
    handles.append(handle)

results = [await h.result() for h in handles]
```

**LangGraph 实现**:
```python
from langgraph.constants import Send

def grade_fanout_node(state: ExamPaperState):
    """扇出节点"""
    return [
        Send("grade_question_node", {"region": region})
        for region in state["all_regions"]
    ]

def grade_question_node(state: Dict) -> Dict:
    """单题批改节点"""
    region = state["region"]
    result = grading_agent.run(...)
    return {"grading_result": result}

# 图定义
graph.add_node("grade_fanout", grade_fanout_node)
graph.add_node("grade_question", grade_question_node)
graph.add_node("aggregate", aggregate_node)

graph.add_conditional_edges(
    "grade_fanout",
    lambda state: [Send("grade_question", ...) for ...]
)
graph.add_edge("grade_question", "aggregate")
```

---

## 7. Schedule → cron 触发 + start_run

### 7.1 定时任务映射

**Temporal 实现**:
```python
@workflow.defn
class ScheduledRuleUpgradeWorkflow:
    @workflow.run
    async def run(self, input_data: Dict[str, Any]):
        while True:
            result = await workflow.execute_child_workflow(
                RuleUpgradeWorkflow,
                config,
                id=f"rule_upgrade_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_queue="default-queue"
            )
            await workflow.sleep(timedelta(days=1))
```

**LangGraph 实现（系统 cron）**:
```bash
# crontab
0 2 * * * python -m src.scripts.trigger_rule_upgrade
```

```python
# src/scripts/trigger_rule_upgrade.py
import asyncio
from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator

async def main():
    orchestrator = LangGraphOrchestrator()
    run_id = await orchestrator.start_run(
        graph_name="rule_upgrade",
        payload={"min_sample_count": 100, "time_window_days": 7}
    )
    print(f"Rule upgrade started: {run_id}")

if __name__ == "__main__":
    asyncio.run(main())
```

**LangGraph 实现（LangSmith Deployment cron）**:
```python
# 在 LangSmith Deployment 中配置 cron job
# 无需代码实现，通过 UI 配置
```

---

## 8. History/Audit → checkpoints + run/attempt 表

### 8.1 审计追踪映射

**Temporal 实现**:
- Temporal Server 自动记录所有事件到 History
- 通过 `handle.fetch_history()` 查询

**LangGraph 实现**:
```sql
-- 创建 run 表
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    graph_name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_data JSONB,
    output_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error TEXT
);

-- 创建 attempt 表
CREATE TABLE attempts (
    attempt_id SERIAL PRIMARY KEY,
    run_id TEXT REFERENCES runs(run_id),
    attempt_number INT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- 创建 checkpoint 表（由 PostgresSaver 自动管理）
-- 包含 thread_id, checkpoint_id, channel_values, metadata 等
```

```python
# 记录 run
async def start_run(graph_name: str, payload: Dict) -> str:
    run_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO runs (run_id, graph_name, status, input_data) VALUES ($1, $2, $3, $4)",
        run_id, graph_name, "running", json.dumps(payload)
    )
    return run_id

# 查询 run
async def get_run(run_id: str) -> Dict:
    row = await db.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
    return dict(row)
```

---

## 9. 迁移实施步骤

### Step 1: 抽象接口隔离（已完成）

- ✅ `src/orchestration/base.py`: `Orchestrator` 抽象接口
- ✅ `src/orchestration/temporal_orchestrator.py`: Temporal 实现

### Step 2: 实现 LangGraph Orchestrator

- ⏭️ `src/orchestration/langgraph_orchestrator.py`: LangGraph 实现
- ⏭️ 实现 `start_run`, `get_status`, `cancel`, `retry`, `list_runs`, `send_event`

### Step 3: 实现 LangGraph Graph

- ⏭️ `src/graphs/exam_paper_graph.py`: ExamPaperGraph
- ⏭️ `src/graphs/batch_grading_graph.py`: BatchGradingGraph
- ⏭️ `src/graphs/rule_upgrade_graph.py`: RuleUpgradeGraph

### Step 4: Durable Execution

- ⏭️ 配置 PostgresSaver
- ⏭️ 实现 run/attempt 表
- ⏭️ 实现崩溃恢复逻辑

### Step 5: 迁移正在运行的 Workflow

- ⏭️ 停止接入新 Temporal run
- ⏭️ Drain 现有 Temporal run
- ⏭️ 导出未完成列表
- ⏭️ 重新 start_run 到 LangGraph

### Step 6: 清理 Temporal

- ⏭️ 删除 Temporal SDK 依赖
- ⏭️ 删除 workflow/activity/worker 代码
- ⏭️ 删除 temporal server 容器/k8s 资源
- ⏭️ 删除环境变量配置
- ⏭️ 更新文档

---

## 10. 验收清单

### 10.1 功能验收

- [ ] API 触发 → 后台执行 → 状态可查
- [ ] 可取消/可重试
- [ ] 可恢复（模拟 worker 崩溃）
- [ ] 并行 fanout 场景（300 子任务）
- [ ] 重试退避、失败归因
- [ ] 人工介入路径（interrupt + resume）

### 10.2 性能验收

- [ ] 单题批改延迟 < 30 秒
- [ ] 并发 100 个 run 无性能下降
- [ ] Checkpointer 写入延迟 < 100ms

### 10.3 清理验收

- [ ] `temporal` 相关依赖完全清理
- [ ] 全文搜索 `temporal/workflow/activity/taskQueue/namespace` 结果为 0（除 changelog）
- [ ] 部署配置无 Temporal 引用
- [ ] 文档无 Temporal 引用

---

**映射表完成**
