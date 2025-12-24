# Implementation Plan

## Step 1: 抽象接口与依赖隔离

- [x] 1. 创建 Orchestrator 抽象接口




  - [x] 1.1 定义 Orchestrator 抽象基类和数据模型


    - 创建 `src/orchestration/base.py`
    - 定义 `RunStatus` 枚举、`RunInfo` 数据类
    - 定义 `Orchestrator` 抽象基类及所有方法签名
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [ ]* 1.2 编写 Orchestrator 接口属性测试
    - **Property 1: Orchestrator 接口完整性**
    - **Validates: Requirements 1.1, 1.2**
  - [x] 1.3 实现 TemporalOrchestrator 包装器


    - 创建 `src/orchestration/temporal_orchestrator.py`
    - 包装现有 Temporal Client 调用
    - 实现所有 Orchestrator 接口方法
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [x] 1.4 修改业务层使用 Orchestrator 接口


    - 更新 `src/services/submission.py` 使用 Orchestrator
    - 更新 `src/api/routes/submissions.py` 使用 Orchestrator
    - 添加依赖注入配置
    - _Requirements: 1.1_



- [x] 2. Checkpoint - 确保所有测试通过



  - Ensure all tests pass, ask the user if questions arise.

## Step 2: LangGraph Graph 实现

- [x] 3. 定义 Graph State 和核心类型




  - [x] 3.1 创建 GradingGraphState 类型定义


    - 创建 `src/graphs/state.py`
    - 定义 `GradingGraphState` TypedDict
    - 包含 job_id、inputs、progress、artifacts、errors、attempts、timestamps 等字段
    - _Requirements: 2.1_
  - [x] 3.2 创建重试策略配置类


    - 创建 `src/graphs/retry.py`
    - 定义 `RetryConfig` 数据类
    - 实现 `with_retry` 异步函数
    - 实现 `create_retryable_node` 工厂函数
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [ ]* 3.3 编写重试策略属性测试
    - **Property 4: 重试策略正确性**
    - **Validates: Requirements 4.1, 4.4**


- [x] 4. 将 Activity 重写为 Node 函数



  - [x] 4.1 重写 segment_document 为 Node


    - 创建 `src/graphs/nodes/segment.py`
    - 实现 `segment_node` 函数
    - 集成重试策略
    - _Requirements: 2.2, 2.3_
  - [x] 4.2 重写 grade_question 为 Node


    - 创建 `src/graphs/nodes/grade.py`
    - 实现 `grade_node` 函数
    - 集成缓存检查和重试策略
    - _Requirements: 2.2, 2.3_
  - [x] 4.3 重写 persist_results 为 Node


    - 创建 `src/graphs/nodes/persist.py`
    - 实现 `persist_node` 函数
    - _Requirements: 2.2, 2.3_
  - [x] 4.4 重写 notify_teacher 为 Node


    - 创建 `src/graphs/nodes/notify.py`
    - 实现 `notify_node` 函数
    - _Requirements: 2.2, 2.3_

- [ ] 5. 实现多智能体批改 Graph
  - [ ] 5.1 创建 Supervisor 路由节点
    - 创建 `src/graphs/nodes/supervisor.py`
    - 实现 `supervisor_node` 函数
    - 实现 `route_to_agent` 路由决策函数
    - _Requirements: 12.1_
  - [ ]* 5.2 编写多智能体分发属性测试
    - **Property 7: 多智能体分发正确性**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**
  - [ ] 5.3 创建专门智能体节点
    - 创建 `src/graphs/nodes/agents/objective.py` - ObjectiveAgent
    - 创建 `src/graphs/nodes/agents/essay.py` - EssayAgent
    - 创建 `src/graphs/nodes/agents/stepwise.py` - StepwiseAgent
    - 创建 `src/graphs/nodes/agents/lab_design.py` - LabDesignAgent
    - _Requirements: 12.2, 12.3, 12.4, 12.5_
  - [ ] 5.4 创建聚合节点
    - 创建 `src/graphs/nodes/aggregate.py`
    - 实现 `aggregate_node` 函数
    - 汇总所有智能体结果到 State
    - _Requirements: 12.6, 5.2_
  - [ ]* 5.5 编写并行执行属性测试
    - **Property 5: 并行执行完整性**
    - **Validates: Requirements 5.1, 5.2, 5.3**
  - [ ] 5.6 创建人工介入中断节点
    - 创建 `src/graphs/nodes/review.py`
    - 实现 `review_check_node` 函数
    - 实现 `wait_for_review_node` 函数（使用 interrupt()）
    - _Requirements: 2.4, 8.1_
  - [ ]* 5.7 编写人工介入属性测试
    - **Property 6: 人工介入流程正确性**
    - **Validates: Requirements 8.1, 8.2**


