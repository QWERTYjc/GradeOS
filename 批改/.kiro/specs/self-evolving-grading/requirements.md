# Requirements Document

## Introduction

本规格定义了 AI 批改系统的架构升级，核心目标是实现"自我成长"能力——系统能够从老师的反馈中持续学习，同时优化批改流程以支持流式传输和并行处理。升级后的系统将具备：固定分批并行批改、批改后学生分割、RAG 判例记忆、动态提示词、个性化校准、客观题确定性判分、以及自动规则升级机制。

## Glossary

- **Batch（批次）**：固定 10 张图片为一个处理单元
- **Exemplar（判例）**：老师确认过的正确批改示例，用于 few-shot 学习
- **Exemplar_Memory（判例记忆库）**：存储和检索判例的向量数据库
- **Rule_Patch（规则补丁）**：从老师改判中自动生成的判分规则修正
- **Confidence_Score（置信度分数）**：模型对批改结果的确定程度，范围 0.0-1.0
- **Streaming_Response（流式响应）**：通过 SSE/WebSocket 实时推送的批改进度数据
- **Student_Boundary（学生边界）**：标识一份试卷从哪一页到哪一页属于同一学生
- **Normalization_Rule（规范化规则）**：将学生答案转换为标准格式的规则（如单位换算、同义表达）
- **Calibration_Profile（校准配置）**：特定老师或学校的扣分规则、容差、措辞模板
- **Eval_Set（评测集）**：用于回归测试规则补丁的标注数据集
- **Grading_Log（批改日志）**：记录每次批改的完整上下文，用于后续分析

## Requirements

### Requirement 1: 流式批改进度传输

**User Story:** As a 教师, I want to 实时看到批改进度和中间结果, so that I can 及时了解系统工作状态并在必要时介入。

#### Acceptance Criteria

1. WHEN 批改任务启动 THEN THE Streaming_Service SHALL 建立 SSE 连接并开始推送进度事件
2. WHEN 单个页面批改完成 THEN THE Streaming_Service SHALL 在 500ms 内推送该页面的批改结果
3. WHEN 批次内所有页面并行批改完成 THEN THE Streaming_Service SHALL 推送批次汇总事件
4. WHEN 客户端断开连接后重连 THEN THE Streaming_Service SHALL 从上次断点继续推送未接收的事件
5. WHEN 批改过程中发生错误 THEN THE Streaming_Service SHALL 推送包含错误详情和重试建议的错误事件

### Requirement 2: 固定分批并行批改

**User Story:** As a 系统管理员, I want to 将试卷图片按固定批次并行处理, so that I can 最大化利用计算资源并保持可预测的处理时间。

#### Acceptance Criteria

1. WHEN 接收到试卷图片集合 THEN THE Batch_Processor SHALL 将图片按 10 张一组进行分批
2. WHEN 图片总数不足 10 张 THEN THE Batch_Processor SHALL 将剩余图片作为最后一个批次处理
3. WHEN 处理单个批次 THEN THE LangGraph_Executor SHALL 并行执行该批次内所有页面的批改
4. WHEN 批次内任一页面批改失败 THEN THE Batch_Processor SHALL 记录失败详情并继续处理其他页面
5. WHEN 批次处理完成 THEN THE Batch_Processor SHALL 汇总该批次的批改结果和统计信息

### Requirement 3: 批改后学生分割

**User Story:** As a 教师, I want to 系统自动识别每份试卷的页面范围, so that I can 按学生查看完整的批改结果。

#### Acceptance Criteria

1. WHEN 批次批改完成 THEN THE Student_Boundary_Detector SHALL 分析批改结果中的学生标识信息
2. WHEN 检测到学生标识变化 THEN THE Student_Boundary_Detector SHALL 标记新学生的起始页码
3. WHEN 学生标识信息缺失或模糊 THEN THE Student_Boundary_Detector SHALL 使用页面内容相似度和题目序列作为辅助判断依据
4. WHEN 分割结果置信度低于 0.8 THEN THE Student_Boundary_Detector SHALL 标记该边界为待人工确认
5. WHEN 分割完成 THEN THE Student_Boundary_Detector SHALL 输出每个学生的页面范围列表

### Requirement 4: RAG 判例记忆系统

**User Story:** As a 教师, I want to 系统记住我确认过的正确判例, so that 下次遇到类似情况时系统能自动参考这些判例。

#### Acceptance Criteria

1. WHEN 老师确认某个批改结果正确 THEN THE Exemplar_Memory SHALL 将该判例存入向量数据库
2. WHEN 存储判例 THEN THE Exemplar_Memory SHALL 记录题目类型、学生答案、评分结果、老师评语和确认时间
3. WHEN 批改新答案 THEN THE Exemplar_Memory SHALL 检索最相似的 3-5 个判例作为 few-shot 示例
4. WHEN 检索到的判例相似度低于 0.7 THEN THE Exemplar_Memory SHALL 不将该判例加入 prompt
5. WHEN 判例库容量超过阈值 THEN THE Exemplar_Memory SHALL 按使用频率和时效性淘汰旧判例

### Requirement 5: 动态提示词拼装

**User Story:** As a 系统, I want to 根据题型和上下文动态选择提示词模板, so that 批改质量能针对不同场景优化。

#### Acceptance Criteria

