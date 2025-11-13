# 图片和 PDF 支持总结

**更新时间**: 2025-11-09  
**功能**: 添加图片、PDF、Word 文件支持

---

## 📋 已完成的工作

### 1. ✅ 创建文件处理器

**文件**: `ai_correction/functions/file_processor.py`

**功能**:
- `process_file(file_path)` - 统一的文件处理接口
- `_read_image_as_base64()` - 读取图片并转换为 base64
- `_read_pdf_as_text()` - 读取 PDF 文件（使用 PyPDF2）
- `_read_word_as_text()` - 读取 Word 文件（使用 python-docx）
- `_read_text_file()` - 读取文本文件
- `extract_text_from_image_with_llm()` - 使用 LLM 从图片中提取文字（OCR）

**支持的格式**:
- 图片：`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`
- 文档：`.pdf`, `.docx`, `.doc`
- 文本：`.txt`, `.md`, `.json`, `.csv`

### 2. ✅ 更新 InputParserAgent

**文件**: `ai_correction/functions/langgraph/agents/input_parser.py`

**改动**:
1. 添加 `llm_client` 参数到 `__init__`
2. 扩展 `supported_formats` 包含所有支持的格式
3. 修改 `_read_file()` 方法：
   - 使用 `file_processor.process_file()` 处理文件
   - 如果是图片，调用 `extract_text_from_image_with_llm()` 提取文字
   - 如果是 PDF/Word，直接返回提取的文本

**代码示例**:
```python
def __init__(self, llm_client=None):
    self.supported_formats = ['.txt', '.md', '.json', '.csv', '.pdf', '.docx', '.doc', 
                             '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    self.llm_client = llm_client

def _read_file(self, file_path: str) -> str:
    from ..file_processor import process_file, extract_text_from_image_with_llm
    
    # 处理文件
    file_data = process_file(file_path)
    
    # 如果是图片，使用 LLM 提取文字
    if file_data['type'] == 'image':
        if self.llm_client:
            print(f"📸 正在从图片中提取文字: {path.name}")
            return extract_text_from_image_with_llm(file_data['content'], self.llm_client)
        else:
            return f"[图片文件: {path.name}，需要 LLM 支持才能提取文字]"
    
    # 其他格式直接返回文本内容
    return file_data['content']
```

### 3. ✅ 更新工作流

**文件**: `ai_correction/functions/langgraph/workflow_production.py`

**改动**:
```python
# 初始化 Agent
input_parser = InputParserAgent(llm_client)  # 传递 LLM 客户端以支持图片OCR
```

### 4. ✅ 更新文件上传器

**文件**: `ai_correction/functions/langgraph/production_integration.py`

**改动**:
```python
question_files = st.file_uploader(
    "上传题目文件",
    type=['txt', 'md', 'json', 'pdf', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
    accept_multiple_files=True,
    key='question_files',
    help="支持文本、PDF、Word、图片格式"
)
```

---

## 🎯 工作原理

### 图片处理流程

1. **用户上传图片** → Streamlit 文件上传器
2. **保存到临时目录** → `tempfile.mkdtemp()`
3. **InputParserAgent 读取文件** → `_read_file()`
4. **file_processor 处理** → `process_file()`
   - 读取图片为 base64
   - 返回 `{'type': 'image', 'content': base64_string}`
5. **LLM OCR 提取文字** → `extract_text_from_image_with_llm()`
   - 构建视觉输入消息
   - 调用 OpenRouter API（Gemini 2.5 Flash Lite 支持视觉）
   - 返回提取的文字
6. **解析文字内容** → `_extract_questions_from_text()`
7. **继续批改流程** → QuestionAnalyzer, QuestionGrader 等

### PDF 处理流程

1. **用户上传 PDF** → Streamlit 文件上传器
2. **保存到临时目录** → `tempfile.mkdtemp()`
3. **InputParserAgent 读取文件** → `_read_file()`
4. **file_processor 处理** → `process_file()`
   - 使用 PyPDF2 读取 PDF
   - 提取所有页面的文本
   - 返回 `{'type': 'pdf', 'content': text_string}`