- [ ] 6. 组装完整的 Graph 定义
  - [ ] 6.1 创建 ExamPaperGraph
    - 创建 `src/graphs/exam_paper.py`
    - 组装所有节点和边
    - 配置条件路由
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ] 6.2 创建 BatchGradingGraph
    - 创建 `src/graphs/batch_grading.py`
    - 实现并行 fanout 逻辑
    - 集成学生边界检测
    - _Requirements: 5.1, 5.4_
  - [ ] 6.3 创建 RuleUpgradeGraph
    - 创建 `src/graphs/rule_upgrade.py`
    - 实现规则挖掘 → 补丁生成 → 回归测试 → 部署流程
    - _Requirements: 2.1_

- [ ] 7. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Step 3: Durable Execution 实现

- [ ] 8. 配置 PostgreSQL Checkpointer
  - [ ] 8.1 创建 Checkpointer 配置模块
    - 创建 `src/graphs/checkpointer.py`
    - 配置 PostgresSaver 连接
    - 实现 Checkpointer 工厂函数
    - _Requirements: 3.1_
  - [ ] 8.2 创建数据库迁移脚本
    - 创建 `alembic/versions/xxx_add_langgraph_runs_tables.py`
    - 添加 runs 表
    - 添加 run_attempts 表
    - _Requirements: 3.4_

- [ ] 9. 实现 LangGraphOrchestrator
  - [ ] 9.1 创建 LangGraphOrchestrator 类
    - 创建 `src/orchestration/langgraph_orchestrator.py`
    - 实现 `start_run` 方法（含幂等性检查）
    - 实现 `get_status` 方法
    - 实现 `cancel` 方法
    - 实现 `retry` 方法
    - 实现 `list_runs` 方法
    - 实现 `send_event` 方法
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [ ]* 9.2 编写幂等性属性测试
    - **Property 2: 幂等性保证**
    - **Validates: Requirements 9.3**
  - [ ]* 9.3 编写状态查询属性测试
    - **Property 8: 状态查询一致性**
    - **Validates: Requirements 7.1, 14.3**
  - [ ]* 9.4 编写取消操作属性测试
    - **Property 9: 取消操作原子性**
    - **Validates: Requirements 1.3, 14.5**

- [ ] 10. 实现 Worker 轮询执行
  - [ ] 10.1 创建 Graph Worker
    - 创建 `src/graphs/worker.py`
    - 实现轮询 pending runs 逻辑
    - 实现 `graph.invoke(thread_id=...)` 调用
    - 实现崩溃恢复逻辑
    - _Requirements: 3.3, 3.5_
  - [ ]* 10.2 编写检查点恢复属性测试
    - **Property 3: 检查点恢复正确性**
    - **Validates: Requirements 3.3, 3.5**
  - [ ]* 10.3 编写进度更新属性测试
    - **Property 10: 进度更新单调性**
    - **Validates: Requirements 5.5, 7.1**

- [ ] 11. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.


## Step 4: 定时任务与 API 集成

- [ ] 12. 实现定时任务调度
  - [ ] 12.1 创建定时任务表迁移
    - 创建 `alembic/versions/xxx_add_scheduled_jobs_table.py`
    - 添加 scheduled_jobs 表
    - _Requirements: 6.1_
  - [ ] 12.2 实现 Cron 调度器
    - 创建 `src/graphs/scheduler.py`
    - 实现 cron 表达式解析
    - 实现定时触发 `start_run` 逻辑
    - _Requirements: 6.1, 6.2, 6.4_
  - [ ] 12.3 添加手动触发 API
    - 更新 `src/api/routes/` 添加手动触发端点
    - _Requirements: 6.5_

- [ ] 13. 更新 API 层集成
  - [ ] 13.1 更新 submissions API
    - 修改 `src/api/routes/submissions.py`
    - 使用 LangGraphOrchestrator 替代 Temporal Client
    - _Requirements: 14.1, 14.2_
  - [ ] 13.2 添加 runs API
    - 创建 `src/api/routes/runs.py`
    - 实现 GET /runs/{run_id}/status
    - 实现 POST /runs/{run_id}/cancel
    - 实现 POST /runs/{run_id}/retry
    - 实现 POST /runs/{run_id}/events
    - _Requirements: 14.3, 14.4, 14.5_
  - [ ] 13.3 更新 WebSocket 推送
    - 修改 `src/services/streaming.py`
    - 从 Graph State 读取进度并推送
    - _Requirements: 11.1, 11.2_

