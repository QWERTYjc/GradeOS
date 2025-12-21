# Implementation Plan

## Phase 1: 流式传输与分批处理基础设施

- [-] 1. 实现流式推送服务


- [x] 1.1 创建 StreamingService 类和 SSE 事件模型


  - 实现 StreamEvent、EventType 数据模型
  - 实现 create_stream、push_event、close_stream 方法
  - 添加 Redis 事件队列支持
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 1.2 编写属性测试：流式事件推送及时性


  - **Property 31: 流式事件推送及时性**
  - **Validates: Requirements 1.2**

- [x] 1.3 实现断点续传功能


  - 创建 stream_events 表迁移
  - 实现 get_events 方法支持 from_sequence 参数
  - 添加事件持久化和恢复逻辑
  - _Requirements: 1.4_

- [x] 1.4 编写属性测试：断点续传正确性


  - **Property 32: 断点续传正确性**
  - **Validates: Requirements 1.4**

- [x] 1.5 实现错误事件推送



  - 添加错误事件类型和格式
  - 实现错误详情和重试建议生成
  - _Requirements: 1.5_

- [x] 2. Checkpoint - 确保所有测试通过






  - Ensure all tests pass, ask the user if questions arise.


- [ ] 3. 实现批次处理器


- [ ] 3.1 创建 BatchProcessor 类和批次模型
  - 实现 BATCH_SIZE = 10 常量
  - 实现 create_batches 方法
  - 实现 BatchResult 数据模型
  - _Requirements: 2.1, 2.2_

- [ ] 3.2 编写属性测试：分批正确性
  - **Property 1: 分批正确性**
  - **Validates: Requirements 2.1, 2.2**

- [ ] 3.3 实现 LangGraph 并行执行器
  - 创建并行批改图结构
  - 实现 process_batch 方法
  - 集成现有 GradingAgent
  - _Requirements: 2.3_

- [ ] 3.4 编写属性测试：并行执行完整性
  - **Property 2: 并行执行完整性**
  - **Validates: Requirements 2.3**

- [ ] 3.5 实现批次容错和结果汇总
  - 实现单页失败不影响整批的逻辑
  - 实现 aggregate_results 方法
  - _Requirements: 2.4, 2.5_

- [ ] 3.6 编写属性测试：批次容错性和汇总正确性
  - **Property 3: 批次容错性**
  - **Property 4: 批次汇总正确性**
  - **Validates: Requirements 2.4, 2.5**


- [ ] 4. Checkpoint - 确保所有测试通过

  - Ensure all tests pass, ask the user if questions arise.


## Phase 2: 学生边界检测


- [x] 5. 实现学生边界检测器



- [x] 5.1 创建 StudentBoundaryDetector 类和边界模型


  - 实现 StudentBoundary、BoundaryDetectionResult 数据模型
  - 实现 detect_boundaries 方法框架
  - _Requirements: 3.1, 3.5_

- [x] 5.2 编写属性测试：学生边界检测触发和输出


  - **Property 5: 学生边界检测触发**
  - **Property 6: 学生边界标记正确性**
  - **Validates: Requirements 3.1, 3.2, 3.5**

- [x] 5.3 实现学生标识提取和题目循环检测


  - 实现 _extract_student_markers 方法
  - 实现 _detect_question_cycle 方法
  - 集成现有 StudentIdentificationService
  - _Requirements: 3.2, 3.3_

- [x] 5.4 实现低置信度边界标记


  - 添加置信度计算逻辑
  - 实现 needs_confirmation 标记
  - _Requirements: 3.4_

- [x] 5.5 编写属性测试：低置信度边界标记


  - **Property 7: 低置信度边界标记**
  - **Validates: Requirements 3.4**


- [x] 6. Checkpoint - 确保所有测试通过



  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: RAG 判例记忆系统


- [-] 7. 实现判例记忆库



- [x] 7.1 创建 exemplars 表和 pgvector 索引

  - 创建数据库迁移文件
  - 添加 pgvector 扩展支持
  - 创建向量索引
  - _Requirements: 4.1_


- [x] 7.2 创建 ExemplarMemory 类和判例模型

  - 实现 Exemplar 数据模型
  - 实现 store_exemplar 方法
  - 实现向量嵌入生成
  - _Requirements: 4.1, 4.2_

- [x] 7.3 编写属性测试：判例存储完整性



  - **Property 8: 判例存储完整性**
  - **Validates: Requirements 4.1, 4.2**

- [ ] 7.4 实现判例检索功能
  - 实现 retrieve_similar 方法
  - 添加相似度阈值过滤（>= 0.7）
  - 限制返回数量（3-5 个）
  - _Requirements: 4.3, 4.4_

- [ ] 7.5 编写属性测试：判例检索数量约束
  - **Property 9: 判例检索数量约束**
  - **Validates: Requirements 4.3, 4.4**

- [ ] 7.6 实现判例淘汰策略
  - 实现 evict_old_exemplars 方法
  - 按使用频率和时效性排序
  - _Requirements: 4.5_

- [ ] 7.7 编写属性测试：判例淘汰策略
  - **Property 10: 判例淘汰策略**
  - **Validates: Requirements 4.5**

