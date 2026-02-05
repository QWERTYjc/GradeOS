# 学生助手与错题本深度集成 - 任务列表

## 任务概览

根据 requirements.md 和 design.md，前端部分已基本完成，主要需要完成后端多模态支持。

## 任务列表

- [x] 1. 后端 API 多模态支持
  - [x] 1.1 更新 AssistantChatRequest 模型添加 images 和 wrong_question_context 字段
  - [x] 1.2 实现苏格拉底式教学系统提示词构建函数
  - [x] 1.3 实现 Gemini 多模态内容构建（支持图片+文本）
  - [x] 1.4 更新 /api/assistant/chat 端点处理多模态请求

- [x] 2. 错题本前端完善
  - [x] 2.1 确保"深究这道题"按钮正确传递图片到 localStorage
  - [x] 2.2 验证跳转到学生助手后自动发送消息功能

- [x] 3. 集成测试
  - [x] 3.1 测试完整流程：错题本 → 学生助手 → 多模态分析
