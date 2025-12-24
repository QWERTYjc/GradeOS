# Temporal 足迹盘点报告

生成时间：2025-12-24
目标：彻底移除 Temporal 依赖，迁移到 LangGraph

---

## 1. Workflow 定义清单

### 1.1 主要 Workflow 文件

| 文件路径 | Workflow 类 | 业务语义 | 触发入口 | 关键特性 |
|---------|------------|---------|---------|---------|
| `src/workflows/exam_paper.py` | `ExamPaperWorkflow` | 试卷级批改 | API `/submissions` | Signal(review_signal), Query(get_progress), 子工作流扇出 |
| `src/workflows/batch_grading.py` | `BatchGradingWorkflow` | 批量多学生批改 | API `/batch` | 学生识别、子工作流并行 |
| `src/workflows/batch_grading_enhanced.py` | `EnhancedBatchGradingWorkflow` | 增强批量批改 | API `/batch` | 流式推送、固定分批、学生边界检测 |
| `src/workflows/rule_upgrade.py` | `RuleUpgradeWorkflow` | 规则升级 | 定时任务 | 规则挖掘、补丁生成、回归测试、灰度发布 |
| `src/workflows/rule_upgrade.py` | `ScheduledRuleUpgradeWorkflow` | 定时规则升级 | Cron | 循环执行子工作流 |
| `src/workflows/question_grading.py` | `QuestionGradingChildWorkflow` | 单题批改子工作流 | 父工作流调用 | 重试策略 |
| `src/workflows/enhanced_workflow.py` | `EnhancedWorkflowMixin` | 增强工作流混入 | 被继承 | Query, Signal, 分布式锁, 进度查询 |

### 1.2 Workflow 装饰器使用统计

- `@workflow.defn`: 7 处
- `@workflow.run`: 7 处
- `@workflow.signal`: 7 处
- `@workflow.query`: 5 处
- `workflow.execute_activity`: 30+ 处
- `workflow.start_child_workflow`: 5 处
- `workflow.wait_condition`: 2 处
- `workflow.sleep`: 2 处
- `workflow.info()`: 5 处

---

## 2. Activity 定义清单

### 2.1 主要 Activity 文件

| 文件路径 | Activity 函数 | 业务语义 | 依赖服务 |
|---------|--------------|---------|---------|
| `src/activities/grade.py` | `grade_question_activity` | 题目批改 | GradingAgent, CacheService |
| `src/activities/boundary_detection.py` | `detect_student_boundaries_activity` | 学生边界检测 | StudentBoundaryDetector |
| `src/activities/streaming.py` | `push_stream_event_activity` | 推送流式事件 | StreamingService, Redis |
| `src/activities/streaming.py` | `create_stream_activity` | 创建流式连接 | StreamingService, Redis |
| `src/activities/rule_upgrade.py` | `mine_failure_patterns_activity` | 挖掘失败模式 | RuleMiner, GradingLogger |
| `src/activities/rule_upgrade.py` | `generate_patch_activity` | 生成补丁 | PatchGenerator |
| `src/activities/rule_upgrade.py` | `run_regression_test_activity` | 运行回归测试 | RegressionTester |
| `src/activities/rule_upgrade.py` | `deploy_patch_canary_activity` | 灰度发布补丁 | PatchDeployer |
| `src/activities/rule_upgrade.py` | `monitor_deployment_activity` | 监控部署 | PatchDeployer |
| `src/activities/rule_upgrade.py` | `rollback_deployment_activity` | 回滚部署 | PatchDeployer |
| `src/activities/rule_upgrade.py` | `promote_deployment_activity` | 全量发布 | PatchDeployer |

### 2.2 Activity 装饰器使用统计

- `@activity.defn`: 15+ 处
- `activity.heartbeat()`: 未使用（但配置了 heartbeat_timeout）

---

## 3. Worker 清单

### 3.1 Worker 文件

| 文件路径 | Worker 类型 | Task Queue | 注册内容 |
|---------|------------|-----------|---------|
| `src/workers/cognitive_worker.py` | 认知 Worker | `vision-compute-queue` | Activities: segment, grade, notify, persist, enhanced_activities |
| `src/workers/orchestration_worker.py` | 编排 Worker | `default-queue` | Workflows: ExamPaperWorkflow, BatchGradingWorkflow, etc. |

### 3.2 Worker 配置

- `TEMPORAL_HOST`: 环境变量，默认 `localhost:7233`
- `TEMPORAL_NAMESPACE`: 环境变量，默认 `default`
- `MAX_CONCURRENT_ACTIVITIES`: 环境变量，默认 `10`
- `max_concurrent_workflow_tasks`: 配置值
- `max_concurrent_activity_task_polls`: 配置值

---

## 4. Temporal Client 调用点

### 4.1 Orchestrator 抽象层

| 文件路径 | 类/函数 | 调用方法 |
|---------|--------|---------|
| `src/orchestration/base.py` | `Orchestrator` (抽象类) | 定义接口 |
| `src/orchestration/temporal_orchestrator.py` | `TemporalOrchestrator` | `client.start_workflow`, `client.get_workflow_handle`, `handle.describe`, `handle.query`, `handle.cancel`, `handle.signal`, `client.list_workflows` |

