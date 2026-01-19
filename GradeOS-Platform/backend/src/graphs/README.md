# LangGraph 编排模块

本模块提供了 LangGraph Graph 的状态定义和重试策略，用于替�?Temporal 工作流编排�?

## 模块结构

```
src/graphs/
├── __init__.py          # 模块导出
├── state.py             # Graph 状态类型定�?
├── retry.py             # 重试策略实现
└── README.md            # 本文�?
```

## 状态类�?

### GradingGraphState

用于单份试卷批改的状态定义�?

```python
from src.graphs import GradingGraphState, create_initial_grading_state

# 创建初始状�?
state = create_initial_grading_state(
    job_id="job_001",
    submission_id="sub_001",
    exam_id="exam_001",
    student_id="student_001",
    file_paths=["path/to/file.pdf"],
    rubric="评分细则内容"
)

# 增量更新状�?
updated_state = {
    **state,
    "current_stage": "grading",
    "percentage": 50.0,
    "grading_results": [{"question_id": "q1", "score": 8.5}]
}
```

### BatchGradingGraphState

用于批量批改多份试卷的状态定义�?

工作流程：`接收文件 �?图像预处�?�?解析评分标准 �?固定分批批改 �?学生分割 �?结果审核 �?导出结果`

```python
from src.graphs import BatchGradingGraphState, create_initial_batch_state

state = create_initial_batch_state(
    batch_id="batch_001",
    exam_id="exam_001",
    pdf_path="path/to/batch.pdf",
    rubric="评分细则"
)

# 新流程支持的字段
state["answer_images"] = ["base64_image_1", "base64_image_2"]  # 答题图像
state["rubric_images"] = ["base64_rubric_1"]  # 评分标准图像
state["api_key"] = "your_api_key"  # LLM API Key
```

### RuleUpgradeGraphState

用于规则升级流程的状态定义�?

```python
from src.graphs import RuleUpgradeGraphState, create_initial_upgrade_state

state = create_initial_upgrade_state(
    upgrade_id="upgrade_001",
    trigger_type="scheduled",
    time_window={"start": "2024-01-01", "end": "2024-01-31"}
)
```

## 重试策略

### RetryConfig

配置节点的重试行为�?

```python
from src.graphs import RetryConfig

# 自定义重试配�?
config = RetryConfig(
    initial_interval=1.0,        # 初始重试间隔（秒�?
    backoff_coefficient=2.0,     # 退避系�?
    maximum_interval=60.0,       # 最大重试间隔（秒）
    maximum_attempts=3,          # 最大重试次�?
    timeout=300.0,               # 单次执行超时（秒�?
    non_retryable_errors=[ValueError, TypeError]  # 不可重试的错误类�?
)

# 计算重试间隔
interval = config.calculate_interval(attempt=2)  # �?2 次重试的间隔
```

### 预定义配�?

```python
from src.graphs import (
    DEFAULT_RETRY_CONFIG,        # 默认配置
    LLM_API_RETRY_CONFIG,     # LLM API 配置（处理限流）
    FAST_FAIL_RETRY_CONFIG,      # 快速失败配�?
    PERSISTENCE_RETRY_CONFIG,    # 持久化操作配�?
)
```

### with_retry

为异步函数添加重试逻辑�?

```python
from src.graphs import with_retry, RetryConfig

async def call_LLM_api(prompt: str) -> str:
    # 调用 LLM API
    ...

config = RetryConfig(maximum_attempts=5)
result = await with_retry(call_LLM_api, config, "你好")
```

### create_retryable_node

创建带重试的 LangGraph 节点�?

```python
from src.graphs import create_retryable_node, LLM_API_RETRY_CONFIG
from src.graphs.state import GradingGraphState

async def grade_node(state: GradingGraphState) -> GradingGraphState:
    # 批改逻辑
    result = await call_LLM_api(state["rubric"])
    return {**state, "grading_results": [result]}

async def fallback_node(state: GradingGraphState, error: Exception) -> GradingGraphState:
    # 降级逻辑：使用缓存结果或默认�?
    return {**state, "grading_results": [], "error": str(error)}

# 创建可重试节�?
retryable_grade_node = create_retryable_node(
    grade_node,
    LLM_API_RETRY_CONFIG,
    fallback_func=fallback_node,
    node_name="grade_question"
)
```

## 错误处理

### 错误记录

节点执行失败时，错误会自动记录到状态中�?

```python
{
    "errors": [
        {
            "node": "grade_question",
            "error_type": "RuntimeError",
            "error_message": "API 限流",
            "timestamp": "2024-01-01T12:00:00"
        }
    ],
    "retry_count": 3
}
```

### 降级处理

