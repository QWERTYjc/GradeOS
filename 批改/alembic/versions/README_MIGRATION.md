# 数据库迁移说明

## 架构深度融合迁移 (b061af4f20aa)

此迁移文件添加了架构深度融合优化所需的所有数据库表和字段。

### 包含的变更

#### 1. 追踪表 (trace_spans)
- **需求**: 5.4
- **用途**: 存储端到端追踪信息
- **字段**: trace_id, span_id, parent_span_id, kind, name, start_time, end_time, duration_ms, attributes, status
- **索引**: 
  - idx_trace_spans_trace (trace_id)
  - idx_trace_spans_time (start_time)
  - idx_trace_spans_duration (duration_ms > 500)

#### 2. Saga 事务日志表 (saga_transactions)
- **需求**: 4.5
- **用途**: 记录分布式事务执行历史
- **字段**: saga_id, steps, final_status, started_at, completed_at, error_message
- **索引**: idx_saga_status (final_status)

#### 3. 检查点表增强 (langgraph_checkpoints)
- **需求**: 9.1, 9.3
- **新增字段**:
  - is_compressed: 标记数据是否压缩
  - is_delta: 标记是否为增量存储
  - base_checkpoint_id: 增量存储的基础检查点 ID
  - data_size_bytes: 数据大小（字节）

#### 4. 工作流状态缓存表 (workflow_state_cache)
- **需求**: 3.5
- **用途**: Redis 降级时的工作流状态缓存
- **字段**: workflow_id, state, updated_at

### 运行迁移

```bash
# 查看当前版本
alembic current

# 升级到最新版本
alembic upgrade head

# 查看迁移历史
alembic history

# 回滚到上一个版本
alembic downgrade -1

# 回滚到特定版本
alembic downgrade abea6430ff73
```

### 注意事项

1. 运行迁移前请确保 PostgreSQL 数据库正在运行
2. 确保数据库连接配置正确（alembic.ini 或环境变量）
3. 建议在生产环境运行前先在测试环境验证
4. 此迁移会修改现有的 langgraph_checkpoints 表，请确保有备份

### 验证迁移

运行迁移后，可以使用以下 SQL 验证表是否创建成功：

```sql
-- 检查追踪表
SELECT * FROM trace_spans LIMIT 1;

-- 检查 Saga 事务日志表
SELECT * FROM saga_transactions LIMIT 1;

-- 检查检查点表新增字段
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'langgraph_checkpoints' 
AND column_name IN ('is_compressed', 'is_delta', 'base_checkpoint_id', 'data_size_bytes');

-- 检查工作流状态缓存表
SELECT * FROM workflow_state_cache LIMIT 1;
```
