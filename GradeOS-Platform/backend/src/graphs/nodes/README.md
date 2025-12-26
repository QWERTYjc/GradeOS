# LangGraph 节点模块

本模块包含将 Temporal Activity 重写为 LangGraph Node 的实现。

## 概述

在从 Temporal 迁移到 LangGraph 的过程中，我们将原有的 Activity 重写为 Node 函数。每个 Node 都是一个纯函数，接收 `GradingGraphState` 作为输入，返回更新后的状态。

## 节点列表

### 1. segment_node - 文档分割节点

**文件**: `segment.py`

**功能**: 使用 LayoutAnalysisService 调用 Gemini 2.5 Flash Lite 识别试卷中的题目边界。

**输入状态字段**:
- `submission_id`: 提交 ID
- `file_paths`: 文件路径列表

**输出状态字段**:
- `artifacts.segmentation_results`: 分割结果列表
- `progress.segmentation_completed`: 分割完成标志
- `progress.total_questions`: 总题目数
- `current_stage`: "segmentation_completed"
- `percentage`: 20.0

**重试策略**:
- 初始间隔: 2.0 秒
- 退避系数: 2.0
- 最大间隔: 60.0 秒
- 最大尝试次数: 3
- 不可重试错误: `ValueError` (无法识别题目)

**使用示例**:
```python
from src.graphs.nodes import segment_node

state = {
    "submission_id": "sub_123",
    "file_paths": ["/path/to/page1.jpg", "/path/to/page2.jpg"],
    # ... 其他字段
}

result_state = await segment_node(state)
```

### 2. grade_node - 批改节点

**文件**: `grade.py`

**功能**: 首先检查语义缓存，缓存未命中时调用 LangGraph 智能体进行批改。对于高置信度结果（> 0.9），将其缓存到 Redis。

**输入状态字段**:
- `submission_id`: 提交 ID
- `rubric`: 评分标准
- `artifacts.segmentation_results`: 分割结果

**输出状态字段**:
- `grading_results`: 批改结果列表
- `total_score`: 总分
- `max_total_score`: 满分
- `progress.grading_completed`: 批改完成标志
- `progress.completed_questions`: 已完成题目数
- `current_stage`: "grading_completed"
- `percentage`: 20.0 + (完成题目数 / 总题目数 * 60.0)

**重试策略**:
- 初始间隔: 3.0 秒
- 退避系数: 2.0
- 最大间隔: 120.0 秒
- 最大尝试次数: 5
- 不可重试错误: `ValueError`, `TypeError`

**缓存策略**:
- 缓存命中: 直接返回缓存结果
- 缓存未命中: 调用智能体批改
- 高置信度 (> 0.9): 缓存结果到 Redis

**使用示例**:
```python
from src.graphs.nodes import grade_node

state = {
    "submission_id": "sub_123",
    "rubric": "评分标准文本",
    "artifacts": {
        "segmentation_results": [...]
    },
    # ... 其他字段
}

result_state = await grade_node(state)
```

### 3. persist_node - 持久化节点

**文件**: `persist.py`

**功能**: 将批改结果保存到 PostgreSQL，并更新提交状态。

**输入状态字段**:
- `submission_id`: 提交 ID
- `grading_results`: 批改结果列表
- `total_score`: 总分
- `max_total_score`: 满分

**输出状态字段**:
- `progress.persistence_completed`: 持久化完成标志
- `current_stage`: "persistence_completed"
- `percentage`: 90.0

**数据库操作**:
1. 保存各题目的批改结果到 `grading_results` 表
2. 更新提交的总分
3. 更新提交状态为 `COMPLETED`

**使用示例**:
```python
from src.graphs.nodes import persist_node

state = {
    "submission_id": "sub_123",
    "grading_results": [...],
    "total_score": 85.0,
    "max_total_score": 100.0,
    # ... 其他字段
}

result_state = await persist_node(state)
```

