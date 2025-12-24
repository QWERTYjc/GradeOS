# Requirements Document

## Introduction

本文档定义了将 AI 批改系统从 Temporal 工作流编排引擎迁移到 LangGraph 的需求规格。迁移目标是彻底移除 Temporal 依赖，同时保留长任务可恢复、重试退避、状态查询、并行 fanout、人工介入、定时任务等核心能力。

## Glossary

- **Temporal**: 当前使用的分布式工作流编排引擎，提供持久化执行、重试、信号等能力
- **LangGraph**: 目标编排框架，基于图结构的智能体推理框架，支持 Checkpointer 实现持久化执行
- **Workflow**: 工作流定义，在 Temporal 中用 `@workflow.defn` 装饰，迁移后对应 LangGraph Graph
- **Activity**: 工作流中的原子任务单元，在 Temporal 中用 `@activity.defn` 装饰，迁移后对应 LangGraph Node
- **Signal**: Temporal 中用于向运行中工作流发送外部事件的机制，迁移后用 `interrupt()` + `resume` 实现
- **Query**: Temporal 中用于查询工作流状态的机制，迁移后通过读取持久化 State 实现
- **Checkpointer**: LangGraph 的状态持久化组件，支持 PostgreSQL/Redis 后端
- **Thread_ID**: LangGraph 中标识一次执行的唯一标识符，对应 Temporal 的 workflow_run_id
- **Orchestrator**: 编排器抽象接口，隔离业务层对具体编排引擎的依赖
- **Run Table**: 自托管模式下用于跟踪后台执行的数据库表
- **Idempotency Key**: 幂等键，用于防止重复执行造成的副作用

## Requirements

### Requirement 1: Orchestrator 抽象接口

**User Story:** As a 开发者, I want 业务层通过统一的 Orchestrator 接口调用编排能力, so that 可以无缝切换底层编排引擎而不影响业务代码。

#### Acceptance Criteria

1. WHEN 业务层需要启动工作流 THEN Orchestrator 接口 SHALL 提供 `start_run(payload) -> run_id` 方法
2. WHEN 业务层需要查询工作流状态 THEN Orchestrator 接口 SHALL 提供 `get_status(run_id) -> RunStatus` 方法
3. WHEN 业务层需要取消工作流 THEN Orchestrator 接口 SHALL 提供 `cancel(run_id) -> bool` 方法
4. WHEN 业务层需要重试失败的工作流 THEN Orchestrator 接口 SHALL 提供 `retry(run_id) -> run_id` 方法
5. WHEN 业务层需要列出工作流 THEN Orchestrator 接口 SHALL 提供 `list_runs(filters) -> List[RunInfo]` 方法
6. WHEN 业务层需要发送外部事件 THEN Orchestrator 接口 SHALL 提供 `send_event(run_id, event) -> bool` 方法

### Requirement 2: LangGraph Graph 实现

**User Story:** As a 系统架构师, I want 将现有 Temporal Workflow 重写为 LangGraph Graph, so that 可以利用 LangGraph 的图结构和检查点能力实现持久化执行。

#### Acceptance Criteria

1. WHEN 定义 Graph State THEN 系统 SHALL 包含 job_id、inputs、progress、artifacts、errors、attempts、timestamps 等字段
2. WHEN 将 Activity 重写为 Node THEN 系统 SHALL 确保每个 Node 是纯函数或工具调用，状态更新写回 State
3. WHEN Node 执行完成 THEN 系统 SHALL 自动触发 Checkpointer 保存状态
4. WHEN 需要人工确认或外部回调 THEN 系统 SHALL 使用 `interrupt()` 暂停执行并提供 `resume` API
5. WHEN Graph 执行失败 THEN 系统 SHALL 根据重试策略决定是从检查点恢复还是重新开始

### Requirement 3: 持久化执行（Durable Execution）

**User Story:** As a 运维工程师, I want 系统在 Worker 崩溃或重启后能从检查点继续执行, so that 长时间运行的批改任务不会丢失进度。

#### Acceptance Criteria

1. WHEN 启用 Checkpointer THEN 系统 SHALL 使用 PostgreSQL 作为检查点存储后端
2. WHEN 每个 Run 启动 THEN 系统 SHALL 分配固定的 thread_id 用于检查点关联
3. WHEN Worker 崩溃后重启 THEN 系统 SHALL 从最近的检查点恢复执行
4. WHEN 使用自托管模式 THEN 系统 SHALL 维护 run 表和 attempt 表记录执行状态
5. WHEN Worker 轮询执行 THEN 系统 SHALL 调用 `graph.invoke(thread_id=...)` 恢复执行

