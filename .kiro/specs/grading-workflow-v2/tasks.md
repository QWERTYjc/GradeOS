# Implementation Plan: 批改工作流系统重构 v2

## Overview

本任务清单基于设计文档，将批改工作流系统 v2 的实现分解为可执行的编码任务。任务按照依赖关系排序，确保增量开发和持续集成。

注意：OpenRouter 适配（llm.py、llm_client.py）和 SQLite 基础设施（sqlite.py）已完成，不在任务范围内。

## Tasks

- [ ] 1. 后端核心服务实现
  - [ ] 1.1 实现 GradingWorker 双阶段批改服务
    - 创建 `backend/src/services/grading_worker.py`
    - 实现 `process_student()` 方法，协调视觉和文本模型
    - 实现 `vision_grading()` 方法，调用视觉模型提取内容并初步批改
    - 实现 `text_grading()` 方法，调用文本模型深度批改
    - 使用现有的 `UnifiedLLMClient` 进行 LLM 调用
    - _Requirements: 3.2, 3.3_

  - [ ] 1.2 实现 GradingSelfReport 批改自白服务
    - 创建 `backend/src/services/grading_self_report.py`
    - 实现 `generate_self_report()` 方法
    - 生成批改过程说明、可疑位置标记、建议复核点
    - _Requirements: 3.4_

  - [ ] 1.3 实现 StudentSummary 学生总结服务
    - 创建 `backend/src/services/student_summary.py`
    - 实现 `generate_summary()` 方法
    - 基于批改结果生成学生总结
    - _Requirements: 4.4_

  - [ ]* 1.4 编写核心服务单元测试
    - 测试 GradingWorker 双阶段流程
    - 测试 GradingSelfReport 生成逻辑
    - 测试 StudentSummary 生成逻辑
    - _Requirements: 1.1, 3.2, 3.3, 3.4, 4.4_

- [ ] 2. 工作流暂停态实现
  - [ ] 2.1 修改 batch_grading.py 添加暂停点逻辑
    - 在 rubric_parse_node 后添加 RUBRIC_REVIEW 暂停点
    - 在所有学生批改完成后添加 GRADING_REVIEW 暂停点
    - 使用 LangGraph 的 `interrupt()` 实现暂停
    - 保存暂停状态到 SQLite
    - _Requirements: 2.1, 4.1_

  - [ ] 2.2 实现工作流恢复 API
    - 创建 `backend/src/api/routes/grading_resume.py`
    - 实现 `POST /grading/{batch_id}/resume` 端点
    - 支持 confirm_rubric、modify_rubric、confirm_results、modify_result 操作
    - 实现 `GET /grading/{batch_id}/state` 端点
    - _Requirements: 2.4, 6.2, 6.3_

  - [ ] 2.3 集成 GradingWorker 到工作流
    - 修改 batch_grading.py 使用新的 GradingWorker
    - 在批改完成后调用 GradingSelfReport 生成自白
    - 在确认后调用 StudentSummary 生成总结
    - _Requirements: 3.1, 3.4, 4.4_

  - [ ]* 2.4 编写工作流状态转换属性测试
    - **Property 2: Workflow State Transition Validity**
    - **Validates: Requirements 2.1, 2.4, 4.1, 4.5**

  - [ ]* 2.5 编写状态持久化往返属性测试
    - **Property 3: State Persistence Round-Trip**
    - **Validates: Requirements 2.5, 6.2, 6.3**

- [ ] 3. Checkpoint - 后端核心功能验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 4. 班级系统集成 API
  - [ ] 4.1 实现班级导入 API
    - 在 `backend/src/api/routes/` 添加班级集成路由
    - 实现 `POST /grading/{batch_id}/import-to-class` 端点
    - 实现 student_key 到 student_id 的映射逻辑
    - 更新 student_grading_results 表
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 4.2 实现班级批改历史 API
    - 实现 `GET /class/{class_id}/grading-history` 端点
    - 按 class_id 过滤批改历史
    - _Requirements: 5.4, 8.1_

  - [ ] 4.3 实现撤销导入 API
    - 实现 `POST /grading/{batch_id}/revoke` 端点
    - 更新 revoked_at 字段
    - _Requirements: 5.5_

  - [ ] 4.4 实现一键批改 API
    - 实现 `POST /homework/{homework_id}/grade` 端点
    - 支持批改全部或指定提交
    - _Requirements: 1.4, 8.3_

  - [ ]* 4.5 编写班级导入映射属性测试
    - **Property 6: Class Import Mapping Correctness**
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 4.6 编写班级历史过滤属性测试
    - **Property 8: Class Grading History Filtering**
    - **Validates: Requirements 5.4**

