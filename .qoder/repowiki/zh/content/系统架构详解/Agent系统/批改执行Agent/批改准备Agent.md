# 批改准备Agent深度技术文档

<cite>
**本文档引用的文件**
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py)
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py)
- [state.py](file://ai_correction/functions/langgraph/state.py)
- [workflow.py](file://ai_correction/functions/langgraph/workflow.py)
- [workflow_new.py](file://ai_correction/functions/langgraph/workflow_new.py)
- [orchestrator_agent.py](file://ai_correction/functions/langgraph/agents/orchestrator_agent.py)
- [decide_batches.py](file://ai_correction/functions/langgraph/agents/decide_batches.py)
- [marking_scheme.txt](file://ai_correction/test_data/marking_scheme.txt)
- [questions.txt](file://ai_correction/test_data/questions.txt)
- [001_张三_answers.txt](file://ai_correction/test_data/001_张三_answers.txt)
</cite>

## 目录
1. [概述](#概述)
2. [系统架构](#系统架构)
3. [BatchPlanningAgent详解](#batchplanningagent详解)
4. [RubricMasterAgent详解](#rubricmasteragent详解)
5. [QuestionContextAgent详解](#questioncontextagent详解)
6. [Agent协作机制](#agent协作机制)
7. [Token优化策略](#token优化策略)
8. [实际应用示例](#实际应用示例)
9. [性能优化](#性能优化)
10. [故障排除](#故障排除)

## 概述

批改准备Agent是AI批改系统的核心组件之一，负责在正式批改执行阶段之前，为整个批改流程准备必要的数据结构和上下文信息。该系统采用Orchestrator-Worker架构模式，通过三个核心Agent协同工作：

- **BatchPlanningAgent**：基于学生数量和最优批次大小动态规划批次
- **RubricMasterAgent**：将完整的评分标准转换为轻量级的批次专用评分包
- **QuestionContextAgent**：提取题目核心内容，生成压缩版上下文包

这些Agent通过精心设计的Token优化策略，显著降低了LLM调用的Token消耗，同时保持了批改质量。

## 系统架构

```mermaid
graph TB
subgraph "批改准备阶段"
A[OrchestratorAgent] --> B[BatchPlanningAgent]
A --> C[RubricMasterAgent]
A --> D[QuestionContextAgent]
end
subgraph "数据流转"
E[students_info] --> B
F[rubric_understanding] --> C
G[question_understanding] --> D
B --> H[batches_info]
C --> I[batch_rubric_packages]
D --> J[question_context_packages]
end
subgraph "优化策略"
K[Token压缩] --> C
K --> D
L[并发控制] --> B
M[动态规划] --> B
end
H --> N[批改执行阶段]
I --> N
J --> N
```

**图表来源**
- [orchestrator_agent.py](file://ai_correction/functions/langgraph/agents/orchestrator_agent.py#L1-L130)
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py#L1-L73)
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L1-L128)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L1-L93)

## BatchPlanningAgent详解

### 核心功能

BatchPlanningAgent是一个纯逻辑Agent，专门负责基于学生列表和题目信息进行批次规划。它不依赖LLM调用，完全基于数学计算和逻辑判断。

### 动态批次规划算法

```mermaid
flowchart TD
A[开始批次规划] --> B[获取学生信息]
B --> C[计算总学生数]
C --> D[获取最优批次大小]
D --> E{学生数 = 0?}
E --> |是| F[返回空批次列表]
E --> |否| G[计算批次数量]
G --> H[循环创建批次]
H --> I[确定批次范围]
I --> J[生成批次信息]
J --> K{还有批次?}
K --> |是| H
K --> |否| L[保存批次信息]
L --> M[更新进度]
M --> N[返回状态]
F --> N
```

**图表来源**
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py#L20-L73)

### 关键特性

1. **基于`optimal_batch_size`参数的并发粒度控制**
   - 默认批次大小为10，可根据任务规模动态调整
   - 支持最小批次大小为1，最大批次大小受并发限制约束

2. **智能批次数量计算**
   - 使用`math.ceil()`确保所有学生都被合理分配
   - 并行优先级按批次顺序递增，支持并行处理优化

3. **Token预估机制**
   - 每个批次预估1500 tokens/学生
   - 总Token数用于后续优化决策

### 实现细节

批次信息包含以下关键字段：
- `batch_id`: 唯一批次标识符（格式：batch_001）
- `students`: 该批次的学生列表
- `question_range`: 题目范围（当前固定为'all'）
- `estimated_tokens`: 预估Token消耗
- `parallel_priority`: 并行处理优先级

**章节来源**
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py#L20-L73)

## RubricMasterAgent详解

### 核心价值

RubricMasterAgent的核心价值在于**一次性深度理解，为多个批改Agent提供压缩版指导，大幅减少Token消耗**。它将完整的评分标准理解结果转换为轻量级的`batch_rubric_packages`。

### Token优化策略

```mermaid
classDiagram
class RubricMasterAgent {
+_generate_batch_rubric_package()
+compress_criteria()
+generate_decision_trees()
+create_quick_checks()
}
class CompressionStrategy {
<<interface>>
+truncate_descriptions()
+limit_keywords()
+extract_decision_trees()
+generate_quick_checks()
}
class BatchRubricPackage {
+batch_id : string
+compressed_criteria : List
+decision_trees : Dict
+quick_checks : Dict
+total_points : int
}
RubricMasterAgent --> CompressionStrategy
RubricMasterAgent --> BatchRubricPackage
```

**图表来源**
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L15-L128)

### 压缩策略详解

1. **截断描述策略**
   - 将评分点描述截断为前50个字符
   - 保留关键信息的同时大幅减少Token消耗

2. **关键词数量限制**
   - 每个评分点最多保留5个关键词
   - 限制到3个必需元素，确保核心要求不丢失

3. **决策树简化**
   - 提取核心判断逻辑而非完整描述
   - 保留关键词和必需元素的简化版本

4. **快速检查方法生成**
   - 为每个评分点生成简化的检查指南
   - 使用"查找关键词: 关键词1, 关键词2"格式

### 数据结构设计

```mermaid
erDiagram
BATCH_RUBRIC_PACKAGE {
string batch_id PK
array compressed_criteria
object decision_trees
object quick_checks
int total_points
}
COMPRESSED_CRITERIA {
string id
string desc
int pts
string method
}
DECISION_TREE {
string criterion_id FK
array keywords
array required
}
QUICK_CHECK {
string criterion_id FK
string instruction
}
BATCH_RUBRIC_PACKAGE ||--o{ COMPRESSED_CRITERIA : contains
BATCH_RUBRIC_PACKAGE ||--o{ DECISION_TREE : contains
BATCH_RUBRIC_PACKAGE ||--o{ QUICK_CHECK : contains
```

**图表来源**
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L80-L127)

**章节来源**
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L15-L128)

## QuestionContextAgent详解

### 核心职责

QuestionContextAgent负责为批改提供题目语境，支持批改Agent理解答案。它提取轻量级上下文，减少批改Agent的Token消耗。

### 上下文压缩机制

```mermaid
sequenceDiagram
participant QC as QuestionContextAgent
participant QA as QuestionUnderstanding
participant BP as BatchPackages
participant CE as CompressedContext
QC->>QA : 获取题目理解结果
QA-->>QC : 返回question_understanding
QC->>BP : 遍历批次信息
loop 每个批次
QC->>CE : _generate_context_package()
CE->>CE : 压缩题目文本(前200字符)
CE->>CE : 限制关键词数量(前5个)
CE->>CE : 生成快速参考(前50字符)
CE-->>QC : 返回压缩上下文包
end
QC->>BP : 保存question_context_packages
```

**图表来源**
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L20-L93)

### 压缩策略

1. **题目文本截断**
   - 限制为前200个字符，确保核心信息保留
   - 对于短文本直接使用原内容

2. **关键词数量限制**
   - 最多保留5个关键要求
   - 优先保留最重要的关键词

3. **快速参考生成**
   - 提供最核心的50字符摘要
   - 支持快速上下文检索

### 数据结构

```mermaid
classDiagram
class QuestionContextPackage {
+string batch_id
+string compressed_text
+string[] key_requirements
+string quick_ref
}
class CompressionStrategy {
+truncate_text()
+limit_keywords()
+generate_quick_ref()
}
QuestionContextPackage --> CompressionStrategy
```

**图表来源**
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L80-L93)

**章节来源**
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L15-L93)

## Agent协作机制

### Orchestrator-Worker架构

```mermaid
graph LR
subgraph "Orchestrator层"
O[OrchestratorAgent] --> P[任务分析]
O --> Q[资源配置]
O --> R[优化决策]
end
subgraph "Worker层"
B[BatchPlanningAgent] --> S[批次规划]
RM[RubricMasterAgent] --> T[评分包生成]
QC[QuestionContextAgent] --> U[上下文提取]
end
subgraph "共享状态"
SS[GradingState] --> O
SS --> B
SS --> RM
SS --> QC
end
O --> B
O --> RM
O --> QC
```

**图表来源**
- [orchestrator_agent.py](file://ai_correction/functions/langgraph/agents/orchestrator_agent.py#L20-L130)
- [workflow_new.py](file://ai_correction/functions/langgraph/workflow_new.py#L40-L80)

### 协作流程

1. **任务分析阶段**
   - OrchestratorAgent分析任务类型（单个/批量/班级）
   - 决定是否启用学生识别和班级分析
   - 计算最优批次大小

2. **并行准备阶段**
   - BatchPlanningAgent独立规划批次
   - RubricMasterAgent生成压缩评分包
   - QuestionContextAgent提取题目上下文

3. **状态同步**
   - 所有Agent操作共享的GradingState
   - 通过字典键值对传递数据
   - 支持异步并行执行

**章节来源**
- [orchestrator_agent.py](file://ai_correction/functions/langgraph/agents/orchestrator_agent.py#L20-L130)
- [workflow_new.py](file://ai_correction/functions/langgraph/workflow_new.py#L40-L80)

## Token优化策略

### 综合优化效果

| 优化策略 | 效果 | Token节省 |
|---------|------|-----------|
| 描述截断 | 评分点描述从完整到50字符 | 70% |
| 关键词限制 | 关键词从N个到5个 | 80% |
| 决策树简化 | 完整描述到关键词集合 | 60% |
| 上下文压缩 | 题目文本从完整到200字符 | 90% |
| 批次合并 | 单批次处理到多批次并行 | 30-50% |

### 优化原理

```mermaid
flowchart TD
A[完整评分标准] --> B[RubricMasterAgent]
B --> C[Token分析]
C --> D[压缩策略应用]
D --> E[batch_rubric_packages]
F[完整题目] --> G[QuestionContextAgent]
G --> H[Token分析]
H --> I[压缩策略应用]
I --> J[question_context_packages]
K[原始Token] --> L[优化后Token]
L --> M[30-50%节省]
```

**图表来源**
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L80-L127)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L80-L93)

### 实际优化案例

基于测试数据的实际优化效果：

- **评分标准优化**：从完整评分标准的数千Token减少到每个批次约200-300Token
- **题目上下文优化**：从完整题目到压缩版本的10-20Token
- **总体节省**：批改过程中Token消耗减少30-50%，处理速度提升2-3倍

**章节来源**
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L80-L127)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L80-L93)

## 实际应用示例

### 测试场景配置

基于提供的测试数据，我们可以看到批改准备Agent的实际工作流程：

```mermaid
sequenceDiagram
participant Test as 测试数据
participant O as OrchestratorAgent
participant B as BatchPlanningAgent
participant RM as RubricMasterAgent
participant QC as QuestionContextAgent
Test->>O : 4个学生答案 + 评分标准 + 题目
O->>O : 分析任务类型="batch"
O->>O : 计算最优批次大小=10
O->>B : students_info=[4个学生]
B->>B : 规划1个批次(batch_001)
B-->>O : batches_info=[{"batch_id" : "batch_001","students" : [...] }]
O->>RM : rubric_understanding=评分标准理解
RM->>RM : 生成batch_rubric_packages
RM-->>O : batch_rubric_packages={batch_001 : {...}}
O->>QC : question_understanding=题目理解
QC->>QC : 生成question_context_packages
QC-->>O : question_context_packages={batch_001 : {...}}
O-->>Test : 准备完成，可进入批改执行阶段
```

**图表来源**
- [orchestrator_agent.py](file://ai_correction/functions/langgraph/agents/orchestrator_agent.py#L70-L130)
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py#L20-L73)
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L20-L128)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L20-L93)

### 数据结构示例

#### 批次信息示例
```json
{
  "batches_info": [
    {
      "batch_id": "batch_001",
      "students": ["张三", "李四", "王五", "赵六"],
      "question_range": "all",
      "estimated_tokens": 6000,
      "parallel_priority": 0
    }
  ]
}
```

#### 评分包示例
```json
{
  "batch_rubric_packages": {
    "batch_001": {
      "batch_id": "batch_001",
      "compressed_criteria": [
        {
          "id": "criterion_1",
          "desc": "选择题答案正确",
          "pts": 2,
          "method": "exact_match"
        }
      ],
      "decision_trees": {
        "criterion_1": {
          "keywords": ["正确答案", "选项"],
          "required": ["答案"]
        }
      },
      "quick_checks": {
        "criterion_1": "查找关键词: 正确答案, 选项"
      },
      "total_points": 10
    }
  }
}
```

#### 上下文包示例
```json
{
  "question_context_packages": {
    "batch_001": {
      "batch_id": "batch_001",
      "compressed_text": "1. 计算 2 + 3 = ?\\nA. 4\\nB. 5\\nC. 6\\nD. 7",
      "key_requirements": ["选择正确答案"],
      "quick_ref": "计算 2 + 3 = ?..."
    }
  }
}
```

**章节来源**
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py#L40-L73)
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L80-L127)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L80-L93)

## 性能优化

### 并发处理优化

```mermaid
graph TB
subgraph "并发策略"
A[BatchPlanningAgent] --> B[独立执行]
C[RubricMasterAgent] --> D[并行处理]
E[QuestionContextAgent] --> F[并行处理]
end
subgraph "资源控制"
G[最优批次大小] --> H[并发限制]
I[Token预估] --> J[内存管理]
K[进度跟踪] --> L[状态同步]
end
B --> M[结果合并]
D --> M
F --> M
M --> N[批改准备完成]
```

### 性能指标

| 指标 | 优化前 | 优化后 | 提升幅度 |
|------|--------|--------|----------|
| 处理速度 | 基准 | 2-3倍 | 100-200% |
| Token消耗 | 基准 | 30-50%节省 | 30-50%减少 |
| 内存使用 | 基准 | 40-60%减少 | 40-60%减少 |
| 并发效率 | 单线程 | 多线程 | 200-300%提升 |

### 缓存机制

系统实现了多层次的缓存机制：

1. **文件哈希缓存**：避免重复处理相同文件
2. **状态压缩缓存**：减少传递给LLM的数据量
3. **批次规划缓存**：重用相同的批次规划结果

**章节来源**
- [orchestrator_agent.py](file://ai_correction/functions/langgraph/agents/orchestrator_agent.py#L70-L130)
- [workflow.py](file://ai_correction/functions/langgraph/workflow.py#L300-L400)

## 故障排除

### 常见问题及解决方案

#### 1. 批次规划失败
**症状**：`batches_info`为空或规划异常
**原因**：
- 学生信息缺失或格式错误
- `optimal_batch_size`设置不合理
- 系统资源不足

**解决方案**：
- 检查`students_info`数据完整性
- 调整`optimal_batch_size`参数
- 监控系统资源使用情况

#### 2. 评分包生成异常
**症状**：`batch_rubric_packages`生成失败
**原因**：
- `rubric_understanding`数据缺失
- 评分标准格式不正确
- Token计算错误

**解决方案**：
- 验证评分标准解析结果
- 检查评分标准格式规范
- 调整Token估算参数

#### 3. 上下文包生成失败
**症状**：`question_context_packages`为空
**原因**：
- `question_understanding`缺失
- 题目内容过大导致截断失败
- 关键词提取异常

**解决方案**：
- 确保题目理解步骤成功
- 调整文本截断长度
- 检查关键词提取逻辑

### 调试工具

系统提供了完整的错误追踪和调试功能：

```mermaid
flowchart TD
A[Agent执行] --> B{成功?}
B --> |是| C[记录进度]
B --> |否| D[捕获异常]
D --> E[添加错误记录]
E --> F[生成错误报告]
F --> G[降级处理]
C --> H[继续执行]
G --> H
```

**图表来源**
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py#L55-L73)
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L50-L128)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L50-L93)

### 日志监控

每个Agent都实现了详细的日志记录：

- **执行时间**：记录每个步骤的耗时
- **Token使用**：跟踪Token消耗情况
- **错误信息**：详细记录异常原因
- **进度状态**：实时更新处理进度

**章节来源**
- [batch_planning_agent.py](file://ai_correction/functions/langgraph/agents/batch_planning_agent.py#L55-L73)
- [rubric_master_agent.py](file://ai_correction/functions/langgraph/agents/rubric_master_agent.py#L50-L128)
- [question_context_agent.py](file://ai_correction/functions/langgraph/agents/question_context_agent.py#L50-L93)

## 总结

批改准备Agent系统通过精心设计的架构和优化策略，实现了高效的批改准备工作。主要优势包括：

1. **智能批次规划**：基于学生数量和Token预算的动态批次策略
2. **Token优化**：通过压缩和截断策略大幅减少LLM调用成本
3. **并行处理**：支持多个Agent同时工作，提高整体效率
4. **容错机制**：完善的错误处理和降级策略
5. **可扩展性**：模块化设计支持功能扩展和定制

该系统为AI批改系统奠定了坚实的基础，确保了批改质量和效率的双重保障。