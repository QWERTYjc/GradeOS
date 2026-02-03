# 学生助手与错题本深度集成 - 设计文档

## 架构概述

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   错题本页面     │────▶│   学生助手页面    │────▶│   后端 API      │
│  (analysis)     │     │  (AIChat.tsx)    │     │ (unified_api)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                       │                        │
        │ localStorage          │ HTTP POST              │ Gemini API
        │ 存储错题上下文         │ images[]              │ 多模态调用
        ▼                       ▼                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ wrong-question  │     │ AssistantChat    │     │ Gemini 2.0      │
│ -context        │     │ Request          │     │ Flash           │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## 数据流设计

### 1. 错题上下文结构
```typescript
interface WrongQuestionContext {
  questionId: string;
  score: number;
  maxScore: number;
  feedback?: string;
  studentAnswer?: string;
  scoringPointResults?: ScoringPointResult[];
  subject?: string;
  topic?: string;
  images?: string[];  // base64 编码的图片
  timestamp: string;
}
```

### 2. API 请求结构
```typescript
interface AssistantChatRequest {
  student_id: string;
  message: string;
  class_id?: string;
  history?: AssistantMessage[];
  session_mode?: string;  // 'wrong_question_review' | 'learning'
  images?: string[];      // base64 图片列表
  wrong_question_context?: WrongQuestionContext;
}
```

### 3. 后端处理流程
```python
# unified_api.py - /api/assistant/chat
async def assistant_chat(request: AssistantChatRequest):
    # 1. 构建系统提示词（苏格拉底式教学）
    system_prompt = build_socratic_prompt(request.wrong_question_context)
    
    # 2. 构建多模态内容
    contents = []
    if request.images:
        for img in request.images:
            contents.append({"type": "image", "data": img})
    contents.append({"type": "text", "text": request.message})
    
    # 3. 调用 Gemini API
    response = await gemini_client.generate_content(
        model="gemini-2.0-flash",
        contents=contents,
        system_instruction=system_prompt
    )
    
    return AssistantChatResponse(content=response.text)
```

## 苏格拉底式教学提示词设计

```
你是一位采用苏格拉底式教学法的AI学习助手。

当学生带着错题来请教时，请遵循以下原则：

1. **诊断错误类型**
   - 概念理解错误：学生对基本概念有误解
   - 计算/操作错误：步骤正确但执行出错
   - 粗心大意：理解正确但疏忽导致错误
   - 知识盲区：缺乏必要的前置知识

2. **引导式提问**
   - 不要直接给出答案
   - 通过提问引导学生发现问题
   - 例如："你能告诉我这道题考查的是什么知识点吗？"

3. **循序渐进**
   - 从学生已知的知识出发
   - 逐步引导到正确理解
   - 每次只聚焦一个知识点

4. **巩固练习**
   - 在学生理解后，提供类似练习题
   - 帮助学生举一反三
```

## 正确性属性

### P1: 图片传递完整性
- 前端传递的 base64 图片必须完整到达后端
- 后端必须正确解析并传递给 Gemini API

### P2: 上下文保持一致性
- 错题上下文在整个对话过程中保持一致
- session_mode 正确标识为 'wrong_question_review'

### P3: 响应相关性
- AI 响应必须与错题内容相关
- 必须采用引导式而非直接给答案的方式

## 文件修改清单

| 文件 | 修改内容 |
|------|----------|
| `backend/src/api/routes/unified_api.py` | 添加 images 字段处理，多模态 Gemini 调用 |
| `backend/src/services/gemini_reasoning.py` | 添加多模态内容构建函数 |
| `frontend/src/app/student/analysis/page.tsx` | 确保"深究这道题"正确传递图片 |