- [ ] 14. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Step 5: 数据迁移

- [ ] 15. 创建迁移脚本
  - [ ] 15.1 实现 Temporal 工作流导出脚本
    - 创建 `scripts/migration/export_temporal_runs.py`
    - 导出所有 pending/running 工作流
    - 生成迁移 payload
    - _Requirements: 9.1, 9.2_
  - [ ] 15.2 实现 LangGraph 导入脚本
    - 创建 `scripts/migration/import_to_langgraph.py`
    - 使用幂等键启动新的 runs
    - _Requirements: 9.3, 9.4_
  - [ ] 15.3 实现审计数据迁移脚本
    - 创建 `scripts/migration/migrate_audit_history.py`
    - 迁移历史执行记录到新表
    - _Requirements: 9.5_

- [ ] 16. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.


## Step 6: Temporal 依赖清理

- [ ] 17. 删除 Temporal 代码
  - [ ] 17.1 删除 Temporal Workflow 文件
    - 删除 `src/workflows/exam_paper.py`
    - 删除 `src/workflows/batch_grading.py`
    - 删除 `src/workflows/question_grading.py`
    - 删除 `src/workflows/enhanced_workflow.py`
    - 删除 `src/workflows/rule_upgrade.py`
    - 删除 `src/workflows/batch_grading_enhanced.py`
    - _Requirements: 10.2_
  - [ ] 17.2 删除 Temporal Activity 文件
    - 删除 `src/activities/segment.py`
    - 删除 `src/activities/grade.py`
    - 删除 `src/activities/notify.py`
    - 删除 `src/activities/persist.py`
    - 删除 `src/activities/identify_students.py`
    - 删除 `src/activities/enhanced_activities.py`
    - 删除 `src/activities/streaming.py`
    - 删除 `src/activities/rule_upgrade.py`
    - 删除 `src/activities/boundary_detection.py`
    - _Requirements: 10.2_
  - [ ] 17.3 删除 Temporal Worker 文件
    - 删除 `src/workers/orchestration_worker.py`
    - 删除 `src/workers/cognitive_worker.py`
    - _Requirements: 10.2_
  - [ ] 17.4 删除 TemporalOrchestrator
    - 删除 `src/orchestration/temporal_orchestrator.py`
    - _Requirements: 10.2_

- [ ] 18. 更新依赖和配置
  - [ ] 18.1 移除 temporalio 依赖
    - 更新 `pyproject.toml` 移除 temporalio
    - 运行 `uv sync` 更新锁文件
    - _Requirements: 10.1_
  - [ ] 18.2 更新 docker-compose.yml
    - 移除 temporal 服务
    - 移除 temporal-ui 服务
    - 更新环境变量
    - _Requirements: 10.3_
  - [ ] 18.3 更新 k8s 配置
    - 更新 `k8s/configmap.yaml` 移除 Temporal 配置
    - 删除 `k8s/keda/cognitive-worker-scaledobject.yaml` 中的 Temporal 触发器
    - 更新 Worker 部署配置
    - _Requirements: 10.3_
  - [ ] 18.4 更新 CI/CD 配置
    - 更新 `.github/workflows/deploy.yml`
    - 移除 Temporal 相关步骤
    - _Requirements: 10.3_

- [ ] 19. 更新文档
  - [ ] 19.1 更新技术文档
    - 更新 `.kiro/steering/tech.md`
    - 更新 `.kiro/steering/structure.md`
    - 更新 `docs/DEPLOYMENT.md`
    - 更新 `docs/INTEGRATION_GUIDE.md`
    - _Requirements: 10.5_
  - [ ] 19.2 更新 README
    - 更新 `README.md` 移除 Temporal 引用
    - 更新 `src/workers/README.md`
    - _Requirements: 10.5_

- [ ] 20. 验证清理完成
  - [ ] 20.1 运行全文搜索验证
    - 搜索 `temporal` 关键字
    - 搜索 `workflow.defn` 关键字
    - 搜索 `activity.defn` 关键字
    - 搜索 `taskQueue` 关键字
    - 确保结果为 0（除 changelog）
    - _Requirements: 10.4_

- [ ] 21. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
