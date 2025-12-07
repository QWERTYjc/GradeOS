# Vision API 彻底移除 + 默认值问题修复

## 🐛 问题描述

### 错误现象
```
文件路径已保存: {'question': [], 'answer': ['temp/uploads/optimized\\answer_1_20251123_183721_optimized_20251123_183722.png'], 'rubric': ['temp/uploads/optimized\\rubric_1_20251123_183722_optimized_20251123_183724.png']}
❌ Gemini API 调用失败: contents are required.
Vision API调用失败: contents are required.
没有题目文件
评分标准文本为空或过短，使用默认标准
未找到题目理解结果，使用默认理解
检测到默认评分标准（只有1个评分点），批改标准解析可能失败
无法获取学生答案内容，使用默认文本
```

### 根本原因

1. **Vision API 仍在使用**：
   - `AnswerUnderstandingAgent._understand_image_answer()` 仍使用 Vision API 格式
   - `QuestionUnderstandingAgent._understand_image_question()` 仍使用 Vision API 格式
   - 传递 `base64` 格式而不是文件路径

2. **文件路径格式问题**：
   - 优化后的文件路径包含反斜杠 `\\`
   - 可能导致跨平台兼容性问题

3. **API 调用失败导致默认值**：
   - Gemini API 收到空内容 (`contents are required`)
   - 系统回退到默认标准/默认理解

---

## ✅ 解决方案

### 1. 修复 AnswerUnderstandingAgent

**文件**: `ai_correction/functions/langgraph/agents/answer_understanding_agent.py`

**修改前**（使用 Vision API base64 格式）：
```python
async def _understand_image_answer(self, image_content: Dict[str, Any]) -> AnswerUnderstanding:
    """理解图片答案（使用Vision API）"""
    prompt = format_answer_understanding_prompt("", is_vision=True)
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_content['mime_type']};base64,{image_content['base64_data']}"
                    }
                }
            ]
        }
    ]
    
    try:
        response = self.llm_client.chat(messages, temperature=0.3, max_tokens=2000)
        return self._parse_understanding(response, "", "vision")
    except Exception as e:
        logger.error(f"Vision API调用失败: {e}")
        return self._default_understanding()
```

**修改后**（使用 Gemini 原生 API）：
```python
async def _understand_image_answer(self, image_content: Dict[str, Any]) -> AnswerUnderstanding:
    """理解图片答案（使用 Gemini 原生多模态 API）"""
    # 获取文件路径
    file_path = image_content.get('file_path')
    if not file_path:
        logger.warning("图片答案缺少文件路径，使用默认理解")
        return self._default_understanding()
    
    logger.info(f"🖼️  使用 Gemini 解析图片答案: {file_path}")
    prompt = format_answer_understanding_prompt("", is_vision=True)
    messages = [{"role": "user", "content": prompt}]
    
    try:
        response = self.llm_client.chat(
            messages,
            temperature=0.3,
            max_tokens=2000,
            files=[file_path],  # 直接传文件路径
            thinking_level="medium",
            timeout=self._get_llm_timeout()
        )
        return self._parse_understanding(response, "", "vision_image")
    except Exception as e:
        logger.error(f"❌ Gemini 解析图片答案失败: {e}")
        return self._default_understanding()
```

### 2. 修复 QuestionUnderstandingAgent

**文件**: `ai_correction/functions/langgraph/agents/question_understanding_agent.py`

**修改内容**：与 AnswerUnderstandingAgent 相同，将 `_understand_image_question()` 方法从 Vision API 格式改为 Gemini 原生 API。

### 3. 修复文件路径格式

**文件**: `ai_correction/functions/image_optimization/image_optimizer.py`

**修改**：
```python
def _save_optimized_image(self, original_path: str, image_binary: bytes) -> str:
    # ... 保存文件逻辑 ...
    
    # 规范化路径（统一使用正斜杠，避免跨平台问题）
    normalized_path = output_path.replace('\\', '/')
    
    logger.debug(f"优化图片已保存: {normalized_path}")
    return normalized_path  # 返回规范化路径
```

**效果**：
- 修改前：`temp/uploads/optimized\\answer_1_20251123_183721_optimized_20251123_183722.png`
- 修改后：`temp/uploads/optimized/answer_1_20251123_183721_optimized_20251123_183722.png`

---

## 📋 修改文件清单

| 文件 | 修改内容 | 行数 |
|------|----------|------|
| `answer_understanding_agent.py` | 图片理解改用 Gemini 原生 API | ~110-135 |
| `question_understanding_agent.py` | 图片理解改用 Gemini 原生 API | ~108-133 |
| `image_optimizer.py` | 路径规范化（统一正斜杠） | ~206-233 |

---

## 🔍 技术细节

### Vision API vs Gemini 原生 API

| 特性 | Vision API (旧) | Gemini 原生 API (新) |
|------|----------------|---------------------|
| 输入格式 | Base64 编码 | 文件路径 |
| 消息格式 | 复杂的嵌套结构 | 简单的文本 + files 参数 |
| 性能 | 需要编码/解码 | 直接读取文件 |
| 内存占用 | 高（base64 膨胀） | 低（流式读取） |
| 代码复杂度 | 高 | 低 |

### 调用对比

**Vision API (旧)**：
```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_data}"
                }
            }
        ]
    }
]
response = llm_client.chat(messages)
```

**Gemini 原生 API (新)**：
```python
messages = [{"role": "user", "content": prompt}]
response = llm_client.chat(
    messages,
    files=[file_path],  # 简单直接
    thinking_level="medium"
)
```

---

## 🧪 验证方法

### 1. 重启应用
```bash
cd ai_correction
streamlit run main.py
```

### 2. 上传测试
1. 上传 2 张答卷图片
2. 上传 2 张评分标准图片
3. 点击 "INITIATE GRADING SEQUENCE"

### 3. 检查日志
应该看到：
```
✅ 正确的日志：
🖼️  使用 Gemini 解析图片答案: temp/uploads/optimized/answer_1_20251123_183721_optimized_20251123_183722.png
🖼️  使用 Gemini 解析图片题目: temp/uploads/optimized/rubric_1_20251123_183722_optimized_20251123_183724.png

❌ 不应该出现：
Vision API调用失败
评分标准文本为空或过短，使用默认标准
未找到题目理解结果，使用默认理解
```

---

## 📊 预期效果

### 修复前
```
❌ Gemini API 调用失败: contents are required
Vision API调用失败: contents are required
评分标准文本为空或过短，使用默认标准
未找到题目理解结果，使用默认理解
检测到默认评分标准（只有1个评分点）
```

### 修复后
```
✅ 🖼️  使用 Gemini 解析图片答案: temp/uploads/optimized/answer_1_20251123_183721.png
✅ 🖼️  使用 Gemini 解析图片题目: temp/uploads/optimized/rubric_1_20251123_183722.png
✅ 答案理解完成，提取到 X 个关键点
✅ 评分标准解析完成，识别到 Y 个评分点
✅ 批改工作流正常执行
```

---

## 🚀 后续优化建议

1. **移除 base64_data 字段**：
   - 既然不再使用 Vision API，可以完全移除 base64 编码
   - 减少内存占用和处理时间

2. **统一路径处理**：
   - 在文件保存时就使用正斜杠
   - 避免后续多次转换

3. **增强错误处理**：
   - 当文件路径不存在时，提供更明确的错误信息
   - 区分"文件不存在"和"API 调用失败"

---

**修复时间**: 2025-11-23  
**影响范围**: 图片理解、题目理解、文件路径处理  
**测试状态**: ✅ 待验证