- [ ] 7.8 编写属性测试：判例序列化往返一致性
  - **Property 30: 判例序列化往返一致性**
  - **Validates: Requirements 11.1, 11.2, 11.3**


- [x] 8. Checkpoint - 确保所有测试通过



  - Ensure all tests pass, ask the user if questions arise.


## Phase 4: 动态提示词拼装

- [x] 9. 实现提示词拼装器




- [x] 9.1 创建 PromptAssembler 类和提示词模型


  - 实现 PromptSection、AssembledPrompt 数据模型
  - 创建题型基础模板文件
  - 实现 load_base_template 方法
  - _Requirements: 5.1_

- [x] 9.2 编写属性测试：提示词模板选择正确性


  - **Property 11: 提示词模板选择正确性**
  - **Validates: Requirements 5.1**

- [x] 9.3 实现错误模式引导和详细推理提示


  - 实现 add_error_guidance 方法
  - 实现 add_detailed_reasoning_prompt 方法
  - _Requirements: 5.2, 5.3_

- [x] 9.4 实现判例格式化和提示词拼装


  - 实现 format_exemplars 方法
  - 实现 assemble 方法
  - 添加优先级截断逻辑
  - _Requirements: 5.4, 5.5_

- [x] 9.5 编写属性测试：提示词截断优先级


  - **Property 12: 提示词截断优先级**
  - **Validates: Requirements 5.5**

- [x] 10. Checkpoint - 确保所有测试通过




  - Ensure all tests pass, ask the user if questions arise.

## Phase 5: 个性化校准配置

- [-] 11. 实现校准服务


- [x] 11.1 创建 calibration_profiles 表


  - 创建数据库迁移文件
  - 添加索引
  - _Requirements: 6.1_

- [x] 11.2 创建 CalibrationService 类和配置模型


  - 实现 CalibrationProfile、ToleranceRule 数据模型
  - 实现 get_or_create_profile 方法
  - _Requirements: 6.1_

- [x] 11.3 编写属性测试：校准配置默认创建



  - **Property 13: 校准配置默认创建**
  - **Validates: Requirements 6.1**

- [ ] 11.4 实现配置更新和应用
  - 实现 update_profile 方法
  - 实现 apply_tolerance 方法
  - 实现 generate_feedback 方法
  - _Requirements: 6.2, 6.4, 6.5_

- [ ] 11.5 编写属性测试：校准配置更新一致性
  - **Property 14: 校准配置更新一致性**
  - **Validates: Requirements 6.2**

- [ ] 11.6 集成校准配置到批改流程
  - 修改 GradingAgent 加载校准配置
  - 应用容差和措辞模板
  - _Requirements: 6.3, 6.4, 6.5_

- [x] 12. Checkpoint - 确保所有测试通过





  - Ensure all tests pass, ask the user if questions arise.


## Phase 6: 客观题评分与二次验证

- [x] 13. 增强客观题评分




- [x] 13.1 修改 ObjectiveAgent 输出完整性


  - 确保输出包含 score、confidence、reasoning_trace
  - 添加评分依据记录
  - _Requirements: 7.1, 7.2, 7.5_

- [x] 13.2 编写属性测试：客观题评分输出完整性


  - **Property 15: 客观题评分输出完整性**
  - **Validates: Requirements 7.1, 7.2, 7.5**

- [x] 13.3 实现低置信度二次验证


  - 添加置信度阈值检查（< 0.85）
  - 实现二次验证流程（不同提示词或第二模型）
  - _Requirements: 7.3_

- [x] 13.4 编写属性测试：低置信度二次验证触发


  - **Property 16: 低置信度二次验证触发**
  - **Validates: Requirements 7.3**

- [x] 13.5 实现二次验证不一致处理


  - 比较首次和二次验证结果
  - 不一致时标记待人工复核
  - _Requirements: 7.4_

- [x] 13.6 编写属性测试：二次验证不一致处理


  - **Property 17: 二次验证不一致处理**
  - **Validates: Requirements 7.4**


- [x] 14. Checkpoint - 确保所有测试通过



  - Ensure all tests pass, ask the user if questions arise.

## Phase 7: 批改日志系统


- [x] 15. 实现批改日志服务






- [x] 15.1 创建 grading_logs 表
  - 创建数据库迁移文件
  - 添加索引（submission_id、was_overridden、created_at）
  - _Requirements: 8.1_



- [x] 15.2 创建 GradingLogger 类和日志模型
  - 实现 GradingLog 数据模型
  - 实现 log_grading 方法
  - _Requirements: 8.1, 8.2, 8.3_


- [x] 15.3 编写属性测试：批改日志完整性

  - **Property 18: 批改日志完整性**
  - **Validates: Requirements 8.1, 8.2, 8.3**


- [x] 15.4 实现改判日志记录

  - 实现 log_override 方法
  - 更新 was_overridden、override_score 等字段
  - _Requirements: 8.4_


- [x] 15.5 编写属性测试：改判日志完整性

  - **Property 19: 改判日志完整性**
  - **Validates: Requirements 8.4**

