# Requirements Document

## Introduction

本文档定义了批改工作流优化的需求，采用 LangGraph + AgentScope 架构，实现通过 Agent Skill 动态获取指定题目批改标准，解决跨页题目合并问题，并确保大规模并行批改能力。

核心目标：
1. 动态评分标准获取：批改 Worker 在批改时动态获取指定题目的评分标准
2. 跨页题目合并：解决一道题分两页导致小题当大题算、分数计算错误的问题
3. 并行批改能力：确保大规模批改的高速处理能力
4. 结果统一合并：分批并行操作后的结果需要智能合并

## Glossary

- **Grading_Worker**: 执行具体批改任务的工作单元，负责分析学生答案并给出评分
- **Agent_Skill**: Agent 可调用的技能模块，提供特定功能如获取评分标准、识别题目等
- **Rubric_Registry**: 评分标准注册中心，存储和管理所有题目的评分标准
- **Question_Merger**: 题目合并器，负责识别和合并跨页的同一道题目
- **Page_Batch**: 页面批次，一组待并行处理的页面
- **Grading_Result**: 批改结果，包含分数、反馈、题目详情等信息
- **Cross_Page_Question**: 跨页题目，指答案跨越多个页面的单道题目
- **Question_Context**: 题目上下文，包含题目编号、所在页面、评分标准等完整信息

## Requirements

### Requirement 1: 动态评分标准获取

**User Story:** As a 批改系统, I want to 在批改每道题时动态获取该题的评分标准, so that 批改 Worker 能够针对性地应用正确的评分规则。

#### Acceptance Criteria

1. WHEN Grading_Worker 开始批改一道题目 THEN THE Rubric_Registry SHALL 返回该题目的完整评分标准（包括得分点、标准答案、另类解法）
2. WHEN 评分标准包含多个得分点 THEN THE Grading_Worker SHALL 逐一核对每个得分点并记录得分情况
3. WHEN 题目存在另类解法 THEN THE Rubric_Registry SHALL 同时返回所有有效的解法及其评分条件
4. IF 请求的题目编号在 Rubric_Registry 中不存在 THEN THE System SHALL 返回默认评分规则并标记为低置信度
5. WHEN 评分标准被更新 THEN THE Rubric_Registry SHALL 确保后续批改使用最新版本

### Requirement 2: 跨页题目识别与合并

**User Story:** As a 批改系统, I want to 自动识别和合并跨越多页的同一道题目, so that 不会将小题当作大题计算，确保分数准确。

#### Acceptance Criteria

1. WHEN 同一题目的答案出现在连续多页 THEN THE Question_Merger SHALL 将这些页面的内容合并为单一题目上下文
2. WHEN 页面 N 的题目编号与页面 N+1 的题目编号相同 THEN THE Question_Merger SHALL 识别为跨页题目
3. WHEN 页面 N 的最后一道题未完成（无明确结束标记）且页面 N+1 以相同题号开始 THEN THE Question_Merger SHALL 合并这两部分内容
4. WHEN 合并跨页题目后 THEN THE System SHALL 只计算一次该题的满分，不重复计算
5. IF 跨页题目合并置信度低于阈值 THEN THE System SHALL 标记该题目需要人工确认
6. WHEN 题目包含子题（如 7a, 7b）THEN THE Question_Merger SHALL 正确识别子题关系并分别评分

### Requirement 3: 并行批改架构

**User Story:** As a 系统管理员, I want to 系统支持大规模并行批改, so that 能够快速处理大量学生试卷。

#### Acceptance Criteria

1. WHEN 接收到批量批改请求 THEN THE System SHALL 将页面分成多个 Page_Batch 并行处理
2. WHEN 并行批改执行时 THEN THE System SHALL 确保每个 Grading_Worker 独立获取所需的评分标准
3. WHEN 单个 Page_Batch 处理失败 THEN THE System SHALL 重试该批次而不影响其他批次
4. WHILE 并行批改进行中 THEN THE System SHALL 实时报告各批次的处理进度
5. WHEN 所有 Page_Batch 完成 THEN THE System SHALL 触发结果合并流程

### Requirement 4: 结果智能合并

**User Story:** As a 批改系统, I want to 智能合并分批并行处理的结果, so that 最终输出完整、准确的学生成绩。

#### Acceptance Criteria

1. WHEN 所有并行批次完成 THEN THE System SHALL 按页码顺序合并所有批改结果
2. WHEN 合并结果时发现同一题目被多次评分（跨页情况）THEN THE System SHALL 合并为单一评分记录
3. WHEN 合并跨页题目评分 THEN THE System SHALL 汇总所有得分点的得分，不重复计算满分
4. WHEN 检测到评分冲突（同一得分点不同分数）THEN THE System SHALL 标记冲突并选择置信度更高的结果
5. WHEN 合并完成 THEN THE System SHALL 验证总分等于各题得分之和
6. IF 总分验证失败 THEN THE System SHALL 标记该学生结果需要人工审核

### Requirement 5: Agent Skill 架构

**User Story:** As a 开发者, I want to 通过 Agent Skill 模块化批改能力, so that 系统具有良好的扩展性和可维护性。

#### Acceptance Criteria

