# Requirements Document

## Introduction

本功能旨在优化 GradeOS AI 批改系统的评分标准引用和记忆系统。核心目标是：
1. 确保 AI 评分时必须给出具体的评分标准引用，明确哪一条标准支撑了哪一步评分
2. 实现自白驱动的记忆更新机制，让 AI 能够根据自白结果自我迭代
3. 确保逻辑复核节点保持无状态，作为记忆系统的"制衡"

## Glossary

- **Rubric_Citation**: 评分标准引用，指 AI 评分时引用的具体评分标准条目
- **Grading_Memory_Service**: 批改记忆服务，管理批改经验的积累、存储、检索和共享
- **Self_Report**: 批改自白，用于辅助人工核查的自我报告
- **Logic_Review**: 逻辑复核，无状态的独立验证节点
- **Confidence_Score**: 置信度分数，表示 AI 对评分结果的确信程度
- **Alternative_Solution**: 另类解法，学生使用的非标准但可能正确的解题方法
- **Memory_Entry**: 记忆条目，存储在记忆系统中的单条经验记录
- **Calibration_Stats**: 校准统计，用于调整置信度预测的历史数据

## Requirements

### Requirement 1: 评分标准强制引用

**User Story:** As a 教师, I want AI 评分时必须给出具体的评分标准引用, so that 我能清楚地看到每一步评分的依据。

#### Acceptance Criteria

1. WHEN AI 对某个得分点进行评分 THEN THE Scoring_System SHALL 输出该得分点对应的评分标准条目编号和原文
2. WHEN AI 评分结果中缺少评分标准引用 THEN THE Self_Report SHALL 标记该评分点为"缺失引用"并降低置信度
3. WHEN AI 识别到学生使用另类解法 THEN THE Scoring_System SHALL 标记为"另类解法"并将置信度降低至少 0.15
4. THE Scoring_Point_Result SHALL 包含 rubric_reference 字段，记录引用的评分标准条目
5. WHEN 评分标准引用与实际评分不一致 THEN THE Self_Report SHALL 生成警告信息

### Requirement 2: 自白驱动的记忆更新

**User Story:** As a 系统管理员, I want AI 能够根据自白结果自我迭代, so that 批改质量能够持续提升。

#### Acceptance Criteria

1. WHEN Self_Report 识别到低置信度评分 THEN THE Grading_Memory_Service SHALL 记录该模式为待验证记忆
2. WHEN Self_Report 识别到缺失证据 THEN THE Grading_Memory_Service SHALL 记录该模式为风险信号
3. WHEN 人工复核确认 AI 评分正确 THEN THE Grading_Memory_Service SHALL 将相关记忆标记为已验证
4. WHEN 人工复核修正 AI 评分 THEN THE Grading_Memory_Service SHALL 记录修正历史并更新置信度校准
5. THE Grading_Memory_Service SHALL 区分"可信记忆"和"待验证记忆"两种状态
6. WHEN 记忆被多次证伪 THEN THE Grading_Memory_Service SHALL 降低该记忆的可信度或删除

### Requirement 3: 记忆分层与可审计

**User Story:** As a 系统管理员, I want 记忆系统是分层的、可审计的、可回滚的, so that 我能够追踪和管理 AI 的学习过程。

#### Acceptance Criteria

1. THE Grading_Memory_Service SHALL 支持短期记忆（当前批次）和长期记忆（历史积累）两层存储
2. WHEN 存储新记忆 THEN THE Grading_Memory_Service SHALL 记录来源批次、创建时间、验证状态
3. THE Grading_Memory_Service SHALL 提供记忆查询接口，支持按科目、类型、时间范围过滤
4. WHEN 管理员请求回滚 THEN THE Grading_Memory_Service SHALL 能够删除指定时间范围内的记忆
5. THE Grading_Memory_Service SHALL 记录每条记忆的确认次数和证伪次数

### Requirement 4: 逻辑复核无状态独立性

**User Story:** As a 系统架构师, I want 逻辑复核节点保持无状态, so that 它能作为记忆系统的独立制衡。

#### Acceptance Criteria

1. THE Logic_Review SHALL 不访问 Grading_Memory_Service 的任何记忆数据
2. WHEN Logic_Review 执行评分验证 THEN THE Logic_Review SHALL 仅基于当前评分结果和评分标准进行判断
3. THE Logic_Review SHALL 独立计算置信度，不受历史记忆影响
4. WHEN Logic_Review 发现评分问题 THEN THE Logic_Review SHALL 生成独立的修正建议
5. THE Logic_Review 的输出 SHALL 作为记忆系统更新的输入之一

### Requirement 5: 置信度与引用关联

**User Story:** As a 教师, I want 置信度能够反映评分标准引用的质量, so that 我能快速识别需要重点复核的评分。

#### Acceptance Criteria

1. WHEN 评分点有明确的评分标准引用 THEN THE Confidence_Score SHALL 保持或提高
2. WHEN 评分点缺少评分标准引用 THEN THE Confidence_Score SHALL 降低至少 0.2
3. WHEN 使用另类解法评分 THEN THE Confidence_Score SHALL 降低至少 0.15
4. WHEN 评分标准引用与学生答案匹配度低 THEN THE Confidence_Score SHALL 降低
5. THE Scoring_Point_Result SHALL 包含 citation_quality 字段，表示引用质量（high/medium/low/missing）

### Requirement 6: 记忆防护机制

**User Story:** As a 系统管理员, I want 记忆系统有防护机制, so that 能够防止错误累积和过度泛化。

#### Acceptance Criteria

1. WHEN 新记忆与已有高可信度记忆冲突 THEN THE Grading_Memory_Service SHALL 标记冲突并请求人工审核
2. THE Grading_Memory_Service SHALL 限制单个模式的泛化范围，不超过指定的科目和题型
3. WHEN 记忆的证伪次数超过确认次数 THEN THE Grading_Memory_Service SHALL 自动降级或删除该记忆
4. THE Grading_Memory_Service SHALL 支持按科目隔离记忆，防止跨科目污染
5. WHEN 批次完成后 THEN THE Grading_Memory_Service SHALL 执行记忆整合，合并重复模式

### Requirement 7: 数据模型扩展

**User Story:** As a 开发者, I want 数据模型支持评分标准引用和记忆状态, so that 系统能够完整记录评分过程。

#### Acceptance Criteria

1. THE Scoring_Point_Result SHALL 扩展包含 rubric_reference、citation_quality、is_alternative_solution 字段
2. THE Memory_Entry SHALL 扩展包含 verification_status（verified/pending/contradicted）字段
3. THE Self_Report SHALL 扩展包含 citation_issues 列表，记录引用相关问题
4. THE Question_Result SHALL 扩展包含 rubric_citations 汇总字段
5. WHEN 序列化评分结果 THEN THE Scoring_System SHALL 包含完整的引用信息
