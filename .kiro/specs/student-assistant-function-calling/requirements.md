# Requirements Document

## Introduction

本需求文档定义了为 GradeOS 学生 AI 助手添加 function calling 能力的功能需求。通过集成 function calling，AI 助手能够动态查询数据库中与学生相关的批改结果、成绩、进度等数据，提供更精准、更个性化的学习辅导。

## Glossary

- **Student Assistant**: 学生 AI 助手，为学生提供学习辅导、答疑解惑的 AI 系统
- **Function Calling**: LLM 的工具调用能力，允许 AI 模型调用预定义的函数来获取外部数据
- **Grading Result**: 批改结果，包含学生作业的得分、反馈、错题分析等信息
- **Knowledge Mastery**: 知识掌握度，学生对特定知识点的掌握程度评估
- **Tool Schema**: 工具函数的定义，包括函数名、参数、返回值等
- **LLM Client**: 大语言模型客户端，负责与 AI 模型通信
- **Database Query**: 数据库查询，从 PostgreSQL 或 SQLite 中检索数据

## Requirements

### Requirement 1

**User Story:** 作为学生，我希望 AI 助手能够查询我的历史成绩和批改结果，以便获得基于真实数据的学习建议

#### Acceptance Criteria

1. WHEN 学生询问自己的成绩或批改结果 THEN the Student Assistant SHALL 调用数据库查询工具获取学生的批改历史
2. WHEN 查询批改历史 THEN the System SHALL 返回学生的得分、最高分、批改时间、作业标题等信息
3. WHEN 批改结果包含多个作业 THEN the System SHALL 按时间倒序排列并限制返回数量
4. WHEN 数据库查询失败 THEN the System SHALL 返回空结果并记录错误日志
5. WHEN 学生询问特定作业的详细结果 THEN the Student Assistant SHALL 调用工具获取该作业的题目级别详情

### Requirement 2

**User Story:** 作为学生，我希望 AI 助手能够分析我的知识点掌握情况，以便了解自己的薄弱环节

#### Acceptance Criteria

1. WHEN 学生询问知识点掌握情况 THEN the Student Assistant SHALL 调用知识掌握度查询工具
2. WHEN 查询知识掌握度 THEN the System SHALL 返回学生在各知识点的掌握水平、正确率、最近评估时间
3. WHEN 知识点数据存在 THEN the System SHALL 计算掌握度百分比并标识薄弱知识点
4. WHEN 学生询问特定科目的知识点 THEN the System SHALL 支持按科目过滤查询结果
5. WHEN 知识点数据为空 THEN the System SHALL 返回提示信息说明暂无数据

### Requirement 3

**User Story:** 作为学生，我希望 AI 助手能够查看我的错题记录，以便针对性地复习

#### Acceptance Criteria

1. WHEN 学生询问错题或薄弱题目 THEN the Student Assistant SHALL 调用错题记录查询工具
2. WHEN 查询错题记录 THEN the System SHALL 返回题目内容、学生答案、正确答案、错误类型、反馈建议
3. WHEN 错题记录包含多个题目 THEN the System SHALL 按错误严重程度和时间排序
4. WHEN 学生询问特定类型的错题 THEN the System SHALL 支持按错误类型、科目、知识点过滤
5. WHEN 错题记录包含批注坐标 THEN the System SHALL 保留坐标信息以便前端渲染

### Requirement 4

**User Story:** 作为学生，我希望 AI 助手能够查询我的作业提交记录，以便了解自己的学习进度

#### Acceptance Criteria

1. WHEN 学生询问作业提交情况 THEN the Student Assistant SHALL 调用作业提交查询工具
2. WHEN 查询作业提交 THEN the System SHALL 返回作业标题、提交时间、批改状态、得分
3. WHEN 作业未批改 THEN the System SHALL 显示"待批改"状态
4. WHEN 学生询问特定班级的作业 THEN the System SHALL 支持按班级 ID 过滤查询
5. WHEN 作业提交记录为空 THEN the System SHALL 返回友好提示信息

### Requirement 5

**User Story:** 作为学生，我希望 AI 助手能够查看班级统计数据，以便了解自己在班级中的相对位置

#### Acceptance Criteria

