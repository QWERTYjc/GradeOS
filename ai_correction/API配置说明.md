# API配置说明

## 问题诊断

如果批改功能出现 **404 错误** 或 **API调用失败**，通常是以下原因：

### 1. OpenRouter API 密钥未设置

**错误信息：**
```
404 Client Error: Not Found for url: https://openrouter.ai/api/v1/chat/completions
```

**解决方案：**

1. **获取 API 密钥**
   - 访问：https://openrouter.ai/keys
   - 注册账号并创建 API 密钥

2. **配置环境变量**
   
   在项目根目录创建或编辑 `.env` 文件：
   
   ```bash
   # OpenRouter 配置
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxx
   
   # 或者使用通用配置
   LLM_PROVIDER=openrouter
   LLM_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxx
   ```

3. **验证配置**
   
   重启 Streamlit 应用后，检查终端输出是否显示：
   ```
   LLM Client 初始化: provider=openrouter, model=google/gemini-2.5-flash-lite
   ```

### 2. 使用测试数据（无需API）

如果暂时无法配置API，可以使用内置的测试数据：

1. 在批改页面点击 **"🧪 LOAD TEST DATA"** 按钮
2. 系统会加载演示用的批改结果
3. 可以查看完整的批改报告和界面效果

### 3. 切换其他 LLM 提供商

如果 OpenRouter 不可用，可以切换到其他提供商：

#### 使用 Gemini（推荐）

在 `.env` 文件中设置：
```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash-exp
```

获取 Gemini API 密钥：https://makersuite.google.com/app/apikey

#### 使用 OpenAI

在 `.env` 文件中设置：
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4
```

### 4. 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 404 | API端点不存在 | 检查模型名称是否正确，访问 https://openrouter.ai/models 查看可用模型 |
| 401 | 未授权 | 检查API密钥是否正确设置 |
| 429 | 请求过多 | 等待一段时间后重试，或升级API套餐 |
| 500 | 服务器错误 | OpenRouter服务暂时不可用，稍后重试 |

### 5. 验证配置是否生效

运行以下命令检查环境变量：

```bash
# Windows PowerShell
$env:OPENROUTER_API_KEY

# Linux/Mac
echo $OPENROUTER_API_KEY
```

或者在 Python 中检查：
```python
import os
from dotenv import load_dotenv
load_dotenv()
print("API Key:", os.getenv('OPENROUTER_API_KEY', 'NOT SET'))
```

## 快速开始

1. **最简单的方式**：使用测试数据
   - 点击 "🧪 LOAD TEST DATA" 按钮
   - 无需任何配置即可查看效果

2. **完整功能**：配置 API 密钥
   - 获取 OpenRouter API 密钥
   - 在 `.env` 文件中设置
   - 重启应用

3. **遇到问题**：查看错误提示
   - 系统会显示详细的错误信息
   - 按照提示检查配置





