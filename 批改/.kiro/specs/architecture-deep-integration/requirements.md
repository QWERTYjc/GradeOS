# 需求文档

## 简介

本文档定义了 AI 批改系统架构深度融合优化的需求规范。目标是优化 Temporal 工作流编排引擎、LangGraph 智能体框架、Redis 缓存层和 PostgreSQL 数据存储层之间的集成，实现更高效的数据流转、更强的一致性保证、更好的可观测性和更低的延迟。当前系统各组件相对独立，本次优化将实现组件间的深度融合，包括统一的状态管理、分布式事务协调、智能缓存预热、以及端到端的追踪能力。

## 术语表

- **Temporal**: 分布式工作流编排引擎，提供持久化执行和故障恢复能力
- **LangGraph**: 基于图结构的智能体框架，支持循环推理和状态管理
- **PostgreSQL Checkpointer**: LangGraph 的 PostgreSQL 检查点持久化器
- **Redis Cluster**: Redis 集群模式，提供高可用缓存服务
- **Saga Pattern**: 分布式事务模式，通过补偿操作保证最终一致性
- **Write-Through Cache**: 写穿缓存策略，写入时同时更新缓存和数据库
- **Cache-Aside Pattern**: 旁路缓存模式，应用程序负责缓存的读写
- **Distributed Tracing**: 分布式追踪，跨服务的请求链路追踪
- **Connection Pool**: 数据库连接池，复用数据库连接提高性能
- **Temporal Signal**: Temporal 信号机制，用于向运行中的工作流发送消息
- **Temporal Query**: Temporal 查询机制，用于查询工作流状态
- **Activity Heartbeat**: Temporal Activity 心跳，用于长时间运行的 Activity 报告进度
- **LangGraph State Channel**: LangGraph 状态通道，用于节点间数据传递
- **Semantic Cache Key**: 语义缓存键，基于内容语义而非精确匹配的缓存键

## 需求列表

### 需求 1：Temporal 与 LangGraph 状态同步

**用户故事：** 作为系统架构师，我希望 Temporal 工作流状态与 LangGraph 智能体状态能够双向同步，以便在任何故障点都能恢复到一致的状态。

#### 验收标准

1. WHEN Temporal 工作流启动 LangGraph 智能体时，工作流应当将 workflow_run_id 作为 thread_id 传递给 LangGraph
2. WHEN LangGraph 智能体完成状态转换时，智能体应当通过 Activity Heartbeat 向 Temporal 报告进度
3. WHEN Temporal Worker 崩溃并恢复时，工作流应当从 PostgreSQL 检查点恢复 LangGraph 状态并继续执行
4. WHEN LangGraph 执行失败时，Temporal 应当根据重试策略决定是从检查点恢复还是重新开始
5. WHEN 工作流需要查询智能体中间状态时，Temporal Query 应当能够返回最新的 LangGraph 状态快照

### 需求 2：PostgreSQL 统一数据层

**用户故事：** 作为数据库管理员，我希望所有持久化数据都通过统一的 PostgreSQL 数据层管理，以便简化运维并保证数据一致性。

#### 验收标准

1. WHEN 系统初始化时，数据库连接池应当创建共享的连接池供 Temporal Activities、LangGraph Checkpointer 和 Repository 层使用
2. WHEN 批改结果需要持久化时，系统应当在单个数据库事务中同时保存 grading_results 和更新 submissions 状态
3. WHEN LangGraph 检查点保存时，检查点应当与批改中间结果在同一事务中持久化
4. WHEN 查询批改历史时，系统应当通过单次查询联合 submissions、grading_results 和 langgraph_checkpoints 表返回完整数据
5. WHEN 数据库连接池耗尽时，系统应当返回明确的错误信息并触发告警

### 需求 3：Redis 多层缓存架构

**用户故事：** 作为系统运维人员，我希望 Redis 缓存能够支持多层缓存策略，以便不同类型的数据能够采用最优的缓存策略。

#### 验收标准

1. WHEN 批改结果生成时，系统应当采用 Write-Through 策略同时写入 Redis 和 PostgreSQL
2. WHEN 查询批改结果时，系统应当先查询 Redis 热数据缓存，未命中时再查询 PostgreSQL 并回填缓存
3. WHEN 评分细则更新时，系统应当通过 Redis Pub/Sub 通知所有 Worker 节点失效本地缓存
4. WHEN 工作流状态变更时，系统应当将状态同步到 Redis 以支持实时查询
5. WHEN Redis 集群节点故障时，系统应当自动降级到直接查询 PostgreSQL

### 需求 4：分布式事务协调

**用户故事：** 作为系统架构师，我希望跨组件的操作能够保证事务一致性，以便在部分失败时能够正确回滚或补偿。

#### 验收标准