5. **解析文字内容** → `_extract_questions_from_text()`
6. **继续批改流程** → QuestionAnalyzer, QuestionGrader 等

---

## 🔧 依赖库

需要安装以下 Python 库：

```bash
pip install PyPDF2  # PDF 解析
pip install python-docx  # Word 文档解析
```

如果没有安装这些库，系统会返回占位符文本（例如 `[PDF文件: xxx.pdf]`）。

---

## 🎨 LLM 视觉输入格式

OpenRouter API 支持视觉输入，消息格式如下：

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "请提取图片中的文字"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,{base64_string}"
                }
            }
        ]
    }
]
```

**支持的模型**:
- Google Gemini 2.5 Flash Lite ✅
- Google Gemini Pro Vision ✅
- OpenAI GPT-4 Vision ✅
- Claude 3 Opus/Sonnet ✅

---

## 📊 测试场景

### 场景 1: 上传图片题目

**输入**:
- 题目文件: `题目.jpg` (包含手写或打印的题目)
- 答案文件: `答案.txt`
- 评分标准: `标准.txt`

**流程**:
1. 系统读取 `题目.jpg`
2. 使用 LLM 提取文字：`📸 正在从图片中提取文字: 题目.jpg`
3. LLM 返回提取的文字内容
4. 解析题目
5. 批改答案

### 场景 2: 上传 PDF 文件

**输入**:
- 题目文件: `题目.pdf`
- 答案文件: `答案.pdf`
- 评分标准: `标准.pdf`

**流程**:
1. 系统使用 PyPDF2 读取 PDF
2. 提取所有页面的文本
3. 解析题目和答案
4. 批改答案

### 场景 3: 混合格式

**输入**:
- 题目文件: `题目.jpg` (图片)
- 答案文件: `答案.pdf` (PDF)
- 评分标准: `标准.txt` (文本)

**流程**:
1. 题目：LLM OCR 提取文字
2. 答案：PyPDF2 提取文字
3. 评分标准：直接读取文本
4. 批改答案

---

## ⚠️ 已知问题

### 1. PDF 解析失败

**问题**: 之前的测试中，PDF 文件解析失败，显示 `不支持的文件格式: .pdf`

**原因**: `InputParserAgent` 的 `supported_formats` 没有包含 `.pdf`

**解决**: ✅ 已修复，现在支持 PDF

### 2. 图片需要 LLM 支持

**问题**: 如果没有提供 LLM API Key，图片无法提取文字

**解决**: 
- 在高级配置中提供 LLM API 密钥
- 或者使用环境变量中的默认 API Key

### 3. 批改立即完成但结果为空

**问题**: 批改按钮点击后立即完成，但结果为空或报错

**可能原因**:
1. 文件解析失败（格式不支持）
2. 题目/答案提取失败（正则表达式不匹配）
3. LLM API 调用失败
4. 聚合结果时除零错误（`division by zero`）

**调试方法**:
- 查看终端输出的详细日志
- 检查 `DEBUG:` 开头的调试信息
- 查看 `agent_outputs_*.md` 文件

---

## 🚀 下一步

### 待测试

1. **测试图片上传** ⏳
   - 上传手写题目图片
   - 验证 LLM OCR 提取效果
   - 检查批改结果

2. **测试 PDF 上传** ⏳
   - 上传 PDF 格式的题目和答案
   - 验证 PyPDF2 提取效果
   - 检查批改结果

3. **测试混合格式** ⏳
   - 同时上传图片、PDF、文本文件
   - 验证系统能否正确处理

### 待优化

1. **添加进度提示** 💡
   - 显示 "正在提取图片文字..."
   - 显示 "正在解析 PDF..."
   - 显示批改进度

2. **优化 OCR 提示词** 💡
   - 针对不同类型的内容（题目/答案/评分标准）使用不同的提示词
   - 提高提取准确性

3. **添加图片预览** 💡
   - 在上传后显示图片缩略图
   - 允许用户确认图片内容

4. **错误处理** 💡
   - 更友好的错误提示
   - 提供重试机制

---

**更新完成时间**: 2025-11-09  
**系统版本**: v2.2  
**状态**: 代码已完成，待测试