- [x] 15.6 实现日志写入容错


  - 添加本地暂存队列
  - 实现 flush_pending 方法
  - _Requirements: 8.5_


- [x] 15.7 编写属性测试：日志写入容错

  - **Property 20: 日志写入容错**
  - **Validates: Requirements 8.5**


- [x] 15.8 实现改判样本查询

  - 实现 get_override_samples 方法
  - 支持时间窗口和数量过滤
  - _Requirements: 9.1_


- [ ] 16. Checkpoint - 确保所有测试通过



  - Ensure all tests pass, ask the user if questions arise.


## Phase 8: 自动规则升级引擎


- [x] 17. 实现规则挖掘器



- [x] 17.1 创建 RuleMiner 类和失败模式模型


  - 实现 FailurePattern 数据模型
  - 实现 analyze_overrides 方法
  - 实现 is_pattern_fixable 方法
  - _Requirements: 9.1, 9.2_

- [x] 17.2 编写属性测试：规则挖掘触发条件


  - **Property 21: 规则挖掘触发条件**
  - **Validates: Requirements 9.1**

- [x] 18. 实现补丁生成器




- [x] 18.1 创建 PatchGenerator 类和补丁模型


  - 实现 RulePatch、PatchType 数据模型
  - 实现 generate_patch 方法
  - _Requirements: 9.2_

- [x] 18.2 编写属性测试：补丁生成条件


  - **Property 22: 补丁生成条件**
  - **Validates: Requirements 9.2**


- [x] 19. 实现回归测试器



- [x] 19.1 创建 RegressionTester 类和测试结果模型

  - 实现 RegressionResult 数据模型
  - 实现 run_regression 方法
  - 实现 is_improvement 方法
  - _Requirements: 9.3, 9.4_

- [x] 19.2 编写属性测试：回归测试必要性和发布条件


  - **Property 23: 回归测试必要性**
  - **Property 24: 补丁发布条件**
  - **Validates: Requirements 9.3, 9.4**

- [x] 20. Checkpoint - 确保所有测试通过






  - Ensure all tests pass, ask the user if questions arise.








- [ ] 21. 实现补丁部署器

- [x] 21.1 创建 rule_patches 表


  - 创建数据库迁移文件
  - 添加索引（status、version）
  - _Requirements: 10.1, 10.2_



- [ ] 21.2 创建 PatchDeployer 类
  - 实现 deploy_canary 方法


  - 实现 promote_to_full 方法
  - 实现 rollback 方法

  - _Requirements: 9.4, 9.5_



- [ ] 21.3 编写属性测试：异常自动回滚
  - **Property 25: 异常自动回滚**
  - **Validates: Requirements 9.5**


- [ ] 21.4 实现部署监控
  - 实现 monitor_deployment 方法
  - 添加异常检测和自动回滚逻辑
  - _Requirements: 9.5_


- [x] 22. 实现版本管理器




- [x] 22.1 创建 VersionManager 类

  - 实现 allocate_version 方法
  - 实现 record_deployment 方法
  - _Requirements: 10.1, 10.2_

- [x] 22.2 编写属性测试：版本号唯一性和部署记录完整性

  - **Property 26: 版本号唯一性**
  - **Property 27: 部署记录完整性**
  - **Validates: Requirements 10.1, 10.2**

- [x] 22.3 实现回滚和历史查询

  - 实现 rollback_to_version 方法
  - 实现 get_history 方法
  - 添加依赖关系处理
  - _Requirements: 10.3, 10.4, 10.5_

- [x] 22.4 编写属性测试：回滚正确性和历史查询完整性


  - **Property 28: 回滚正确性**
  - **Property 29: 历史查询完整性**



  - **Validates: Requirements 10.3, 10.4, 10.5**

- [x] 23. Checkpoint - 确保所有测试通过







  - Ensure all tests pass, ask the user if questions arise.


## Phase 9: 集成与端到端测试


- [x] 24. 集成所有组件




- [x] 24.1 修改 BatchGradingWorkflow 集成新组件


  - 集成 StreamingService 推送进度
  - 集成 BatchProcessor 分批处理
  - 集成 StudentBoundaryDetector 学生分割
  - _Requirements: 1.1, 2.1, 3.1_

- [x] 24.2 修改 GradingAgent 集成自我成长组件


  - 集成 ExemplarMemory 判例检索
  - 集成 PromptAssembler 动态提示词
  - 集成 CalibrationService 校准配置
  - 集成 GradingLogger 日志记录
  - _Requirements: 4.3, 5.1, 6.3, 8.1_

- [x] 24.3 创建规则升级定时任务


  - 实现每日/每周规则挖掘任务
  - 集成 RuleMiner → PatchGenerator → RegressionTester → PatchDeployer 流程
  - _Requirements: 9.1, 9.2, 9.3, 9.4_


- [x] 24.4 编写端到端集成测试


  - 测试完整批改流程
  - 测试流式推送
  - 测试学生分割
  - 测试判例检索和动态提示词

- [x] 25. Final Checkpoint - 确保所有测试通过





  - Ensure all tests pass, ask the user if questions arise.
