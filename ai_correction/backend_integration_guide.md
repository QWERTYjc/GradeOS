# 后端适配与集成指南 (Backend Integration Guide)

## 1. 概述
本指南详细说明了如何在 Streamlit 前端集成 Textin 图像增强服务，并将其连接到多模态批改工作流 (`run_multimodal_grading`)。

## 2. 核心变更点

### 2.1 入口文件 (`ai_correction/main.py`)

在 `show_grading()` 函数中新增了图片上传与自动优化逻辑：
- **UI 组件**: 使用 `st.file_uploader` 接收多张图片 (`jpg`, `png`, `webp`)。
- **优化触发**: 调用 `functions.image_optimization_integration.process_uploaded_images` 自动处理上传图片。
- **会话状态**: 优化后的图片路径存储在 `st.session_state.uploaded_file_paths['answer']` 中。
- **自动回退**: 若 Textin API 不可用或优化失败，自动降级使用原图。

### 2.2 批改工作流衔接

在 `show_result_page()` 中更新了参数传递逻辑：
- **多文件支持**: 自动检测 `answer` 字段是单个路径还是路径列表。
- **参数注入**: 将处理后的文件列表传给 `run_multimodal_grading(..., answer_files=answer_files, ...)`。

## 3. 依赖与配置

### 3.1 环境变量 (.env)
确保配置以下 Textin API 参数：
```ini
TEXTIN_APP_ID=your_app_id
TEXTIN_SECRET_CODE=your_secret_code
# 可选
TEXTIN_API_URL=https://api.textin.com/ai/service/v1/crop_enhance_image
```

### 3.2 依赖库
确保 `requirements.txt` 包含：
```txt
requests>=2.31.0
```

## 4. 验证步骤 (CLI / Terminal)

### 4.1 启动应用
```bash
streamlit run ai_correction/main.py
```

### 4.2 交互验证
1. 登录系统 (默认 Demo 账号: `demo` / `demo`)。
2. 进入 "GRADING STATION" 页面。
3. 在 "Student Answer" 区域上传 1-2 张试卷图片。
4. 观察 "Image Enhancement" 进度条和状态提示。
5. 点击 "INITIATE GRADING SEQUENCE"。
6. 确认进入结果页面，且批改正常启动。

### 4.3 快速调试 (CLI)
如果需要单独测试优化模块，可以使用以下脚本：
```bash
python -c "from functions.image_optimization_integration import optimize_images; print(optimize_images(['test_image.jpg']))"
```
(注：需确保 `test_image.jpg` 存在)



