# Implementation Plan: 批改工作流优化

## Overview

本实现计划将批改工作流优化分解为可执行的编码任务，采用增量开发方式，确保每个任务都能独立验证。实现顺序遵循依赖关系：数据模型 → 核心组件 → Agent Skills → 工作流集成 → 测试验证。

## Tasks

- [x] 1. 数据模型定义与序列化
  - [x] 1.1 定义核心数据模型（QuestionRubric, QuestionResult, PageGradingResult, StudentResult）
    - 在 `GradeOS-Platform/backend/src/models/grading_models.py` 中定义数据类
    - 包含所有必要字段：题目编号、得分、满分、置信度、反馈、得分点明细、页面索引、is_cross_page、merge_source
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [ ]* 1.2 编写属性测试：Grading_Result 数据结构完整性
    - **Property 8: Grading_Result 数据结构完整性**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
  - [x] 1.3 实现 JSON 序列化/反序列化方法
    - 为所有数据模型实现 to_dict() 和 from_dict() 方法
    - _Requirements: 8.6_
  - [ ]* 1.4 编写属性测试：JSON 序列化 Round-Trip
    - **Property 9: JSON 序列化 Round-Trip**
    - **Validates: Requirements 8.6**

- [-] 2. Rubric Registry 实现
  - [x] 2.1 实现 RubricRegistry 类
    - 创建 `GradeOS-Platform/backend/src/services/rubric_registry.py`
    - 实现评分标准的存储、查询、更新功能
    - 支持内存缓存模式
    - _Requirements: 1.1, 1.3, 1.5, 11.3_
  - [ ]* 2.2 编写属性测试：评分标准获取完整性
    - **Property 1: 评分标准获取完整性**
    - **Validates: Requirements 1.1, 1.3**
  - [x] 2.3 实现默认评分规则返回逻辑
    - 当题目不存在时返回默认规则并标记低置信度
    - _Requirements: 1.4_
  - [ ]* 2.4 编写属性测试：无数据库模式缓存行为
    - **Property 10: 无数据库模式缓存行为**
    - **Validates: Requirements 11.3**

- [x] 3. Checkpoint - 数据模型与 Registry 验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 4. Question Merger 实现
  - [x] 4.1 实现跨页题目检测逻辑
    - 创建 `GradeOS-Platform/backend/src/services/question_merger.py`
    - 实现 detect_cross_page_questions 方法
    - 检测连续页面相同题号、未完成题目延续等情况
    - _Requirements: 2.1, 2.2, 2.3_
  - [ ]* 4.2 编写属性测试：跨页题目识别正确性
    - **Property 2: 跨页题目识别正确性**
    - **Validates: Requirements 2.1, 2.2, 2.3**
  - [x] 4.3 实现跨页题目合并逻辑
    - 实现 merge_cross_page_results 方法
    - 确保满分只计算一次
    - 合并得分点结果
    - _Requirements: 2.4, 4.3_
  - [ ]* 4.4 编写属性测试：跨页题目满分不重复计算
    - **Property 3: 跨页题目满分不重复计算**
    - **Validates: Requirements 2.4, 4.3**
  - [x] 4.5 实现子题识别与处理
    - 正确识别子题关系（如 7a, 7b）
    - 分别评分并正确聚合
    - _Requirements: 2.6_
  - [x] 4.6 实现低置信度标记逻辑
    - 当合并置信度低于阈值时标记需人工确认
    - _Requirements: 2.5_

- [x] 5. Agent Skills 实现
  - [x] 5.1 创建 Agent Skills 基础架构
    - 创建 `GradeOS-Platform/backend/src/skills/grading_skills.py`
    - 定义 Skill 装饰器和注册机制
    - 实现调用日志记录
    - _Requirements: 5.5_
  - [x] 5.2 实现 get_rubric_for_question Skill
    - 从 RubricRegistry 获取指定题目的评分标准
    - _Requirements: 5.1, 1.1_
  - [x] 5.3 实现 identify_question_numbers Skill
    - 调用 LLM 从页面图像中识别题目编号
    - _Requirements: 5.2_
  - [x] 5.4 实现 detect_cross_page_questions Skill
    - 封装 QuestionMerger 的跨页检测功能
    - _Requirements: 5.3_
  - [x] 5.5 实现 merge_question_results Skill
    - 封装 QuestionMerger 的合并功能
    - _Requirements: 5.4_
  - [x] 5.6 实现 Skill 错误处理与重试
    - 返回明确错误信息
    - 支持重试机制
    - _Requirements: 5.6_

- [x] 6. Checkpoint - Skills 验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 7. Result Merger 实现
  - [x] 7.1 实现批次结果合并逻辑
    - 创建 `GradeOS-Platform/backend/src/services/result_merger.py`
    - 按页码排序合并
    - 去重处理
    - _Requirements: 4.1, 4.2_
  - [ ]* 7.2 编写属性测试：结果合并顺序正确性
    - **Property 5: 结果合并顺序正确性**
    - **Validates: Requirements 4.1, 4.2**
  - [x] 7.3 实现评分冲突处理
    - 检测同一得分点不同分数的情况
    - 选择置信度更高的结果
    - _Requirements: 4.4_
  - [x] 7.4 实现总分验证逻辑
    - 验证总分等于各题得分之和
    - 验证失败时标记需人工审核
    - _Requirements: 4.5, 4.6_
  - [ ]* 7.5 编写属性测试：总分等于各题得分之和
    - **Property 6: 总分等于各题得分之和**
    - **Validates: Requirements 4.5**