### Requirement 4: 重试与超时策略

**User Story:** As a 开发者, I want 系统提供节点级重试和超时控制, so that 可以处理 Gemini API 限流等临时故障。

#### Acceptance Criteria

1. WHEN Node 执行失败 THEN 系统 SHALL 根据配置的重试策略进行指数退避重试
2. WHEN 重试次数耗尽 THEN 系统 SHALL 将执行路由到补偿或降级分支
3. WHEN Node 执行超时 THEN 系统 SHALL 中断执行并触发超时处理逻辑
4. WHEN 配置重试策略 THEN 系统 SHALL 支持 initial_interval、backoff_coefficient、maximum_attempts 参数
5. WHEN 遇到不可重试错误 THEN 系统 SHALL 立即失败而不进行重试

### Requirement 5: 并行 Fanout 与聚合

**User Story:** As a 系统架构师, I want 系统支持并行执行多个子任务并聚合结果, so that 可以高效处理多题目批改场景。

#### Acceptance Criteria

1. WHEN 需要并行执行多个子任务 THEN 系统 SHALL 使用 fanout 子图模式分发任务
2. WHEN 所有子任务完成 THEN 系统 SHALL 在聚合节点汇总结果
3. WHEN 部分子任务失败 THEN 系统 SHALL 记录失败信息并继续处理成功的结果
4. WHEN 配置并发限制 THEN 系统 SHALL 使用信号量控制最大并发数
5. WHEN 子任务执行 THEN 系统 SHALL 更新父任务的进度信息

### Requirement 6: 定时任务调度

**User Story:** As a 运维工程师, I want 系统支持定时触发工作流执行, so that 可以实现规则升级等周期性任务。

#### Acceptance Criteria

1. WHEN 配置定时任务 THEN 系统 SHALL 支持 cron 表达式定义执行周期
2. WHEN 定时触发时间到达 THEN 系统 SHALL 自动调用 `start_run` 启动工作流
3. WHEN 使用自托管模式 THEN 系统 SHALL 通过系统 cron 或现有队列触发执行
4. WHEN 定时任务执行失败 THEN 系统 SHALL 记录失败并在下一周期重试
5. WHEN 需要手动触发 THEN 系统 SHALL 提供 API 立即执行定时任务

### Requirement 7: 状态查询与审计

**User Story:** As a 教师, I want 查询批改任务的执行状态和历史记录, so that 可以了解批改进度和排查问题。

#### Acceptance Criteria

1. WHEN 查询工作流状态 THEN 系统 SHALL 返回当前阶段、进度百分比、详细信息
2. WHEN 查询执行历史 THEN 系统 SHALL 返回所有检查点和状态变更记录
3. WHEN 记录审计日志 THEN 系统 SHALL 将关键状态写入 run/attempt/error 表
4. WHEN 查询失败原因 THEN 系统 SHALL 返回详细的错误信息和堆栈跟踪
5. WHEN 导出执行记录 THEN 系统 SHALL 支持按时间范围和状态筛选

### Requirement 8: 人工介入（Human-in-the-Loop）

**User Story:** As a 教师, I want 在低置信度批改结果时进行人工审核, so that 可以确保批改质量。

#### Acceptance Criteria

1. WHEN 批改置信度低于阈值 THEN 系统 SHALL 使用 `interrupt()` 暂停执行
2. WHEN 教师提交审核结果 THEN 系统 SHALL 通过 `resume` API 恢复执行
3. WHEN 审核超时 THEN 系统 SHALL 根据配置自动批准或拒绝
4. WHEN 教师覆盖分数 THEN 系统 SHALL 更新 State 中的评分结果
5. WHEN 审核完成 THEN 系统 SHALL 记录审核操作到审计日志

### Requirement 9: 迁移脚本与数据迁移

**User Story:** As a 运维工程师, I want 平滑迁移正在运行的 Temporal 工作流到 LangGraph, so that 不会丢失任何进行中的批改任务。

#### Acceptance Criteria