1. WHEN 批改流程涉及多个数据存储时，系统应当采用 Saga 模式协调分布式事务
2. WHEN 缓存写入成功但数据库写入失败时，系统应当执行补偿操作删除缓存条目
3. WHEN Temporal Activity 超时时，系统应当检查并清理可能的部分写入状态
4. WHEN 人工审核覆盖分数时，系统应当在单个事务中更新数据库、失效缓存并发送通知
5. WHEN 分布式事务失败时，系统应当记录详细的事务日志以支持人工干预

### 需求 5：端到端可观测性

**用户故事：** 作为系统运维人员，我希望能够追踪请求从 API 到 Temporal 到 LangGraph 的完整链路，以便快速定位性能瓶颈和故障点。

#### 验收标准

1. WHEN API 接收请求时，系统应当生成唯一的 trace_id 并传递给所有下游组件
2. WHEN Temporal 工作流执行时，工作流应当将 trace_id 附加到所有 Activity 调用
3. WHEN LangGraph 节点执行时，节点应当记录带有 trace_id 的结构化日志
4. WHEN 查询追踪信息时，系统应当能够返回包含 Temporal 工作流、LangGraph 节点、数据库操作和缓存操作的完整链路
5. WHEN 性能指标超过阈值时，系统应当自动触发告警并记录详细的诊断信息

### 需求 6：智能缓存预热与失效

**用户故事：** 作为系统运维人员，我希望缓存能够智能预热高频访问的数据，以便减少冷启动延迟并提高缓存命中率。

#### 验收标准

1. WHEN 系统启动时，缓存服务应当从 PostgreSQL 加载最近 7 天的高置信度批改结果到 Redis
2. WHEN 新的评分细则创建时，系统应当预计算并缓存该细则的哈希值
3. WHEN 缓存命中率低于 60% 时，系统应当分析访问模式并调整预热策略
4. WHEN 批量导入历史数据时，系统应当异步预热相关缓存而不阻塞主流程
5. WHEN 缓存内存使用超过 80% 时，系统应当基于 LRU 策略淘汰低优先级缓存

### 需求 7：API 端点优化

**用户故事：** 作为前端开发者，我希望 API 端点能够提供更丰富的查询能力和更好的性能，以便构建更好的用户体验。

#### 验收标准

1. WHEN 查询批改状态时，API 应当支持 WebSocket 实时推送状态变更
2. WHEN 批量查询批改结果时，API 应当支持分页、排序和过滤参数
3. WHEN 查询单个批改结果时，API 应当支持指定返回字段以减少数据传输
4. WHEN API 响应时间超过 500ms 时，系统应当记录慢查询日志并触发告警
5. WHEN 并发请求超过阈值时，API 应当返回 429 状态码并提供 Retry-After 头

### 需求 8：连接池与资源管理

**用户故事：** 作为系统运维人员，我希望系统能够高效管理数据库和 Redis 连接，以便在高并发场景下保持稳定性能。

#### 验收标准

1. WHEN 系统启动时，连接池应当预创建最小数量的数据库连接和 Redis 连接
2. WHEN 连接使用完毕时，连接应当正确归还到连接池而不是关闭
3. WHEN 连接空闲超过 5 分钟时，连接池应当关闭多余的空闲连接
4. WHEN 获取连接超时时，系统应当返回明确的错误信息而不是无限等待
5. WHEN Worker 进程关闭时，系统应当优雅地关闭所有连接并等待进行中的操作完成

### 需求 9：LangGraph 检查点优化

**用户故事：** 作为系统架构师，我希望 LangGraph 检查点能够高效存储和恢复，以便支持大规模并发批改任务。

#### 验收标准

1. WHEN 保存检查点时，系统应当仅保存状态增量而非完整状态以减少存储开销
2. WHEN 恢复检查点时，系统应当支持从任意历史检查点恢复而不仅是最新检查点
3. WHEN 检查点数据超过 1MB 时，系统应当压缩数据后再存储
4. WHEN 检查点保存失败时，系统应当重试最多 3 次后标记任务为需要人工干预
5. WHEN 检查点数据超过 30 天时，系统应当自动归档到冷存储

### 需求 10：Temporal 工作流增强

**用户故事：** 作为系统架构师，我希望 Temporal 工作流能够更好地与其他组件集成，以便提供更强大的编排能力。

#### 验收标准

1. WHEN 工作流需要等待外部事件时，工作流应当支持通过 Redis Pub/Sub 接收事件通知
2. WHEN 工作流执行时间超过预期时，工作流应当通过 Temporal Query 暴露当前进度
3. WHEN 批量提交多份试卷时，系统应当支持父工作流批量启动子工作流并限制并发数
4. WHEN 工作流需要访问共享资源时，工作流应当通过 Redis 分布式锁协调访问
5. WHEN 工作流版本升级时，系统应当支持新旧版本工作流并行运行