- [x] 8. Grading Worker 优化
  - [x] 8.1 重构 GradingWorker 使用 Agent Skills
    - 修改 `GradeOS-Platform/backend/src/services/gemini_reasoning.py`
    - 集成 RubricRegistry 和 GradingSkills
    - 实现动态评分标准获取
    - _Requirements: 1.1, 1.2_
  - [x] 8.2 实现得分点逐一核对逻辑
    - 为每个得分点记录得分情况
    - 生成详细的得分点明细
    - _Requirements: 1.2_
  - [x] 8.3 实现另类解法支持
    - 在评分时考虑另类解法
    - _Requirements: 1.3_

- [x] 9. 并行批改架构优化
  - [x] 9.1 优化批次分发逻辑
    - 修改 `GradeOS-Platform/backend/src/graphs/batch_grading.py`
    - 支持配置批次大小
    - _Requirements: 3.1, 10.1_
  - [x] 9.2 实现 Worker 独立性保证
    - 每个 Worker 独立获取评分标准
    - 不共享可变状态
    - _Requirements: 3.2_
  - [ ]* 9.3 编写属性测试：并行批次独立性与错误隔离
    - **Property 4: 并行批次独立性与错误隔离**
    - **Validates: Requirements 3.2, 3.3**
  - [x] 9.4 实现批次失败重试
    - 单批次失败不影响其他批次
    - 支持失败批次重试
    - _Requirements: 3.3, 9.3_
  - [x] 9.5 实现进度报告
    - 实时报告各批次处理进度
    - _Requirements: 3.4_

- [x] 10. Checkpoint - 并行批改验证
  - 确保所有测试通过，如有问题请询问用户

- [x] 11. 学生边界检测优化
  - [x] 11.1 优化学生边界检测逻辑
    - 修改 `GradeOS-Platform/backend/src/services/student_boundary_detector.py`
    - 优先使用批改结果中的学生信息
    - 改进题目循环检测算法
    - _Requirements: 6.1, 6.2_
  - [x] 11.2 实现学生结果聚合
    - 正确聚合学生范围内的所有题目
    - 处理跨页题目避免重复计算
    - _Requirements: 6.3, 6.5_
  - [ ]* 11.3 编写属性测试：学生边界检测与聚合正确性
    - **Property 7: 学生边界检测与聚合正确性**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
  - [x] 11.4 实现低置信度边界标记
    - 置信度低于阈值时标记需人工确认
    - _Requirements: 6.4_

- [x] 12. LangGraph 工作流集成
  - [x] 12.1 添加跨页题目合并节点
    - 在 batch_grading.py 中添加 cross_page_merge_node
    - 在 segment_node 之前执行
    - _Requirements: 2.1, 4.2_
  - [x] 12.2 集成 Result Merger
    - 在合并节点中使用 ResultMerger
    - _Requirements: 4.1, 4.3_
  - [x] 12.3 更新工作流状态定义
    - 在 state.py 中添加跨页题目相关字段
    - _Requirements: 8.1-8.5_
  - [x] 12.4 实现结果导出为 JSON
    - 支持无数据库模式下导出结果
    - _Requirements: 11.4_

- [x] 13. 轻量级部署支持
  - [x] 13.1 实现无数据库模式检测
    - 检测 DATABASE_URL 环境变量
    - 自动选择运行模式
    - _Requirements: 11.1, 11.8_
  - [x] 13.2 实现数据库降级逻辑
    - 数据库连接失败时自动降级
    - _Requirements: 11.6, 11.7_
  - [ ]* 13.3 编写属性测试：数据库降级行为
    - **Property 11: 数据库降级行为**
    - **Validates: Requirements 11.7**

- [x] 14. 错误处理完善
  - [x] 14.1 实现指数退避重试
    - API 调用失败时使用指数退避
    - 最多重试3次
    - _Requirements: 9.1_
  - [x] 14.2 实现错误隔离
    - 单页失败不影响其他页面
    - 记录错误并继续处理
    - _Requirements: 9.2_
  - [x] 14.3 实现部分结果保存
    - 不可恢复错误时保存已完成结果
    - _Requirements: 9.4_
  - [x] 14.4 实现详细错误日志
    - 记录错误类型、上下文、堆栈信息
    - _Requirements: 9.5_

- [x] 15. Final Checkpoint - 完整流程验证
  - 确保所有测试通过
  - 运行端到端测试验证完整流程
  - 如有问题请询问用户

## Notes

- 任务标记 `*` 的为可选测试任务，可根据时间跳过以加快 MVP 开发
- 每个属性测试应至少运行 100 次迭代
- Checkpoints 用于验证阶段性成果，确保增量开发的正确性
- 实现时优先保证核心功能，测试可在后续补充
