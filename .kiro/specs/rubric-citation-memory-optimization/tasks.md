# Implementation Plan: 评分标准引用和 Confession 系统优化

## Overview

基于 OpenAI Confessions 核心设计原则，实现评分标准引用和 Confession 系统优化。技术栈：Python 3.11+, FastAPI, LangGraph, Hypothesis（属性测试）。

## Tasks

- [ ] 1. 扩展数据模型
  - [ ] 1.1 扩展 ScoringPointResult 添加评分标准引用字段
    - 在 `src/models/grading_models.py` 中添加 rubric_reference、rubric_text、citation_quality、is_alternative_solution、alternative_reason、confidence_adjustment 字段
    - 更新 to_dict() 和 from_dict() 方法
    - _Requirements: 1.4, 7.1_
  
  - [ ] 1.2 扩展 MemoryEntry 添加验证状态字段
    - 在 `src/services/grading_memory.py` 中添加 MemoryVerificationStatus 枚举
    - 添加 verification_status、verified_at、verified_by、conflict_with、generalization_scope 字段
    - 更新 to_dict() 和 from_dict() 方法
    - _Requirements: 2.5, 3.5, 7.2_
  
  - [ ]* 1.3 编写数据模型单元测试
    - 测试新增字段的序列化/反序列化
    - 测试边界值处理
    - _Requirements: 7.5_

- [ ] 2. 实现 Confession 报告结构
  - [ ] 2.1 创建 Confession 数据类
    - 创建 `src/services/grading_confession.py`
    - 实现 ConfessionReport、InstructionItem、ComplianceItem、UncertaintyItem 数据类
    - _Requirements: 1.5_
  
  - [ ] 2.2 实现 generate_confession() 函数
    - 实现 _extract_instructions() 提取指令和约束
    - 实现 _analyze_compliance() 分析合规性
    - 实现 _identify_uncertainties() 识别不确定性
    - 实现 _calculate_honesty_score() 计算诚实度分数
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  
  - [ ]* 2.3 编写 Confession 结构属性测试
    - **Property 4: Confession 三部分结构完整性**
    - **Validates: Requirements 1.5**
    - _Requirements: 1.5_

- [ ] 3. Checkpoint - 确保数据模型测试通过
  - 运行 `pytest tests/unit/test_grading_models.py -v`
  - 如有问题请询问用户

- [ ] 4. 实现 Confession-Memory 双向连接
  - [ ] 4.1 实现 ConfessionMemoryUpdater 服务
    - 创建 `src/services/confession_memory_updater.py`
    - 实现 process_confession() 方法
    - 实现 process_human_feedback() 方法
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [ ] 4.2 扩展 GradingMemoryService 支持验证状态
    - 添加 update_verification_status() 方法
    - 添加 get_memories_by_verification_status() 方法
    - 添加 rollback_memories_by_time_range() 方法
    - _Requirements: 3.3, 3.4_
  
  - [ ]* 4.3 编写 Confession-Memory 属性测试
    - **Property 5: 低置信度记忆记录**
    - **Property 6: 不确定性风险信号记录**
    - **Property 7: 人工确认记忆验证**
    - **Property 8: 人工修正记忆更新**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 5. 实现记忆防护机制
  - [ ] 5.1 实现记忆自动降级逻辑
    - 在 GradingMemoryService 中添加 _check_and_degrade_memory() 方法
    - 当 contradiction_count > confirmation_count 且 >= 3 时降级
    - _Requirements: 2.6, 6.3_
  
  - [ ] 5.2 实现记忆冲突检测
    - 添加 _detect_memory_conflict() 方法
    - 检测相同 subject 和 question_type 下的语义冲突
    - _Requirements: 6.1_
  
  - [ ] 5.3 实现记忆泛化范围限制
    - 添加 _enforce_generalization_scope() 方法
    - 限制 subjects <= 3, question_types <= 5
    - _Requirements: 6.2_
  
  - [ ]* 5.4 编写记忆防护属性测试
    - **Property 9: 记忆自动降级**
    - **Property 12: 记忆科目隔离**
    - **Validates: Requirements 2.6, 6.3, 6.4**
    - _Requirements: 2.6, 6.3, 6.4_

- [ ] 6. Checkpoint - 确保记忆系统测试通过
  - 运行 `pytest tests/unit/test_grading_memory.py -v`
  - 如有问题请询问用户

- [ ] 7. 扩展 LLM Prompt 强制评分标准引用
  - [ ] 7.1 修改 _build_grading_prompt() 添加 Confession 要求
    - 在 `src/services/llm_reasoning.py` 中添加 Confession 输出要求
    - 强制要求输出 rubric_reference 和 rubric_text
    - 添加 citation_quality 评估要求
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [ ] 7.2 修改 _parse_grading_response() 解析 Confession
    - 解析 LLM 返回的 confession 部分
    - 验证 Confession 三部分结构完整性
    - _Requirements: 1.5_
  
  - [ ]* 7.3 编写 LLM 输出解析属性测试
    - **Property 1: 评分标准引用输出完整性**
    - **Property 2: 缺失引用检测与置信度降低**
    - **Validates: Requirements 1.1, 1.2, 1.4**
    - _Requirements: 1.1, 1.2, 1.4_

- [ ] 8. 确保逻辑复核独立性
  - [ ] 8.1 审查 logic_review_node 确保不访问记忆系统
    - 检查 `src/graphs/batch_grading.py` 中的 logic_review_node
    - 确保不导入或调用 GradingMemoryService
    - 添加代码注释说明独立性要求
    - _Requirements: 4.1, 4.2_
  
  - [ ]* 8.2 编写逻辑复核独立性属性测试
    - **Property 10: 逻辑复核独立性**
    - **Validates: Requirements 4.3**
    - _Requirements: 4.3_

- [ ] 9. 集成 Confession 到批改工作流
  - [ ] 9.1 在 batch_grading.py 中添加 confession_node
    - 在 logic_review_node 之后添加 confession_node
    - 调用 generate_confession() 生成 Confession 报告
    - 调用 ConfessionMemoryUpdater.process_confession() 更新记忆
    - _Requirements: 2.1, 2.2_
  
  - [ ] 9.2 扩展 BatchGradingGraphState 添加 Confession 字段
    - 添加 confession_reports 和 confession_memory_updates 字段
    - _Requirements: 7.3_
  
  - [ ]* 9.3 编写工作流集成测试
    - 测试 Confession 节点正确执行
    - 测试记忆更新正确触发
    - _Requirements: 2.1, 2.2_

- [ ] 10. 实现人工反馈 API
  - [ ] 10.1 添加人工反馈 API 端点
    - 在 `src/api/routes/unified_api.py` 中添加 POST /api/grading/feedback 端点
    - 实现 HumanFeedbackRequest 和 HumanFeedbackResponse 模型
    - 调用 ConfessionMemoryUpdater.process_human_feedback()
    - _Requirements: 2.3, 2.4_
  
  - [ ]* 10.2 编写人工反馈 API 测试
    - 测试确认反馈正确更新记忆状态
    - 测试修正反馈正确记录修正历史
    - _Requirements: 2.3, 2.4_

- [ ] 11. Final Checkpoint - 确保所有测试通过
  - 运行 `pytest tests/ -v`
  - 运行 `make quality` 检查代码质量
  - 如有问题请询问用户

## Notes

- 任务标记 `*` 的为可选测试任务，可跳过以加快 MVP 开发
- 每个属性测试至少运行 100 次迭代
- 属性测试使用 Hypothesis 库
- 代码风格遵循 Black + Ruff（100 字符行宽）
