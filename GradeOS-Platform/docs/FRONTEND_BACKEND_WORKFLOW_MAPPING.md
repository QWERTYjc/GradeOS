# 前后端工作流节点映射文档

## 概述

本文档描述了 GradeOS AI 批改系统前后端工作流节点的对应关系，确保 WebSocket 事件能正确推送到前端 UI。

## 工作流架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LangGraph 批改工作流                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  intake → preprocess → rubric_parse → grade_batch → cross_page_merge            │
│                                           ↓              ↓                      │
│                                      (并行批改)     (跨页合并)                    │
│                                                          ↓                      │
│                                    segment → review → export → END              │
│                                       ↓        ↓        ↓                       │
│                                  (学生分割) (结果审核) (导出结果)                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 节点映射表

| 后端节点 ID | 前端节点 ID | 节点名称 | 是否并行容器 | 说明 |
|------------|------------|---------|-------------|------|
| `intake` | `intake` | 接收文件 | ❌ | 验证输入文件 |
| `preprocess` | `preprocess` | 图像预处理 | ❌ | 图像去噪、增强、旋转校正 |
| `rubric_parse` | `rubric_parse` | 解析评分标准 | ❌ | 使用 RubricParserService 解析 |
| `grade_batch` | `grade_batch` | 分批并行批改 | ✅ | 可配置批次大小，支持重试 |
| `cross_page_merge` | `cross_page_merge` | 跨页题目合并 | ❌ | 检测并合并跨页题目 |
| `segment` | `segment` | 学生分割 | ❌ | 基于批改结果智能判断边界 |
| `review` | `review` | 结果审核 | ❌ | 标记低置信度、待确认项 |
| `export` | `export` | 导出结果 | ❌ | JSON 导出、部分结果保存 |

## WebSocket 事件类型

### 节点状态事件

| 事件类型 | 触发时机 | 数据结构 |
|---------|---------|---------|
| `workflow_update` | 节点状态变化 | `{ nodeId, status, message }` |
| `parallel_agents_created` | 创建并行 Agent | `{ parentNodeId, agents }` |
| `agent_update` | Agent 状态更新 | `{ agentId, status, progress, output }` |

### 业务事件

| 事件类型 | 触发时机 | 数据结构 |
|---------|---------|---------|
| `rubric_parsed` | 评分标准解析完成 | `{ totalQuestions, totalScore }` |
| `batch_start` | 批次开始处理 | `{ batchIndex, totalBatches }` |
| `page_complete` | 单页批改完成 | `{ pageIndex, success, revisionCount }` |
| `batch_complete` | 批次处理完成 | `{ batchIndex, successCount, failureCount }` |
| `cross_page_detected` | 跨页题目检测完成 | `{ questions, mergedCount, crossPageCount }` |
| `students_identified` | 学生识别完成 | `{ students, studentCount }` |
| `review_completed` | 审核完成 | `{ summary }` |
| `workflow_completed` | 工作流完成 | `{ message, results, cross_page_questions }` |
| `workflow_error` | 工作流错误 | `{ message }` |

## 关键文件

### 后端
- `src/graphs/batch_grading.py` - LangGraph 工作流定义
- `src/api/routes/batch_langgraph.py` - WebSocket 事件推送

### 前端
- `src/store/consoleStore.ts` - 工作流状态管理
- `src/components/console/WorkflowGraph.tsx` - 工作流可视化
- `src/components/console/ResultsView.tsx` - 结果展示
- `src/services/ws.ts` - WebSocket 客户端

## 兼容性说明

后端 `_map_node_to_frontend()` 函数支持以下旧节点名称的兼容映射：

```python
{
    "grading": "grade_batch",        # 旧名称 → 新名称
    "detect_boundaries": "segment",
    "grade_student": "grade_batch",
    "aggregate": "review",
    "batch_persist": "export",
    "batch_notify": "export"
}
```

## 更新日志

- **2025-12-28**: 添加 `cross_page_merge` 节点，统一前后端节点 ID 命名
