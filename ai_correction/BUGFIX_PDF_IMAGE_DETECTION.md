# PDF/图片格式检测修复

## 🐛 问题描述

### 错误现象
```
文件路径已保存: {'answer': ['temp/uploads/optimized/answer_1_20251123_184722.png'], 'rubric': ['temp/uploads/optimized/rubric_1_20251123_184723.png']}
没有题目文件
??PDF??????: EOF marker not found  ← 问题在这里！
未找到题目理解结果，使用默认理解
检测到默认评分标准（只有1个评分点），批改标准解析可能失败
```

### 根本原因

**`_extract_and_parse_rubric_from_pdf` 方法没有区分 PDF 和图片格式！**

在 `rubric_interpreter_agent.py` 中：

```python
async def _extract_and_parse_rubric_from_pdf(self, pdf_file_path: str):
    """使用 Gemini 3 Pro 原生多模态能力解析 PDF 评分标准"""
    try:
        # ❌ 问题：总是尝试用 PyPDF2 提取文本
        fallback_text = self._extract_text_from_pdf_local(pdf_file_path)
        # ...
```

当传入的是 PNG 图片时：
1. `_extract_text_from_pdf_local` 使用 PyPDF2 尝试读取
2. PyPDF2 期望 PDF 格式，但收到 PNG
3. 报错：`EOF marker not found`（找不到 PDF 结束标记）
4. 虽然有异常处理，但日志显示乱码错误信息
5. 最终回退到默认标准

---

## ✅ 解决方案

### 修改 `_extract_and_parse_rubric_from_pdf`

**文件**: `ai_correction/functions/langgraph/agents/rubric_interpreter_agent.py`

**修改前**（第 222-252 行）：
```python
async def _extract_and_parse_rubric_from_pdf(self, pdf_file_path: str):
    """使用 Gemini 3 Pro 原生多模态能力解析 PDF 评分标准"""
    try:
        fallback_text = ""
        try:
            # ❌ 总是尝试提取 PDF 文本，即使是图片
            fallback_text = self._extract_text_from_pdf_local(pdf_file_path) or ""
        except Exception as txt_err:
            logger.warning(f"预提取 PDF 文本失败: {txt_err}")
        
        # ... 后续处理 ...
```

**修改后**：
```python
async def _extract_and_parse_rubric_from_pdf(self, pdf_file_path: str):
    """
    使用 Gemini 3 Pro 原生多模态能力解析评分标准（支持 PDF 和图片）
    - 对于 PDF：优先本地文本提取，避免大文件上传阻塞
    - 对于图片：直接使用 Gemini Vision API
    """
    try:
        # ✅ 检查文件类型
        from pathlib import Path
        file_ext = Path(pdf_file_path).suffix.lower()
        is_image = file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        
        fallback_text = ""
        
        # ✅ 只对 PDF 文件尝试本地文本提取
        if not is_image:
            try:
                fallback_text = self._extract_text_from_pdf_local(pdf_file_path) or ""
            except Exception as txt_err:
                logger.warning(f"预提取 PDF 文本失败: {txt_err}")
            
            if fallback_text and len(fallback_text.strip()) > 50:
                logger.info(f"📑 使用本地提取文本解析评分标准")
                return await self._interpret_rubric(fallback_text)
        
        # ✅ 使用 Gemini 原生多模态解析（PDF 或图片）
        file_type = "图片" if is_image else "PDF"
        logger.info(f"📄 使用 Gemini 3 Pro 原生多模态解析 {file_type}: {pdf_file_path}")
        
        response = self.llm_client.chat(
            messages,
            files=[pdf_file_path],  # 直接传文件路径
            thinking_level="high"
        )
        # ...
```

---

## 📋 关键修改点

### 1. 文件类型检测

```python
from pathlib import Path
file_ext = Path(pdf_file_path).suffix.lower()
is_image = file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
```

### 2. 条件判断

```python
# 只对 PDF 文件尝试本地文本提取
if not is_image:
    fallback_text = self._extract_text_from_pdf_local(pdf_file_path)
```

### 3. 动态日志

```python
file_type = "图片" if is_image else "PDF"
logger.info(f"📄 使用 Gemini 3 Pro 原生多模态解析 {file_type}: {pdf_file_path}")
```

---

## 🔍 技术细节

### 为什么会出现这个问题？

1. **方法命名误导**：
   - 方法名叫 `_extract_and_parse_rubric_from_pdf`
   - 但实际上也被用来处理图片
   - 导致开发者没有考虑图片格式

