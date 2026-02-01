# Implementation Plan

- [ ] 1. 创建工具函数基础架构
  - 创建 `src/services/assistant_tools.py` 文件
  - 实现 `ToolParameter`, `ToolDefinition`, `ToolRegistry` 类
  - 实现 `to_gemini_schema()` 方法将工具定义转换为 Gemini function calling schema
  - _Requirements: 7.1, 7.3_

- [ ] 2. 实现核心工具函数
  - 实现 `get_grading_history()` 工具函数
  - 实现 `get_knowledge_mastery()` 工具函数
  - 实现 `get_error_records()` 工具函数
  - 实现 `get_assignment_submissions()` 工具函数
  - 实现 `get_class_statistics()` 工具函数
  - 实现 `get_progress_report()` 工具函数（匹配前端 DiagnosisReportResponse 格式）
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 5.2, 10.1, 10.2_

- [ ]* 2.1 为 get_grading_history 编写属性测试
  - **Property 2: 返回数据完整性**
  - **Validates: Requirements 1.2**

- [ ]* 2.2 为 get_grading_history 编写分页限制属性测试
  - **Property 12: 分页限制**
  - **Validates: Requirements 10.3**

- [ ]* 2.3 为 get_knowledge_mastery 编写属性测试
  - **Property 17: 掌握度计算正确性**
  - **Property 18: 薄弱知识点识别**
  - **Validates: Requirements 2.3**

- [ ]* 2.4 为工具函数编写单元测试
  - 测试每个工具函数的基本功能
  - 测试参数验证
  - 测试边界情况（空数据、大数据量）
  - _Requirements: 1.2, 2.2, 3.2, 4.2, 5.2_

- [ ] 3. 实现工具执行器
  - 创建 `src/services/tool_executor.py` 文件
  - 实现 `ToolCall`, `ToolResult` 数据模型
  - 实现 `ToolExecutor` 类
  - 实现 `execute()` 方法支持并行执行
  - 实现 `_execute_single()` 方法处理单个工具调用
  - 实现权限验证逻辑（学生只能查询自己的数据）
  - 实现超时处理（5 秒超时）
  - _Requirements: 6.1, 6.4, 7.4, 10.4, 10.5_

- [ ]* 3.1 为工具执行器编写属性测试
  - **Property 5: 权限控制**
  - **Property 13: 并行执行**
  - **Property 14: 超时处理**
  - **Validates: Requirements 7.4, 10.4, 10.5**

- [ ]* 3.2 为工具执行器编写单元测试
  - 测试单个工具执行
  - 测试并行执行
  - 测试超时处理
  - 测试权限验证
  - _Requirements: 6.4, 7.4, 10.4, 10.5_

- [ ] 4. 扩展 LLM Client 支持 function calling
  - 更新 `src/services/llm_client.py`
  - 添加 `FunctionCallRequest`, `LLMResponse` 数据模型
  - 实现 `invoke_with_tools()` 方法
  - 集成 Gemini function calling API
  - 实现 function call 请求构建和响应解析
  - _Requirements: 6.2, 6.3_

- [ ]* 4.1 为 LLM Client 编写属性测试
  - **Property 7: 参数生成正确性**
  - **Validates: Requirements 6.2, 7.1**

- [ ]* 4.2 为 LLM Client 编写单元测试
  - 测试 function calling 请求构建
  - 测试响应解析
  - 测试错误处理
  - _Requirements: 6.2, 6.3_

- [ ] 5. 更新 Student Assistant Agent
  - 更新 `src/services/student_assistant_agent.py`
  - 实现 `_init_registry()` 方法注册所有工具
  - 更新 `ainvoke()` 方法支持 function calling 流程
  - 实现工具调用结果整合到 LLM 上下文
  - 更新系统提示，说明何时使用哪些工具
  - _Requirements: 6.1, 6.3, 6.5_

- [ ]* 5.1 为 Student Assistant Agent 编写集成测试
  - 测试完整的 function calling 流程
  - 测试多工具调用场景
  - **Property 9: 多工具调用**
  - **Validates: Requirements 6.5**

- [ ] 6. 更新 /assistant/chat API 端点
  - 更新 `src/api/routes/unified_api.py` 中的 `assistant_chat()` 函数
  - 集成更新后的 Student Assistant Agent
  - 确保响应包含工具调用信息（用于调试）
  - _Requirements: 6.1, 6.3_

- [ ] 7. 更新 /v1/diagnosis/report API 端点
  - 更新 `get_diagnosis_report()` 函数
  - 使用 `get_progress_report()` 工具函数获取数据
  - 移除旧的直接数据库查询逻辑
  - 确保返回数据格式匹配 `DiagnosisReportResponse`
  - _Requirements: 10.1, 10.2_

- [ ] 8. 实现工具调用日志记录
  - 创建数据库迁移脚本添加 `tool_call_logs` 表
  - 在 `ToolExecutor` 中添加日志记录逻辑
  - 记录工具名称、参数、执行时间、结果摘要
  - 记录错误堆栈信息（如果失败）
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ]* 8.1 为日志记录编写属性测试
  - **Property 15: 日志记录完整性**
  - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

- [ ] 9. 实现缓存机制
  - 在工具函数中集成 Redis 缓存
  - 为频繁查询的数据添加缓存（如 grading history, knowledge mastery）
  - 设置合理的缓存过期时间（如 5 分钟）
  - 实现缓存失效逻辑（当数据更新时）
  - _Requirements: 7.5, 10.2_

- [ ]* 9.1 为缓存机制编写属性测试
  - **Property 11: 缓存机制**
  - **Validates: Requirements 7.5, 10.2**

- [ ]* 9.2 为缓存机制编写单元测试
  - 测试缓存命中
  - 测试缓存失效
  - 测试缓存过期
  - _Requirements: 7.5, 10.2_

- [ ] 10. 添加数据模型
  - 在 `src/models/assistant_models.py` 中添加工具相关的 Pydantic 模型
  - 添加 `GradingHistoryRecord`, `KnowledgeMasteryRecord`, `ErrorRecord` 等
  - 添加 `ToolCallLog` 模型
  - _Requirements: 7.2_

- [ ] 11. 端到端测试
  - 编写端到端测试验证完整流程
  - 测试学生询问成绩 → AI 调用工具 → 返回数据 → 生成回复
  - 测试学生询问进度报告 → AI 调用工具 → 返回完整报告数据
  - 测试多工具调用场景
  - 测试错误处理和降级响应
  - _Requirements: 6.1, 6.3, 6.4, 6.5_

- [ ] 12. 性能优化和监控
  - 添加工具调用性能指标收集
  - 优化慢查询（添加数据库索引）
  - 实现查询结果分页
  - 添加监控告警（超时、错误率）
  - _Requirements: 9.4, 10.3, 10.4_

- [ ] 13. 文档和示例
  - 更新 API 文档说明 function calling 功能
  - 添加工具函数使用示例
  - 添加故障排查指南
  - 更新前端集成文档
  - _Requirements: 7.3_

- [ ] 14. Checkpoint - 确保所有测试通过
  - 运行所有单元测试
  - 运行所有属性测试
  - 运行所有集成测试
  - 修复所有失败的测试
  - 确保代码覆盖率 > 80%
  - 如有问题，询问用户