### 4. notify_node - 通知节点

**文件**: `notify.py`

**功能**: 当工作流完成或需要人工介入时发送通知。

**输入状态字段**:
- `submission_id`: 提交 ID
- `exam_id`: 考试 ID
- `student_id`: 学生 ID
- `needs_review`: 是否需要审核
- `grading_results`: 批改结果列表

**输出状态字段**:
- `progress.notification_sent`: 通知发送标志
- `current_stage`: "notification_sent"
- `percentage`: 100.0
- `artifacts.notification`: 通知内容

**通知类型**:
- `grading_completed`: 批改完成通知
- `review_required`: 需要人工审核通知

**使用示例**:
```python
from src.graphs.nodes import notify_node

state = {
    "submission_id": "sub_123",
    "exam_id": "exam_123",
    "student_id": "student_123",
    "needs_review": False,
    "grading_results": [...],
    # ... 其他字段
}

result_state = await notify_node(state)
```

### 5. notify_teacher_node - 教师通知节点

**文件**: `notify.py`

**功能**: 当批改置信度较低时，发送审核通知给教师。

**输入状态字段**:
- `submission_id`: 提交 ID
- `exam_id`: 考试 ID
- `student_id`: 学生 ID
- `grading_results`: 批改结果列表

**输出状态字段**:
- `artifacts.teacher_notification`: 教师通知内容

**低置信度阈值**: 0.7

**使用示例**:
```python
from src.graphs.nodes import notify_teacher_node

state = {
    "submission_id": "sub_123",
    "exam_id": "exam_123",
    "student_id": "student_123",
    "grading_results": [...],
    # ... 其他字段
}

result_state = await notify_teacher_node(state)
```

## 重试策略

所有节点都集成了重试策略，使用 `create_retryable_node` 工厂函数创建。重试策略包括：

- **指数退避**: 重试间隔按指数增长
- **最大尝试次数**: 限制重试次数
- **不可重试错误**: 某些错误不进行重试
- **降级处理**: 重试耗尽时执行降级逻辑

## 错误处理

节点的错误处理遵循以下原则：

1. **可重试错误**: 临时故障（如 API 限流、网络超时）会自动重试
2. **不可重试错误**: 参数错误、逻辑错误不进行重试
3. **降级处理**: 重试耗尽时执行降级逻辑，记录错误并标记需要人工介入
4. **部分失败**: 某些节点（如通知）失败不会中断整个流程

## 状态更新

每个节点都会更新以下状态字段：

- `current_stage`: 当前阶段
- `percentage`: 进度百分比
- `progress`: 进度详情
- `timestamps`: 时间戳
- `artifacts`: 产物
- `errors`: 错误列表（如果有）

## 测试

单元测试位于 `tests/unit/test_graph_nodes.py`，包括：

- 基本功能测试
- 缓存命中/未命中测试
- 错误处理测试
- 通知类型测试

运行测试：
```bash
pytest tests/unit/test_graph_nodes.py -v
```

## 与 Temporal Activity 的对比

| 特性 | Temporal Activity | LangGraph Node |
|-----|------------------|----------------|
| 定义方式 | `@activity.defn` 装饰器 | 纯函数 |
| 状态管理 | 隐式（Temporal 管理） | 显式（State 对象） |
| 重试策略 | Temporal 配置 | 节点内部实现 |
| 检查点 | Temporal 自动保存 | LangGraph Checkpointer |
| 依赖注入 | 函数参数 | 函数内部初始化 |
| 错误处理 | 抛出异常 | 返回错误状态 |

## 下一步

这些节点将在后续任务中组装成完整的 Graph：

- `ExamPaperGraph`: 试卷批改 Graph
- `BatchGradingGraph`: 批量批改 Graph
- `RuleUpgradeGraph`: 规则升级 Graph

参见 `.kiro/specs/temporal-to-langgraph-migration/tasks.md` 中的任务 5 和 6。
