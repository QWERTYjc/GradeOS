# LangGraph 工作流集成文档

## 概述

本文档描述了批改工作流优化中 LangGraph 工作流的集成实现，包括跨页题目合并、结果智能合并和无数据库模式支持。

## 实现的功能

### 1. 跨页题目合并节点 (cross_page_merge_node)

**位置**: `src/graphs/batch_grading.py`

**功能**:
- 在学生分割之前执行
- 检测跨越多个页面的同一道题目
- 合并跨页题目的评分结果
- 确保满分只计算一次，不重复计算

**工作流程**:
1. 接收并行批改的结果
2. 去重并按页码排序
3. 将字典格式转换为 `PageGradingResult` 对象
4. 使用 `ResultMerger` 检测和合并跨页题目
5. 将合并结果转换回字典格式
6. 返回合并后的题目列表和跨页题目信息

**Requirements**: 2.1, 4.2, 4.3

### 2. Result Merger 集成

**位置**: `src/services/result_merger.py`

**功能**:
- 合并多个批次的批改结果
- 按页码排序并去重
- 处理跨页题目合并
- 检测和解决评分冲突
- 验证总分等于各题得分之和

**在工作流中的使用**:
- `cross_page_merge_node`: 使用 `ResultMerger.merge_cross_page_questions()` 进行跨页合并
- `segment_node`: 使用合并后的题目结果进行学生分割，避免重复计算

**Requirements**: 4.1, 4.2, 4.3, 4.4, 4.5

### 3. 工作流状态更新

**位置**: `src/graphs/state.py`

**新增字段**:
```python
class BatchGradingGraphState(TypedDict, total=False):
    # 跨页题目合并结果
    merged_questions: List[Dict[str, Any]]  # 合并后的题目结果列表
    cross_page_questions: List[Dict[str, Any]]  # 跨页题目信息列表
```

**Requirements**: 8.1, 8.2, 8.3, 8.4, 8.5

### 4. JSON 结果导出

**位置**: `src/graphs/batch_grading.py` - `export_node`

**功能**:
- 支持无数据库模式下导出结果为 JSON 文件
- 包含跨页题目信息和合并后的题目结果
- 自动创建导出目录
- 生成带时间戳的文件名

**配置**:
- 环境变量 `EXPORT_DIR`: 指定导出目录（默认 `./exports`）

**导出格式**:
```json
{
  "batch_id": "批次ID",
  "export_time": "导出时间",
  "persisted": false,
  "cross_page_questions": [...],
  "merged_questions": [...],
  "students": [
    {
      "student_name": "学生姓名",
      "student_id": "学号",
      "score": 总分,
      "max_score": 满分,
      "percentage": 百分比,
      "question_results": [
        {
          "question_id": "题号",
          "score": 得分,
          "max_score": 满分,
          "is_cross_page": true/false,
          "page_indices": [页码列表],
          ...
        }
      ],
      ...
    }
  ]
}
```

**Requirements**: 11.4

## 更新的工作流

### 新的工作流顺序

```
intake (接收文件)
  ↓
preprocess (图像预处理)
  ↓
rubric_parse (解析评分标准)
  ↓
┌─────────────────┐
│ grade_batch (N) │  ← 并行批改（可配置批次大小）
└─────────────────┘
  ↓
cross_page_merge  ← 【新增】跨页题目合并
  ↓
segment (学生分割)
  ↓
review (结果审核)
  ↓
export (导出结果)
  ↓
END
```

### 关键改进

1. **跨页题目处理**: 在学生分割之前进行跨页合并，确保分数计算准确
2. **智能结果合并**: 使用 `ResultMerger` 统一处理批次合并和跨页合并
3. **无数据库支持**: 支持离线模式，自动导出 JSON 文件
4. **状态追踪**: 完整记录跨页题目信息和合并来源

## 测试

### 测试文件

`tests/unit/test_langgraph_integration.py`

### 测试覆盖

1. **test_cross_page_merge_node**: 测试跨页题目合并节点
   - 验证跨页题目检测
   - 验证合并后题目数量
   - 验证跨页题目信息

2. **test_export_node_with_merged_questions**: 测试导出节点支持合并后的题目
   - 验证导出数据包含跨页信息
   - 验证题目结果包含 `is_cross_page` 和 `page_indices`
   - 验证学生数据正确性

3. **test_export_node_json_export**: 测试无数据库模式下的 JSON 导出
   - 验证 JSON 文件创建
   - 验证 JSON 内容正确性
   - 验证文件路径返回

### 运行测试

```bash
cd GradeOS-Platform/backend
python -m pytest tests/unit/test_langgraph_integration.py -v
```

## 使用示例

### 创建批改 Graph

```python
from src.graphs.batch_grading import create_batch_grading_graph, BatchConfig

# 配置批次参数
config = BatchConfig(
    batch_size=10,
    max_concurrent_workers=5,
    max_retries=2
)

# 创建 Graph
graph = create_batch_grading_graph(batch_config=config)

# 执行批改
result = await graph.ainvoke({
    "batch_id": "batch_001",
    "answer_images": [...],
    "rubric_images": [...],
    "api_key": "your_api_key"
})

# 获取导出数据
export_data = result["export_data"]
students = export_data["students"]
cross_page_questions = export_data["cross_page_questions"]
```

### 访问合并结果

```python
# 获取合并后的题目
merged_questions = result.get("merged_questions", [])

# 查找跨页题目
for q in merged_questions:
    if q["is_cross_page"]:
        print(f"题目 {q['question_id']} 跨越页面: {q['page_indices']}")
        print(f"合并来源: {q['merge_source']}")
```

### 无数据库模式

```python
import os

# 设置导出目录
os.environ["EXPORT_DIR"] = "./my_exports"

# 执行批改（无数据库连接）
result = await graph.ainvoke({...})

# 获取 JSON 文件路径
json_file = result["export_data"].get("json_file")
if json_file:
    print(f"结果已导出到: {json_file}")
```

## 相关文件

- `src/graphs/batch_grading.py`: 批改工作流定义
- `src/graphs/state.py`: 工作流状态定义
- `src/services/result_merger.py`: 结果合并器
- `src/services/question_merger.py`: 题目合并器
- `src/models/grading_models.py`: 数据模型定义
- `tests/unit/test_langgraph_integration.py`: 集成测试

## 注意事项

1. **跨页合并顺序**: 必须在学生分割之前执行，否则可能导致分数重复计算
2. **数据格式转换**: 注意字典格式和对象格式之间的转换
3. **错误处理**: 跨页合并失败时会降级到不合并模式，不影响整体流程
4. **JSON 导出**: 仅在数据库持久化失败时才导出 JSON 文件
5. **环境变量**: 确保设置 `EXPORT_DIR` 以指定导出目录

## 未来改进

1. 支持更复杂的跨页检测算法
2. 优化大规模批改的内存使用
3. 添加更多的合并策略选项
4. 支持增量导出和断点续传
5. 添加更详细的合并日志和审计追踪
