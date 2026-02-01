# 批改标准复核页面修复报告

## 问题描述

批改标准复核页面（`/grading/rubric-review/{batchId}`）无法访问已保存的 rubric 和 rubric 图片，显示：
- 共 0 题，总分 0
- 暂无批改标准图片
- 暂无批改标准数据

## 根本原因

1. **API 只从 LangGraph state 读取数据**
   - `get_rubric_review_context` 只从 LangGraph 的运行时 state 读取
   - LangGraph state 在流程完成后可能被清理或不可访问

2. **缺少数据持久化读取**
   - 没有从数据库读取 `parsed_rubric`
   - 没有从文件存储读取 `rubric_images`

3. **数据库字段缺失**
   - `GradingHistory` 模型缺少 `rubric_data` 字段
   - 缺少 `current_stage` 字段用于追踪批改阶段

## 修复方案

### 1. 数据库模型更新

**文件**: `GradeOS-Platform/backend/src/db/postgres_grading.py`

添加字段到 `GradingHistory` 数据类：
```python
@dataclass
class GradingHistory:
    # ... 现有字段 ...
    rubric_data: Optional[Dict[str, Any]] = None  # 存储 parsed_rubric
    current_stage: Optional[str] = None  # 当前阶段
```

### 2. 数据库 Schema 更新

**文件**: `GradeOS-Platform/backend/src/db/postgres_grading.py`

在 `ensure_grading_history_schema()` 中添加：
```python
await conn.execute("ALTER TABLE grading_history ADD COLUMN IF NOT EXISTS rubric_data JSONB")
await conn.execute("ALTER TABLE grading_history ADD COLUMN IF NOT EXISTS current_stage VARCHAR(100)")
```

### 3. 保存逻辑更新

**文件**: `GradeOS-Platform/backend/src/graphs/batch_grading.py`

修改 export 节点，将 `parsed_rubric` 保存到 `rubric_data` 字段：
```python
parsed_rubric = state.get("parsed_rubric")
current_stage = state.get("current_stage")

grading_history = GradingHistory(
    # ... 其他字段 ...
    rubric_data=parsed_rubric,  # 保存到 rubric_data
    current_stage=current_stage,
    result_data={
        # 不再在这里保存 parsed_rubric
    },
)
```

### 4. API 读取逻辑增强

**文件**: `GradeOS-Platform/backend/src/api/routes/batch_langgraph.py`

为 `get_rubric_review_context` 添加多层 fallback：

```python
async def get_rubric_review_context(batch_id: str, orchestrator: Orchestrator):
    # 1. 优先从 LangGraph state 读取（实时数据）
    if orchestrator:
        run_info = await orchestrator.get_run_info(f"batch_grading_{batch_id}")
        if run_info and (run_info.state.get("parsed_rubric") or run_info.state.get("rubric_images")):
            return RubricReviewContextResponse(...)
    
    # 2. Fallback: 从数据库和文件存储读取
    return await _load_from_db()

async def _load_from_db():
    # 从数据库读取 parsed_rubric
    history = await get_grading_history(batch_id)
    parsed_rubric = history.rubric_data
    
    # 从文件存储读取 rubric 图片
    rubric_images = await _load_rubric_images_from_storage()
    
    return RubricReviewContextResponse(
        parsed_rubric=parsed_rubric,
        rubric_images=rubric_images,
        ...
    )
```

## 数据库迁移

执行迁移脚本添加新字段：

```bash
cd GradeOS-Platform/backend
psql $DATABASE_URL -f migrations/add_rubric_data_fields.sql
```

或者让应用自动迁移（通过 `ensure_grading_history_schema()`）。

## 测试验证

使用测试脚本验证修复：

```bash
cd GradeOS-Platform/backend
python test_rubric_review_fix.py <batch_id>
```

预期输出：
```
✅ 找到批改历史
✅ rubric_data 存在
   - 总题数: 5
   - 总分: 100
✅ 找到 3 个 rubric 文件
```

## 影响范围

### 修改的文件
1. `backend/src/db/postgres_grading.py` - 数据模型和 Schema
2. `backend/src/graphs/batch_grading.py` - 保存逻辑
3. `backend/src/api/routes/batch_langgraph.py` - API 读取逻辑

### 新增的文件
1. `backend/migrations/add_rubric_data_fields.sql` - 数据库迁移脚本
2. `backend/test_rubric_review_fix.py` - 测试脚本

### 向后兼容性
- ✅ 新字段使用 `ADD COLUMN IF NOT EXISTS`，不影响现有数据
- ✅ 读取逻辑有 fallback，兼容旧数据
- ✅ 现有 API 不受影响

## 部署步骤

1. **备份数据库**（生产环境）
   ```bash
   pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
   ```

2. **部署代码**
   ```bash
   git pull
   # 重启后端服务
   ```

3. **验证迁移**
   - 应用启动时会自动执行 `ensure_grading_history_schema()`
   - 或手动执行迁移脚本

4. **测试验证**
   - 访问批改标准复核页面
   - 确认能看到题目和图片

## 预期效果

修复后，批改标准复核页面应该能够：
- ✅ 显示正确的题目数量和总分
- ✅ 显示所有批改标准图片
- ✅ 显示完整的评分标准数据
- ✅ 支持编辑和重新解析

## 注意事项

1. **旧批次数据**：修复前创建的批次可能没有 `rubric_data`，需要重新批改或手动迁移
2. **文件存储**：确保 rubric 图片已正确保存到文件存储（通过 `save_rubric_files`）
3. **性能**：JSONB 字段已添加 GIN 索引，查询性能良好

## 相关 Issue

- 批改标准复核无法访问已保存 rubric 和 rubric 图片
- 前端显示"共 0 题，总分 0"
- 图片区域显示"暂无批改标准图片"
