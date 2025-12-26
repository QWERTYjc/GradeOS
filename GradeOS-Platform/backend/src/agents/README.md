# LangGraph 批改智能体

## 概述

批改智能体使用 LangGraph 实现循环推理和自我反思，模拟人类教师的阅卷过程。

## 架构

```
vision_extraction → rubric_mapping → critique
                         ↑              ↓
                         └──────────────┘
                         (如果需要修正)
                              ↓
                        finalization → END
```

## 节点说明

### 1. vision_extraction_node
- **功能**：调用 Gemini 3.0 Pro 描述学生解答
- **输入**：question_image, rubric, standard_answer
- **输出**：vision_analysis

### 2. rubric_mapping_node
- **功能**：将评分点映射到证据
- **输入**：vision_analysis, rubric, max_score, critique_feedback
- **输出**：rubric_mapping, initial_score

### 3. critique_node
- **功能**：审查评分并生成反馈
- **输入**：vision_analysis, rubric, rubric_mapping, initial_score
- **输出**：critique_feedback, confidence, revision_count

### 4. finalization_node
- **功能**：格式化最终输出
- **输入**：所有状态
- **输出**：final_score, student_feedback, visual_annotations

## 条件边逻辑

根据需求 3.5，条件函数 `_should_revise` 决定是否需要修正：

- **修正条件**：有反思反馈 AND revision_count < 3
- **最终化条件**：无反思反馈 OR revision_count >= 3

## 使用示例

```python
from src.agents import GradingAgent
from src.services.gemini_reasoning import GeminiReasoningClient
from src.utils.checkpoint import create_checkpointer, get_thread_id

# 初始化客户端
reasoning_client = GeminiReasoningClient(api_key="your-api-key")

# 创建检查点保存器（可选）
checkpointer = create_checkpointer()

# 创建智能体
agent = GradingAgent(
    reasoning_client=reasoning_client,
    checkpointer=checkpointer
)

# 运行批改
result = await agent.run(
    question_image="base64_encoded_image",
    rubric="评分细则文本",
    max_score=10.0,
    standard_answer="标准答案（可选）",
    thread_id=get_thread_id("submission_123", "question_1")
)

# 访问结果
print(f"最终得分: {result['final_score']}/{result['max_score']}")
print(f"置信度: {result['confidence']}")
print(f"学生反馈: {result['student_feedback']}")
```

## 检查点持久化

根据需求 3.7，检查点会自动持久化到 PostgreSQL：

- **thread_id 格式**：`{submission_id}_{question_id}`
- **持久化时机**：每次状态转换
- **用途**：审计追踪、断点恢复

## 错误处理

所有节点都包含错误处理逻辑：

- 捕获异常并设置 `error` 字段
- 将 `confidence` 设置为 0.0（触发人工审核）
- 继续执行而不中断工作流