当所有重试都失败时，可以提供降级函数�?

```python
async def fallback_func(state: GradingGraphState, error: Exception) -> GradingGraphState:
    # 记录错误
    logger.error(f"节点执行失败: {error}")
    
    # 返回部分结果或默认�?
    return {
        **state,
        "current_stage": "partial_failure",
        "error": str(error)
    }
```

## 使用示例

### 完整的节点定�?

```python
from src.graphs import (
    GradingGraphState,
    create_retryable_node,
    LLM_API_RETRY_CONFIG,
)

async def segment_document(state: GradingGraphState) -> GradingGraphState:
    """文档分割节点"""
    file_paths = state["file_paths"]
    
    # 执行分割逻辑
    segments = await perform_segmentation(file_paths)
    
    return {
        **state,
        "current_stage": "segmented",
        "percentage": 25.0,
        "artifacts": {"segments": segments},
        "timestamps": {
            **state.get("timestamps", {}),
            "segmented_at": datetime.now().isoformat()
        }
    }

async def segment_fallback(state: GradingGraphState, error: Exception) -> GradingGraphState:
    """分割失败降级处理"""
    return {
        **state,
        "current_stage": "segmentation_failed",
        "error": f"文档分割失败: {error}"
    }

# 创建可重试节�?
segment_node = create_retryable_node(
    segment_document,
    LLM_API_RETRY_CONFIG,
    fallback_func=segment_fallback,
    node_name="segment_document"
)
```

## �?LangGraph 集成

```python
from langgraph.graph import StateGraph
from src.graphs import GradingGraphState

# 创建 Graph
graph = StateGraph(GradingGraphState)

# 添加节点
graph.add_node("segment", segment_node)
graph.add_node("grade", grade_node)
graph.add_node("persist", persist_node)

# 添加�?
graph.set_entry_point("segment")
graph.add_edge("segment", "grade")
graph.add_edge("grade", "persist")

# 编译 Graph
compiled_graph = graph.compile()
```

## 批量批改 Graph (batch_grading)

批量批改 Graph 实现�?先批改后分割"的工作流，支持并行处理多页试卷�?

### 流程�?

```
intake (接收文件)
    �?
preprocess (图像预处�?
    �?
rubric_parse (解析评分标准)
    �?
┌─────────────────�?
�?grade_batch (N) �? �?固定分批并行批改
└─────────────────�?
    �?
segment (学生分割)  �?基于批改结果智能判断学生边界
    �?
review (结果审核)
    �?
export (导出结果)
    �?
  END
```

### 节点说明

| 节点 | 功能 | 输出 |
|------|------|------|
| `intake` | 验证输入文件 | `current_stage`, `percentage` |
| `preprocess` | 图像去噪、增强、旋转校�?| `processed_images` |
| `rubric_parse` | LLM 解析评分标准 | `parsed_rubric` |
| `grade_batch` | 并行批改（每�?5 页） | `grading_results` (聚合) |
| `segment` | 基于批改结果检测学生边�?| `student_boundaries`, `student_results` |
| `review` | 标记低置信度结果 | `review_summary` |
| `export` | 持久化并准备导出 | `export_data` |

### 使用示例

```python
from src.graphs.batch_grading import create_batch_grading_graph

# 创建 Graph
graph = create_batch_grading_graph()

# 准备输入状�?
initial_state = {
    "batch_id": "batch_001",
    "answer_images": ["base64_img_1", "base64_img_2", ...],
    "rubric_images": ["base64_rubric"],
    "rubric": "评分细则文本",
    "api_key": "your_LLM_api_key"
}

# 执行
result = await graph.ainvoke(initial_state)

# 获取结果
print(f"学生�? {len(result['student_results'])}")
for student in result["student_results"]:
    print(f"  {student['student_key']}: {student['total_score']}/{student['max_total_score']}")
```

## 最佳实�?

1. **使用预定义配�?*：优先使�?`LLM_API_RETRY_CONFIG` 等预定义配置
2. **提供降级函数**：为关键节点提供降级逻辑，避免整个流程失�?
3. **记录详细日志**：在节点中记录执行细节，便于排查问题
4. **合理设置超时**：根据节点的实际执行时间设置合理的超时�?
5. **区分错误类型**：将不可重试的错误（如参数错误）加入 `non_retryable_errors`

## 测试

运行单元测试�?

```bash
# 测试状态定�?
pytest tests/unit/test_graphs_state.py -v

# 测试重试策略
pytest tests/unit/test_graphs_retry.py -v
```

## 相关文档

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [设计文档](.kiro/specs/temporal-to-langgraph-migration/design.md)
- [任务列表](.kiro/specs/temporal-to-langgraph-migration/tasks.md)