2. **PyPDF2 的行为**：
   ```python
   reader = PyPDF2.PdfReader(f)  # 期望 PDF 格式
   # 当传入 PNG 时，报错：EOF marker not found
   ```

3. **异常处理不够细致**：
   - 虽然有 try-except，但没有区分错误类型
   - 日志显示乱码（编码问题）

### 支持的文件格式

| 格式 | 扩展名 | 处理方式 |
|------|--------|----------|
| PDF | `.pdf` | 1. 尝试本地文本提取<br>2. 失败则用 Gemini 多模态 |
| 图片 | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp` | 直接用 Gemini 多模态 |

---

## 🧪 验证方法

### 1. 重启应用
```bash
cd ai_correction
streamlit run main.py
```

### 2. 上传测试

**测试场景 A**：上传 PNG 图片
1. 上传 2 张答卷图片（`.png`）
2. 上传 2 张评分标准图片（`.png`）
3. 点击 "INITIATE GRADING SEQUENCE"

**预期日志**：
```
✅ 正确：
📄 检测到 图片 评分标准，准备解析: path=temp/uploads/optimized/rubric_1.png
📄 使用 Gemini 3 Pro 原生多模态解析 图片: temp/uploads/optimized/rubric_1.png
Gemini 解析完成，提取到 5 个评分点

❌ 不应该出现：
??PDF??????: EOF marker not found
检测到默认评分标准（只有1个评分点）
```

**测试场景 B**：上传 PDF 文件
1. 上传 PDF 格式的答卷
2. 上传 PDF 格式的评分标准
3. 点击 "INITIATE GRADING SEQUENCE"

**预期日志**：
```
✅ 正确：
📄 检测到 PDF 评分标准，准备解析: path=temp/uploads/rubric.pdf
📑 使用本地提取文本解析评分标准（长度 1234）
或
📄 使用 Gemini 3 Pro 原生多模态解析 PDF: temp/uploads/rubric.pdf
```

---

## 📊 修复前后对比

### 修复前

| 文件类型 | 处理流程 | 结果 |
|----------|----------|------|
| PDF | PyPDF2 提取文本 → 解析 | ✅ 正常 |
| 图片 | PyPDF2 提取文本 → **报错** | ❌ 回退默认标准 |

### 修复后

| 文件类型 | 处理流程 | 结果 |
|----------|----------|------|
| PDF | PyPDF2 提取文本 → 解析<br>或 Gemini 多模态 | ✅ 正常 |
| 图片 | **跳过 PyPDF2** → Gemini 多模态 | ✅ 正常 |

---

## 🚀 性能优化

### PDF 文件优化策略

```python
# 1. 尝试本地文本提取（快速）
if not is_image:
    fallback_text = self._extract_text_from_pdf_local(pdf_file_path)
    if fallback_text and len(fallback_text) > 50:
        return await self._interpret_rubric(fallback_text)  # 使用文本解析

# 2. 本地提取失败，使用 Gemini 多模态（较慢但更准确）
response = self.llm_client.chat(files=[pdf_file_path])
```

**优点**：
- 对于文本型 PDF，本地提取更快
- 对于扫描型 PDF，Gemini 多模态更准确
- 自动降级，确保总能得到结果

### 图片文件优化策略

```python
# 直接使用 Gemini 多模态（最优方案）
if is_image:
    response = self.llm_client.chat(files=[pdf_file_path])
```

**优点**：
- 跳过无意义的文本提取尝试
- 减少错误日志
- 提升处理速度

---

## 🔧 后续优化建议

1. **重命名方法**：
   ```python
   # 修改前
   async def _extract_and_parse_rubric_from_pdf(self, pdf_file_path: str):
   
   # 建议改为
   async def _extract_and_parse_rubric_from_file(self, file_path: str):
   ```

2. **增强错误处理**：
   ```python
   try:
       fallback_text = self._extract_text_from_pdf_local(pdf_file_path)
   except PyPDF2.errors.PdfReadError as e:
       logger.warning(f"PDF 格式错误: {e}")
   except Exception as e:
       logger.warning(f"文本提取失败: {e}")
   ```

3. **添加文件验证**：
   ```python
   def _validate_file(self, file_path: str) -> bool:
       """验证文件是否存在且可读"""
       if not os.path.exists(file_path):
           logger.error(f"文件不存在: {file_path}")
           return False
       if not os.access(file_path, os.R_OK):
           logger.error(f"文件不可读: {file_path}")
           return False
       return True
   ```

---

**修复时间**: 2025-11-23  
**影响范围**: 评分标准解析（PDF 和图片）  
**测试状态**: ✅ 待验证