- [ ] 5. Checkpoint - 后端 API 完整性验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 6. 前端批改结果核查页面
  - [ ] 6.1 创建批改结果核查页面
    - 创建 `frontend/src/app/grading/results-review/[batchId]/page.tsx`
    - 显示所有学生的批改结果列表
    - 显示每个学生的批改自白
    - 支持展开/折叠查看详情
    - _Requirements: 4.2_

  - [ ] 6.2 实现批改结果修改功能
    - 支持修改学生分数
    - 支持修改评语
    - 调用 resume API 保存修改
    - _Requirements: 4.3_

  - [ ] 6.3 实现确认和生成总结功能
    - 添加"确认全部"按钮
    - 调用 resume API 确认结果
    - 显示生成的学生总结
    - _Requirements: 4.4, 4.5_

- [ ] 7. 前端评分标准审核页面增强
  - [ ] 7.1 增强 rubric-review 页面人机交互
    - 修改 `frontend/src/app/grading/rubric-review/[batchId]/page.tsx`
    - 支持选中题目重新解析
    - 支持修改评分标准
    - 调用 resume API 确认或修改
    - _Requirements: 2.2, 2.3, 2.4_

- [ ] 8. 前端班级系统集成
  - [ ] 8.1 班级详情页添加批改历史 Tab
    - 修改 `frontend/src/app/teacher/class/[id]/page.tsx`
    - 添加"批改历史"Tab
    - 调用 `/class/{class_id}/grading-history` API
    - 显示批改记录列表
    - 点击记录跳转到批改结果页
    - _Requirements: 8.1, 8.2_

  - [ ] 8.2 作业管理页添加一键批改按钮
    - 修改 `frontend/src/app/teacher/homework/page.tsx`
    - 添加"一键批改"按钮
    - 调用 `/homework/{homework_id}/grade` API
    - 显示批改进度
    - _Requirements: 8.3_

  - [ ] 8.3 提交记录添加批改详情链接
    - 在提交记录列表添加"查看批改详情"链接
    - 跳转到批改结果页
    - _Requirements: 8.4_

- [ ] 9. 前端状态管理增强
  - [ ] 9.1 扩展 consoleStore 支持暂停态
    - 修改 `frontend/src/store/consoleStore.ts`
    - 添加 workflowStatus、pausePoint、pausedData 状态
    - 实现 resumeWorkflow() 方法
    - 实现 refreshWorkflowState() 方法
    - _Requirements: 2.1, 2.4, 4.1_

- [ ] 10. Checkpoint - 前端功能验证
  - 确保所有页面正常工作，如有问题请询问用户

- [ ] 11. 属性测试补充
  - [ ]* 11.1 编写图像预处理格式属性测试
    - **Property 1: Image Preprocessing Format Consistency**
    - **Validates: Requirements 1.1, 1.3**

  - [ ]* 11.2 编写学生边界分割属性测试
    - **Property 4: Student Boundary Splitting Completeness**
    - **Validates: Requirements 3.1**

  - [ ]* 11.3 编写报告生成完整性属性测试
    - **Property 5: Report Generation Completeness**
    - **Validates: Requirements 3.4, 4.4**

  - [ ]* 11.4 编写批改结果修改持久化属性测试
    - **Property 7: Grading Result Modification Persistence**
    - **Validates: Requirements 4.3**

  - [ ]* 11.5 编写撤销状态更新属性测试
    - **Property 9: Revocation Status Update**
    - **Validates: Requirements 5.5**

  - [ ]* 11.6 编写错误状态持久化属性测试
    - **Property 10: Error State Persistence**
    - **Validates: Requirements 6.4**

- [ ] 12. Final Checkpoint - 完整功能验证
  - 确保所有测试通过
  - 验证端到端工作流
  - 如有问题请询问用户

## Notes

- 任务标记 `*` 的为可选测试任务，可根据时间跳过
- 每个 Checkpoint 是验证点，确保阶段性功能完整
- 属性测试使用 Python Hypothesis 库
- 前端测试可使用 Jest + React Testing Library
- OpenRouter 适配和 SQLite 基础设施已完成，无需重复实现