### 4.2 API 层调用

- `src/api/routes/submissions.py`: 调用 `orchestrator.start_run()`
- `src/api/routes/batch.py`: 调用 `orchestrator.start_run()`
- `src/api/routes/reviews.py`: 调用 `orchestrator.send_event()`

---

## 5. 部署配置清单

### 5.1 Docker Compose

**文件**: `docker-compose.yml`

```yaml
services:
  temporal:
    image: temporalio/auto-setup:1.22.4
    environment:
      - DB=postgresql
    # ... 其他配置
  
  temporal-ui:
    image: temporalio/ui:2.21.3
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
    ports:
      - "8080:8080"
  
  api:
    environment:
      - TEMPORAL_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
  
  cognitive-worker:
    environment:
      - TEMPORAL_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
  
  orchestration-worker:
    environment:
      - TEMPORAL_HOST=temporal:7233
      - TEMPORAL_NAMESPACE=default
```

### 5.2 Kubernetes 配置

**文件**: `k8s/configmap.yaml`

```yaml
data:
  TEMPORAL_HOST: "temporal-frontend.temporal:7233"
  TEMPORAL_NAMESPACE: "default"
```

**文件**: `k8s/keda/cognitive-worker-scaledobject.yaml`

```yaml
triggers:
  - type: external
    metadata:
      scalerAddress: temporal-keda-scaler.keda:9090
      namespace: default
      taskQueue: vision-compute-queue
```

**文件**: `k8s/services/network-policy.yaml`

```yaml
ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: temporal
```

### 5.3 依赖声明

**文件**: `pyproject.toml`

```toml
dependencies = [
    "temporalio>=1.5.0",
    # ...
]
```

### 5.4 CI/CD

**文件**: `.github/workflows/deploy.yml`

- 未发现 Temporal 特定配置（需进一步检查）

---

## 6. 重试策略与超时配置

### 6.1 RetryPolicy 定义

| 位置 | 策略名称 | 配置 |
|------|---------|------|
| `src/workflows/exam_paper.py` | `SEGMENT_RETRY_POLICY` | initial=1s, backoff=2.0, max=1m, attempts=2 |
| `src/workflows/exam_paper.py` | `PERSIST_RETRY_POLICY` | initial=1s, backoff=2.0, max=1m, attempts=3 |
| `src/workflows/batch_grading.py` | `IDENTIFY_RETRY_POLICY` | initial=1s, backoff=2.0, max=1m, attempts=2 |
| `src/workflows/batch_grading_enhanced.py` | `GRADING_RETRY_POLICY` | initial=1s, backoff=2.0, max=1m, attempts=3 |
| `src/workflows/rule_upgrade.py` | `RULE_UPGRADE_RETRY_POLICY` | initial=5s, backoff=2.0, max=5m, attempts=3 |

### 6.2 Timeout 配置

- `start_to_close_timeout`: 2-15 分钟不等
- `heartbeat_timeout`: 30 秒

---

## 7. Signal 与 Query 使用

### 7.1 Signal 定义

| Workflow | Signal 名称 | 用途 |
|----------|------------|------|
| `ExamPaperWorkflow` | `review_signal` | 人工审核信号 |
| `EnhancedWorkflowMixin` | `external_event` | 外部事件接收 |
| `EnhancedWorkflowMixin` | `update_langgraph_state` | 更新 LangGraph 状态 |
| `EnhancedWorkflowMixin` | `lock_acquired` | 锁获取通知 |
| `EnhancedWorkflowMixin` | `lock_released` | 锁释放通知 |

### 7.2 Query 定义

| Workflow | Query 名称 | 返回内容 |
|----------|-----------|---------|
| `ExamPaperWorkflow` | `get_progress` | 进度信息 |
| `BatchGradingWorkflow` | `get_progress` | 进度信息 |
| `EnhancedBatchGradingWorkflow` | `get_progress` | 进度信息 |
| `RuleUpgradeWorkflow` | `get_progress` | 升级进度 |
| `EnhancedWorkflowMixin` | `get_progress` | 进度信息 |
| `EnhancedWorkflowMixin` | `get_langgraph_state` | LangGraph 状态快照 |
| `EnhancedWorkflowMixin` | `get_external_events` | 外部事件列表 |
| `EnhancedWorkflowMixin` | `get_held_locks` | 持有的锁 |

---

## 8. 子工作流与并行执行

### 8.1 子工作流调用

| 父工作流 | 子工作流 | Task Queue | 并发控制 |
|---------|---------|-----------|---------|
| `ExamPaperWorkflow` | `QuestionGradingChildWorkflow` | `vision-compute-queue` | 无限制 |
| `BatchGradingWorkflow` | `ExamPaperWorkflow` | `default-queue` | 无限制 |
| `EnhancedBatchGradingWorkflow` | `GradePageWorkflow` | `vision-compute-queue` | 批次内并行 |
| `RuleUpgradeWorkflow` | 无 | - | - |
| `ScheduledRuleUpgradeWorkflow` | `RuleUpgradeWorkflow` | `default-queue` | 串行 |
| `EnhancedWorkflowMixin` | `batch_start_child_workflows` | 可配置 | `max_concurrent` 参数 |