1. WHEN 识别到题目类型 THEN THE Prompt_Assembler SHALL 加载对应题型的基础提示词模板
2. WHEN 检测到特定错误模式 THEN THE Prompt_Assembler SHALL 追加针对该错误模式的引导提示
3. WHEN 上一次批改置信度低 THEN THE Prompt_Assembler SHALL 追加要求更详细推理的提示
4. WHEN 存在相关判例 THEN THE Prompt_Assembler SHALL 将判例格式化后插入 few-shot 区域
5. WHEN 提示词总长度超过模型上下文限制 THEN THE Prompt_Assembler SHALL 按优先级截断低优先级内容

### Requirement 6: 个性化校准配置

**User Story:** As a 教师, I want to 系统按照我的评分风格进行批改, so that 批改结果符合我的教学标准。

#### Acceptance Criteria

1. WHEN 教师首次使用系统 THEN THE Calibration_Service SHALL 创建默认校准配置
2. WHEN 教师修改扣分规则 THEN THE Calibration_Service SHALL 更新该教师的 Calibration_Profile
3. WHEN 批改任务关联特定教师 THEN THE Grading_Agent SHALL 加载该教师的校准配置
4. WHEN 校准配置包含容差设置 THEN THE Grading_Agent SHALL 在判分时应用指定的容差范围
5. WHEN 校准配置包含措辞模板 THEN THE Grading_Agent SHALL 使用指定模板生成评语

### Requirement 7: 客观题 LLM 评分与低置信度二次验证

**User Story:** As a 系统管理员, I want to 客观题由 LLM 完成评分并在低置信度时触发二次验证, so that 评分既灵活又可靠。

#### Acceptance Criteria

1. WHEN 处理客观题 THEN THE Objective_Grader SHALL 使用 LLM 完成答案识别和评分
2. WHEN LLM 完成评分 THEN THE Objective_Grader SHALL 输出评分结果和置信度分数
3. WHEN 评分置信度低于 0.85 THEN THE Objective_Grader SHALL 触发二次验证流程（使用不同提示词或第二模型）
4. WHEN 二次验证结果与首次不一致 THEN THE Objective_Grader SHALL 标记该题为待人工复核
5. WHEN 评分完成 THEN THE Objective_Grader SHALL 记录评分依据和推理过程用于后续分析

### Requirement 8: 批改日志记录

**User Story:** As a 系统, I want to 记录每次批改的完整上下文, so that 后续可以分析失败模式并生成规则补丁。

#### Acceptance Criteria

1. WHEN 完成一次批改 THEN THE Grading_Logger SHALL 记录提取结果、置信度、证据片段
2. WHEN 完成答案规范化 THEN THE Grading_Logger SHALL 记录规范化前后的答案
3. WHEN 完成判分匹配 THEN THE Grading_Logger SHALL 记录匹配结果和失败原因
4. WHEN 老师进行改判 THEN THE Grading_Logger SHALL 记录改判内容和改判原因
5. WHEN 日志写入失败 THEN THE Grading_Logger SHALL 将日志暂存本地并在恢复后重试

### Requirement 9: 自动规则升级机制

**User Story:** As a 系统管理员, I want to 系统自动从老师改判中学习并升级规则, so that 系统判分准确率持续提升。

#### Acceptance Criteria

1. WHEN 累积足够的老师改判样本 THEN THE Rule_Miner SHALL 分析高频失败模式
2. WHEN 识别到可修复的失败模式 THEN THE Patch_Generator SHALL 生成候选规则补丁
3. WHEN 生成候选补丁 THEN THE Regression_Tester SHALL 在 Eval_Set 上运行回归测试
4. WHEN 回归测试通过且误判率下降 THEN THE Patch_Deployer SHALL 将补丁加入灰度发布队列
5. WHEN 灰度发布期间出现异常 THEN THE Patch_Deployer SHALL 自动回滚到上一版本

### Requirement 10: 规则补丁版本管理

**User Story:** As a 系统管理员, I want to 管理和追踪所有规则补丁的版本, so that I can 随时回滚到任意历史版本。

#### Acceptance Criteria

1. WHEN 创建新规则补丁 THEN THE Version_Manager SHALL 分配唯一版本号并记录创建时间
2. WHEN 部署规则补丁 THEN THE Version_Manager SHALL 记录部署时间和部署范围
3. WHEN 请求回滚 THEN THE Version_Manager SHALL 恢复到指定版本的规则集
4. WHEN 查询补丁历史 THEN THE Version_Manager SHALL 返回包含版本号、创建时间、部署状态的列表
5. WHEN 补丁之间存在依赖 THEN THE Version_Manager SHALL 在回滚时处理依赖关系

### Requirement 11: 判例序列化与反序列化

**User Story:** As a 系统, I want to 将判例持久化存储并能准确恢复, so that 判例数据不会丢失且格式一致。

#### Acceptance Criteria

1. WHEN 存储判例 THEN THE Exemplar_Serializer SHALL 将判例转换为 JSON 格式
2. WHEN 加载判例 THEN THE Exemplar_Serializer SHALL 将 JSON 解析为判例对象
3. WHEN 序列化后再反序列化 THEN THE Exemplar_Serializer SHALL 产生与原始判例等价的对象
4. WHEN 判例包含图片引用 THEN THE Exemplar_Serializer SHALL 保留图片的存储路径或哈希值
5. WHEN 遇到格式不兼容的旧版判例 THEN THE Exemplar_Serializer SHALL 执行迁移转换
