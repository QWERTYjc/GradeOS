# 中文文件名编码问题修复

## 🐛 问题描述

### 错误现象
```
[ WARN] global loadsave.cpp:275 cv::findDecoder imread_('uploads\answer_寰俊鍥剧墖_20250430182121.jpg'): can't open/read file
无法读取图片: uploads\answer_微信图片_20250430182121.jpg
AnswerUnderstandingAgent 失败: 'base64_data'
```

### 根本原因

1. **文件名编码问题**：
   - 用户上传的文件包含中文文件名（如 `微信图片_20250430182121.jpg`）
   - Windows 系统下 OpenCV 无法正确处理中文路径
   - 导致图片质量检测失败

2. **数据结构不完整**：
   - `file_processor.py` 只返回 `file_path`，没有 `base64_data`
   - `AnswerUnderstandingAgent` 期望 `image_content['base64_data']`
   - 导致 KeyError: 'base64_data'

---

## ✅ 解决方案

### 1. 文件名规范化 (main.py)

**修改前**：
```python
save_path = UPLOAD_DIR / f"answer_{file.name}"
```

**修改后**：
```python
ext = Path(file.name).suffix
safe_name = f"answer_{idx+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
save_path = UPLOAD_DIR / safe_name
logger.info(f"答卷文件已保存: {file.name} -> {safe_name}")
```

**效果**：
- 原文件名：`微信图片_20250430182121.jpg`
- 保存为：`answer_1_20251123_180530.jpg`
- 避免所有中文字符，确保跨平台兼容

### 2. 添加 base64 编码 (file_processor.py)

**修改前**：
```python
content = {
    'file_path': str(path.absolute()),
    'mime_type': _get_mime_type(suffix),
    'page_count': page_count
}
```

**修改后**：
```python
# 读取文件并生成 base64（用于 Vision API 兼容）
base64_data = None
try:
    import base64
    with open(file_path, 'rb') as f:
        file_bytes = f.read()
        base64_data = base64.b64encode(file_bytes).decode('utf-8')
except Exception as e:
    logger.warning(f"⚠️  Base64 编码失败: {e}")

content = {
    'file_path': str(path.absolute()),
    'mime_type': _get_mime_type(suffix),
    'page_count': page_count
}

# 如果成功生成 base64，添加到内容中
if base64_data:
    content['base64_data'] = base64_data
```

**效果**：
- 同时提供 `file_path` 和 `base64_data`
- 兼容 Gemini 原生 API 和 Vision API
- 避免 KeyError

---

## 📋 修改文件清单

| 文件 | 修改内容 | 行数 |
|------|----------|------|
| `ai_correction/main.py` | 题目文件名规范化 | ~410 |
| `ai_correction/main.py` | 答卷文件名规范化 | ~440 |
| `ai_correction/main.py` | 评分标准文件名规范化 | ~470 |
| `ai_correction/functions/file_processor.py` | 添加 base64 编码 | ~109-145 |

---

## 🧪 验证方法

### 1. 上传中文文件名测试

```bash
cd ai_correction
streamlit run main.py
```

1. 上传包含中文文件名的图片（如 `学生作答.png`）
2. 观察终端日志：
   ```
   答卷文件已保存: 学生作答.png -> answer_1_20251123_180530.png
   ✅ 原生多模态文件处理完成: answer_1_20251123_180530.png
   ```
3. 确认批改流程正常启动，无 OpenCV 警告

### 2. 检查数据结构

在 `AnswerUnderstandingAgent` 中添加调试日志：
```python
logger.info(f"图片内容键: {image_content.keys()}")
# 应输出: 图片内容键: dict_keys(['file_path', 'mime_type', 'page_count', 'base64_data'])
```

---

## 🔍 技术细节

### 文件名生成规则

```python
{type}_{index}_{timestamp}{extension}
```

- `type`: 文件类型（question/answer/rubric）
- `index`: 序号（1, 2, 3...）
- `timestamp`: 时间戳（YYYYmmdd_HHMMSS）
- `extension`: 原文件扩展名（.jpg, .png, .pdf）

**示例**：
- `answer_1_20251123_180530.jpg`
- `rubric_1_20251123_180531.pdf`

### Base64 编码策略

1. **优先使用文件路径**（Gemini 原生 API）
2. **同时提供 base64**（Vision API 兼容）
3. **编码失败不阻断流程**（只记录警告）

---

## 📊 性能影响

| 操作 | 之前 | 之后 | 影响 |
|------|------|------|------|
| 文件保存 | 直接使用原文件名 | 生成安全文件名 | +0.1ms |
| 文件处理 | 只返回路径 | 路径 + base64 | +50-200ms |
| 总体影响 | - | - | 可忽略 |

**说明**：
- Base64 编码增加约 50-200ms（取决于文件大小）
- 对于 10MB 以下的图片，影响可忽略
- 换来的是更好的兼容性和稳定性

---

## 🚀 后续优化建议

1. **延迟加载 base64**：
   - 只在需要时才生成 base64
   - 减少不必要的内存占用

2. **文件名映射表**：
   - 记录原文件名和安全文件名的映射
   - 在 UI 中显示原文件名

3. **异步编码**：
   - 将 base64 编码放到后台线程
   - 不阻塞主流程

---

**修复时间**: 2025-11-23  
**影响范围**: 文件上传和多模态处理  
**测试状态**: ✅ 待验证



