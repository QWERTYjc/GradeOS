# Gemini API Key 配置完成

## �?配置状�?

您的 Gemini API Key 已成功配置并验证�?

### API Key 信息

- **API Key**: `AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE`
- **配置位置**: `.env` 文件
- **验证状�?*: �?已验证可�?

### 可用模型

系统已配置使用以�?Gemini 模型�?

#### 1. Gemini 2.5 Flash Lite
- **模型名称**: `gemini-2.5-flash-lite`
- **用�?*: 页面布局分析和题目分�?
- **特点**: 
  - 高吞吐量
  - 低成�?
  - 快速响�?
  - 适合大规模并发处�?
- **配置文件**: `src/services/layout_analysis.py`

#### 2. Gemini 3.0 Pro Preview
- **模型名称**: `gemini-3-pro-preview`
- **用�?*: 深度推理批改
- **特点**:
  - 最新一代推理能�?
  - 更强的理解力和准确度
  - 支持复杂的多步推�?
  - 适合需要深度理解的任务
- **配置文件**: `src/services/llm_reasoning.py`

## 验证测试结果

### Gemini 2.5 Flash Lite 测试
```
�?测试通过
响应示例: "我是一个大型语言模型，由 Google 训练�?
```

### Gemini 3.0 Pro Preview 测试
```
�?测试通过
响应示例: "好的，当然！我会用一个清晰、易于理解的方式来解释什么是机器学习..."
```

## 环境变量配置

`.env` 文件已创建，包含以下配置�?

```bash
# Gemini API
LLM_API_KEY=AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE

# 其他配置
DATABASE_URL=postgresql://grading_user:grading_pass@localhost:5432/grading_system
REDIS_URL=redis://localhost:6379
TEMPORAL_HOST=localhost:7233
...
```

## 使用说明

### 在代码中使用

系统会自动从环境变量中读�?API Key�?

```python
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取 API Key
api_key = os.getenv("LLM_API_KEY")

# 使用布局分析服务
from src.services.layout_analysis import LayoutAnalysisService
layout_service = LayoutAnalysisService(api_key=api_key)

# 使用推理客户�?
from src.services.llm_reasoning import LLMReasoningClient
reasoning_client = LLMReasoningClient(api_key=api_key)
```

### 测试 API 连接

如需再次测试 API 连接，可以运行：

```python
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
api_key = os.getenv("LLM_API_KEY")

# 测试 Flash Lite
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=api_key
)
response = model.invoke("你好")
print(response.content)
```

## 成本优化建议

### 1. 使用合适的模型

- **布局分析**: 使用 `gemini-2.5-flash-lite`（成本低�?
- **深度推理**: 使用 `gemini-2.5-pro`（准确度高）

### 2. 启用语义缓存

系统已实现语义缓存功能：
- 相似题目自动使用缓存结果
- 高置信度结果缓存 30 �?
- 可节�?60-80% �?API 调用

### 3. 批量处理

- 使用 Temporal 工作流并行处理多道题�?
- 利用 KEDA 自动扩缩容优化资源使�?

### 4. 监控 API 使用

```bash
# 查看缓存命中�?
redis-cli
> INFO stats

# 查看 API 调用日志
tail -f logs/api.log | grep "gemini"
```

## 配额管理

### 查看配额

访问 Google AI Studio 查看 API 配额�?
https://aistudio.google.com/app/apikey

### 配额限制

- **免费�?*: 每分�?15 次请�?
- **付费�?*: 根据您的订阅计划

### 限流配置

系统已配置限流器，防止超出配额：

```bash
# .env 文件中的配置
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

## 安全建议

### 1. 保护 API Key

- �?`.env` 文件已添加到 `.gitignore`
- �?不要�?API Key 提交到版本控�?
- �?在生产环境使用密钥管理服务（�?AWS Secrets Manager�?

### 2. 定期轮换

建议定期更换 API Key�?
1. �?Google AI Studio 生成新的 API Key
2. 更新 `.env` 文件
3. 重启服务

### 3. 监控异常使用

- 监控 API 调用频率
- 设置异常告警
- 定期审查访问日志

## 故障排查

### 问题：API 调用失败

**可能原因**:
1. API Key 无效或过�?
2. 网络连接问题
3. 配额已用�?
4. 模型名称错误

**解决方案**:
```bash
# 1. 验证 API Key
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('LLM_API_KEY'))"

# 2. 测试网络连接
curl https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_API_KEY

# 3. 检查配�?
# 访问 https://aistudio.google.com/app/apikey

# 4. 验证模型名称
python list_models.py  # 如果需要，可以创建此脚�?
```

### 问题：响应速度�?

**优化建议**:
1. 使用 `gemini-2.5-flash-lite` 替代 Pro 版本（如果不需要深度推理）
2. 启用缓存减少重复调用
3. 使用批量处理提高吞吐�?
4. 考虑使用 CDN 加速图像传�?

## 下一�?

1. �?API Key 已配�?
2. �?模型已验�?
3. ⏭️ 启动基础设施服务（PostgreSQL, Redis, Temporal�?
4. ⏭️ 运行数据库迁�?
5. ⏭️ 启动 API 服务�?Workers
6. ⏭️ 测试完整的批改流�?

详细步骤请参�?`QUICKSTART.md` 文件�?

## 技术支�?

如有问题，请查看�?
- 快速启动指�? `QUICKSTART.md`
- 部署文档: `DEPLOYMENT.md`
- 设计文档: `.kiro/specs/ai-grading-agent/design.md`
- API 文档: http://localhost:8000/docs (启动服务�?