### 8.2 并发控制

- `EnhancedWorkflowMixin.batch_start_child_workflows`: 使用 `asyncio.Semaphore` 限制并发

---

## 9. 环境变量依赖

| 环境变量 | 默认值 | 使用位置 |
|---------|-------|---------|
| `TEMPORAL_HOST` | `localhost:7233` | Workers, Orchestrator |
| `TEMPORAL_NAMESPACE` | `default` | Workers, Orchestrator |
| `MAX_CONCURRENT_ACTIVITIES` | `10` | Cognitive Worker |

---

## 10. 测试文件中的 Temporal 引用

| 文件路径 | 引用类型 |
|---------|---------|
| `tests/unit/test_workers.py` | 测试 Worker 签名 |
| `tests/integration/test_temporal_langgraph_sync.py` | 测试 Temporal-LangGraph 同步 |
| `tests/integration/test_workflows.py` | 测试 Workflow 执行 |
| `tests/property/test_*.py` | 多个属性测试引用 Temporal 概念 |

---

## 11. 文档中的 Temporal 引用

| 文件路径 | 引用内容 |
|---------|---------|
| `docs/AI 批改系统设计方案.md` | Temporal Workflow 代码示例 |
| `docs/DEPLOYMENT.md` | 可能包含 Temporal 部署说明 |
| `docs/WIKI.md` | 可能包含 Temporal 架构说明 |
| `.kiro/specs/ai-grading-agent/design.md` | Temporal 架构设计 |
| `.kiro/specs/temporal-to-langgraph-migration/*` | 迁移规格文档 |

---

## 12. 迁移优先级评估

### 12.1 核心业务 Workflow（高优先级）

1. **ExamPaperWorkflow** - 试卷批改主流程
2. **QuestionGradingChildWorkflow** - 单题批改
3. **BatchGradingWorkflow** - 批量批改

### 12.2 增强功能 Workflow（中优先级）

4. **EnhancedBatchGradingWorkflow** - 增强批量批改
5. **RuleUpgradeWorkflow** - 规则升级

### 12.3 定时任务 Workflow（低优先级）

6. **ScheduledRuleUpgradeWorkflow** - 定时规则升级

### 12.4 基础设施（最后清理）

7. **Workers** - 认知 Worker、编排 Worker
8. **Orchestrator** - Temporal Orchestrator 实现
9. **部署配置** - Docker Compose, K8s, KEDA
10. **依赖声明** - pyproject.toml

---

## 13. 风险点识别

### 13.1 高风险

- **正在运行的 Workflow**: 需要 drain 策略，避免中断
- **Signal/Query 依赖**: 人工审核流程依赖 Signal，需要等效实现
- **子工作流扇出**: 大量并行子工作流，需要确保 LangGraph 性能

### 13.2 中风险

- **重试策略**: Temporal 的重试策略需要在 LangGraph 节点中实现
- **超时控制**: Temporal 的超时机制需要在 LangGraph 中等效实现
- **分布式锁**: 依赖 Redis 分布式锁，需要确保兼容性

### 13.3 低风险

- **进度查询**: 可以通过读取 Checkpointer 状态实现
- **定时任务**: 可以用系统 cron 或 LangSmith Deployment cron 替代

---

## 14. 迁移策略建议

### 14.1 分阶段迁移

1. **Phase 1**: 实现 LangGraph Orchestrator，与 Temporal Orchestrator 并存
2. **Phase 2**: 迁移核心 Workflow（ExamPaperWorkflow, QuestionGradingChildWorkflow）
3. **Phase 3**: 迁移批量 Workflow（BatchGradingWorkflow, EnhancedBatchGradingWorkflow）
4. **Phase 4**: 迁移规则升级 Workflow（RuleUpgradeWorkflow, ScheduledRuleUpgradeWorkflow）
5. **Phase 5**: 清理 Temporal 依赖（Workers, 部署配置, 依赖声明）

### 14.2 兼容性保证

- 保持 `Orchestrator` 接口不变
- 业务层代码无需修改
- 通过配置切换 Temporal/LangGraph

### 14.3 回滚策略

- 保留 Temporal 配置和代码，直到 LangGraph 完全稳定
- 通过环境变量快速切换回 Temporal

---

## 15. 下一步行动

1. ✅ **完成 Temporal 足迹盘点**（本文档）
2. ⏭️ **设计 LangGraph Orchestrator 实现**
3. ⏭️ **实现 LangGraph Graph（替代 Workflow）**
4. ⏭️ **实现 Durable Execution（Checkpointer）**
5. ⏭️ **迁移正在运行的 Workflow**
6. ⏭️ **清理 Temporal 依赖**
7. ⏭️ **验证清理完整性**

---

**报告生成完毕**