1. THE System SHALL 提供 get_rubric_for_question Skill 用于获取指定题目的评分标准
2. THE System SHALL 提供 identify_question_numbers Skill 用于从页面图像中识别题目编号
3. THE System SHALL 提供 detect_cross_page_questions Skill 用于检测跨页题目
4. THE System SHALL 提供 merge_question_results Skill 用于合并同一题目的多个评分结果
5. WHEN Agent 调用 Skill THEN THE System SHALL 记录调用日志用于调试和审计
6. WHEN Skill 执行失败 THEN THE System SHALL 返回明确的错误信息并支持重试

### Requirement 6: 学生边界检测优化

**User Story:** As a 批改系统, I want to 在批改完成后准确检测学生边界, so that 能够正确归属每个学生的成绩。

#### Acceptance Criteria

1. WHEN 批改结果包含学生信息（姓名/学号）THEN THE System SHALL 优先使用该信息进行边界检测
2. WHEN 题目编号序列出现循环（如从大题号回到第1题）THEN THE System SHALL 识别为新学生开始
3. WHEN 检测到学生边界 THEN THE System SHALL 将该学生范围内的所有题目结果聚合
4. IF 学生边界检测置信度低于阈值 THEN THE System SHALL 标记需要人工确认
5. WHEN 聚合学生结果时 THEN THE System SHALL 正确处理跨页题目，避免重复计算

### Requirement 7: 评分标准解析增强

**User Story:** As a 批改系统, I want to 增强评分标准解析能力, so that 能够准确提取每道题的评分细则。

#### Acceptance Criteria

1. WHEN 解析评分标准 THEN THE Rubric_Parser SHALL 提取每道题的题号、满分、得分点
2. WHEN 评分标准包含子题 THEN THE Rubric_Parser SHALL 正确解析子题结构和分值
3. WHEN 评分标准包含另类解法 THEN THE Rubric_Parser SHALL 单独提取并标记
4. WHEN 解析完成 THEN THE System SHALL 验证解析出的总分与预期总分一致
5. IF 解析出的总分与预期不符 THEN THE System SHALL 发出警告并记录差异

### Requirement 8: 批改结果数据结构

**User Story:** As a 开发者, I want to 定义清晰的批改结果数据结构, so that 系统各组件能够正确交换数据。

#### Acceptance Criteria

1. THE Grading_Result SHALL 包含题目编号、得分、满分、置信度、反馈字段
2. THE Grading_Result SHALL 包含得分点明细列表，记录每个得分点的得分情况
3. THE Grading_Result SHALL 包含页面索引列表，记录该题目出现在哪些页面
4. THE Grading_Result SHALL 包含 is_cross_page 标记，指示是否为跨页题目
5. THE Grading_Result SHALL 包含 merge_source 字段，记录合并来源（如果是合并结果）
6. WHEN 序列化 Grading_Result THEN THE System SHALL 使用 JSON 格式

### Requirement 9: 错误处理与恢复

**User Story:** As a 系统管理员, I want to 系统具有完善的错误处理和恢复机制, so that 批改任务能够可靠完成。

#### Acceptance Criteria

1. WHEN API 调用失败 THEN THE System SHALL 使用指数退避策略重试最多3次
2. WHEN 单页批改失败 THEN THE System SHALL 记录错误并继续处理其他页面
3. WHEN 批次处理失败 THEN THE System SHALL 支持从失败点恢复
4. WHEN 发生不可恢复错误 THEN THE System SHALL 保存已完成的部分结果
5. THE System SHALL 记录详细的错误日志，包括错误类型、上下文、堆栈信息

### Requirement 10: 性能与可扩展性

**User Story:** As a 系统管理员, I want to 系统具有良好的性能和可扩展性, so that 能够处理大规模批改任务。

#### Acceptance Criteria

1. THE System SHALL 支持配置并行批次大小（默认10页/批次）
2. THE System SHALL 支持配置最大并发 Worker 数量
3. WHEN 处理100页试卷 THEN THE System SHALL 在5分钟内完成批改
4. THE System SHALL 支持水平扩展，通过增加 Worker 节点提升处理能力
5. THE System SHALL 提供性能监控指标（处理速度、队列长度、错误率）

### Requirement 11: 轻量级部署（无数据库依赖）

**User Story:** As a 用户, I want to 系统能够在不依赖线上数据库的情况下运行, so that 降低使用门槛，快速启动批改任务。

#### Acceptance Criteria

1. THE System SHALL 支持无数据库模式运行，所有状态保存在内存或本地文件
2. THE System SHALL 使用 LLM API（如 Gemini API）进行批改，不需要本地部署模型
3. WHEN 无数据库模式启动 THEN THE System SHALL 将评分标准缓存在内存中
4. THE System SHALL 支持将批改结果导出为 JSON 文件，无需数据库持久化
5. THE System SHALL 提供单文件或最小依赖的部署方式
6. WHEN 配置了数据库连接 THEN THE System SHALL 自动启用数据库持久化功能
7. IF 数据库连接失败 THEN THE System SHALL 降级到无数据库模式继续运行
8. THE System SHALL 支持通过环境变量配置运行模式（DATABASE_URL 为空则无数据库模式）