1. WHEN 学生询问班级平均分或排名 THEN the Student Assistant SHALL 调用班级统计查询工具
2. WHEN 查询班级统计 THEN the System SHALL 返回班级平均分、最高分、最低分、及格率
3. WHEN 学生成绩存在 THEN the System SHALL 计算学生在班级中的相对位置
4. WHEN 班级统计数据不存在 THEN the System SHALL 返回提示信息说明暂无统计数据
5. WHEN 查询特定作业的班级统计 THEN the System SHALL 支持按作业 ID 过滤

### Requirement 6

**User Story:** 作为开发者，我希望 function calling 系统能够自动选择合适的工具，以便 AI 助手智能响应学生问题

#### Acceptance Criteria

1. WHEN LLM 收到学生消息 THEN the System SHALL 分析消息内容并决定是否需要调用工具
2. WHEN 需要调用工具 THEN the System SHALL 根据工具 schema 生成正确的函数调用参数
3. WHEN 工具调用完成 THEN the System SHALL 将工具返回的数据整合到 LLM 的上下文中
4. WHEN 工具调用失败 THEN the System SHALL 捕获异常并返回降级响应
5. WHEN 单次对话需要多个工具 THEN the System SHALL 支持连续调用多个工具

### Requirement 7

**User Story:** 作为开发者，我希望工具函数定义清晰且易于扩展，以便未来添加更多查询能力

#### Acceptance Criteria

1. WHEN 定义工具函数 THEN the System SHALL 使用标准的 JSON Schema 格式定义参数
2. WHEN 工具函数执行 THEN the System SHALL 返回结构化的 JSON 数据
3. WHEN 添加新工具 THEN the System SHALL 支持通过配置注册新工具而无需修改核心代码
4. WHEN 工具函数需要权限控制 THEN the System SHALL 验证学生只能查询自己的数据
5. WHEN 工具函数需要性能优化 THEN the System SHALL 支持查询结果缓存

### Requirement 8

**User Story:** 作为学生，我希望 AI 助手能够基于查询到的数据生成个性化建议，以便更有效地学习

#### Acceptance Criteria

1. WHEN AI 助手获取到学生数据 THEN the System SHALL 分析数据并生成针对性建议
2. WHEN 学生成绩下降 THEN the System SHALL 识别趋势并提供改进建议
3. WHEN 学生在某知识点表现薄弱 THEN the System SHALL 推荐相关练习资源
4. WHEN 学生询问学习计划 THEN the System SHALL 基于历史数据生成个性化学习路径
5. WHEN 数据不足以生成建议 THEN the System SHALL 提示学生完成更多作业以获得更好的分析

### Requirement 9

**User Story:** 作为系统管理员，我希望 function calling 的执行过程可追踪，以便调试和优化

#### Acceptance Criteria

1. WHEN 工具被调用 THEN the System SHALL 记录工具名称、参数、执行时间到日志
2. WHEN 工具调用失败 THEN the System SHALL 记录详细的错误堆栈信息
3. WHEN 工具返回数据 THEN the System SHALL 记录返回数据的大小和结构摘要
4. WHEN 需要性能分析 THEN the System SHALL 提供工具调用的性能指标统计
5. WHEN 需要审计 THEN the System SHALL 记录哪个学生在何时调用了哪些工具

### Requirement 10

**User Story:** 作为学生，我希望 AI 助手能够生成我的学习进度报告，以便全面了解自己的学习情况和成长趋势

#### Acceptance Criteria

1. WHEN 学生询问学习进度或成长趋势 THEN the Student Assistant SHALL 调用进度报告生成工具
2. WHEN 生成进度报告 THEN the System SHALL 返回总作业数、完成数、平均分、成绩趋势、知识点进度
3. WHEN 进度报告包含成绩趋势 THEN the System SHALL 按时间顺序展示学生的分数变化
4. WHEN 学生在班级中有排名 THEN the System SHALL 显示学生在班级中的相对位置
5. WHEN 学生达成特定成就 THEN the System SHALL 在报告中展示成就徽章和描述

### Requirement 11

**User Story:** 作为学生，我希望 AI 助手的响应速度快，即使需要查询数据库

#### Acceptance Criteria

1. WHEN 工具查询数据库 THEN the System SHALL 使用异步查询避免阻塞
2. WHEN 查询结果可缓存 THEN the System SHALL 使用 Redis 缓存频繁查询的数据
3. WHEN 查询涉及大量数据 THEN the System SHALL 限制返回结果数量并分页
4. WHEN 多个工具需要调用 THEN the System SHALL 支持并行执行独立的工具调用
5. WHEN 工具执行超时 THEN the System SHALL 在 5 秒内返回超时错误并降级响应