1. WHEN 开始迁移 THEN 系统 SHALL 停止接入新的 Temporal Run
2. WHEN Temporal 队列排空 THEN 系统 SHALL 导出所有未完成工作流列表
3. WHEN 生成迁移 Payload THEN 系统 SHALL 保证幂等性避免重复执行
4. WHEN 重新启动到 LangGraph THEN 系统 SHALL 调用 `start_run` 创建新的执行
5. WHEN 迁移历史审计数据 THEN 系统 SHALL 将关键状态写入新的 DB 表

### Requirement 10: Temporal 依赖清理

**User Story:** As a 开发者, I want 彻底移除仓库中的 Temporal 依赖, so that 简化系统架构和部署复杂度。

#### Acceptance Criteria

1. WHEN 迁移完成 THEN 系统 SHALL 删除 temporalio SDK 依赖
2. WHEN 清理代码 THEN 系统 SHALL 删除所有 workflow/activity/worker/client 代码
3. WHEN 清理部署配置 THEN 系统 SHALL 删除 temporal server 容器/k8s 资源/env/CI 配置
4. WHEN 验证清理 THEN 仓库全文搜索 temporal/workflow/activity/taskQueue/namespace 结果 SHALL 为 0（除 changelog）
5. WHEN 更新文档 THEN 系统 SHALL 更新所有相关文档移除 Temporal 引用

### Requirement 11: 前端 LangGraph 多智能体架构集成

**User Story:** As a 前端开发者, I want 前端直接与 LangGraph 多智能体批改架构交互, so that 可以实时展示批改进度和智能体推理过程。

#### Acceptance Criteria

1. WHEN 前端发起批改请求 THEN 系统 SHALL 通过 API 触发 LangGraph Graph 执行
2. WHEN Graph 执行过程中 THEN 前端 SHALL 通过 WebSocket 接收实时进度更新
3. WHEN 多智能体协作批改 THEN 前端 SHALL 展示当前活跃的智能体类型和推理状态
4. WHEN 智能体节点完成 THEN 前端 SHALL 更新对应的批改结果和置信度
5. WHEN 需要人工介入 THEN 前端 SHALL 展示审核界面并支持提交审核结果

### Requirement 12: 多智能体批改 Graph 架构

**User Story:** As a 系统架构师, I want 使用 LangGraph 实现多智能体协作批改, so that 不同类型的题目可以由专门的智能体处理。

#### Acceptance Criteria

1. WHEN 批改任务启动 THEN Supervisor 智能体 SHALL 根据题目类型分发到专门智能体
2. WHEN 处理客观题 THEN ObjectiveAgent SHALL 执行精确匹配和评分
3. WHEN 处理主观题 THEN EssayAgent SHALL 执行深度推理和多维度评分
4. WHEN 处理步骤题 THEN StepwiseAgent SHALL 执行逐步评分和部分分计算
5. WHEN 处理实验设计题 THEN LabDesignAgent SHALL 执行实验方案评估
6. WHEN 智能体评分完成 THEN 系统 SHALL 将结果汇总到统一的 State 中

### Requirement 13: 前端批改控制台

**User Story:** As a 教师, I want 在前端控制台查看批改过程的详细信息, so that 可以理解 AI 的评分依据。

#### Acceptance Criteria

1. WHEN 查看批改详情 THEN 前端 SHALL 展示智能体推理链和证据链
2. WHEN 查看节点状态 THEN 前端 SHALL 展示每个 Graph 节点的输入输出
3. WHEN 查看检查点 THEN 前端 SHALL 展示可恢复的检查点列表
4. WHEN 需要重试 THEN 前端 SHALL 支持从指定检查点恢复执行
5. WHEN 查看性能指标 THEN 前端 SHALL 展示各节点的执行时间和 Token 消耗

### Requirement 14: API 层 LangGraph 集成

**User Story:** As a 后端开发者, I want API 层直接调用 LangGraph Graph, so that 无需通过 Temporal 中间层。

#### Acceptance Criteria

1. WHEN 接收批改请求 THEN API 层 SHALL 直接创建 LangGraph Graph 实例
2. WHEN 启动后台执行 THEN API 层 SHALL 使用 background runs 模式异步执行
3. WHEN 查询执行状态 THEN API 层 SHALL 从 Checkpointer 读取最新状态
4. WHEN 发送外部事件 THEN API 层 SHALL 调用 Graph 的 resume 方法
5. WHEN 取消执行 THEN API 层 SHALL 标记 run 状态并清理资源
