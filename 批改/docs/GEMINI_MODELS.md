# Gemini 模型配置说明

## 当前使用的模型

### Gemini 3.0 Flash Preview

**模型名称**: `gemini-3-flash-preview`

**选择原因**:
1. ✅ **高性能**: Gemini 3.0 是最新一代模型，性能更强
2. ✅ **更高配额**: 相比实验性模型（exp），预览版有更高的 API 配额
3. ✅ **多模态支持**: 支持文本、图像、视频、音频和 PDF 输入
4. ✅ **大上下文窗口**: 1,048,576 tokens 输入，65,536 tokens 输出
5. ✅ **稳定性**: 预览版比实验版更稳定

**技术规格**:
```
输入类型: text, image, video, audio, PDF
输出类型: text
输入 Token 限制: 1,048,576
输出 Token 限制: 65,536
温度: 0.2 (低温度保持一致性)
```

**支持的功能**:
- ✅ Batch API
- ✅ Caching
- ✅ Code Execution
- ✅ File Search
- ✅ Function Calling
- ✅ Search Grounding
- ✅ Structured Outputs
- ✅ Thinking
- ✅ URL Context

---

## 配额对比

### 实验性模型 (gemini-2.0-flash-exp)

❌ **不推荐使用**

**配额限制**:
- 每分钟请求数 (RPM): **10** ⚠️ 太低
- 每天请求数 (RPD): 1,500
- 每分钟 Token 数 (TPM): 4,000,000

**问题**:
```
429 RESOURCE_EXHAUSTED
You exceeded your current quota.
quotaValue: 10 requests per minute
```

### 预览版模型 (gemini-3-flash-preview)

✅ **推荐使用**

**配额限制** (免费层):
- 每分钟请求数 (RPM): **15** ✅ 更高
- 每天请求数 (RPD): 1,500
- 每分钟 Token 数 (TPM): 1,000,000

**付费层配额**:
- 每分钟请求数 (RPM): **1,000** 🚀
- 每天请求数 (RPD): 无限制
- 每分钟 Token 数 (TPM): 4,000,000

---

## 代码配置

### 1. Gemini 推理客户端

**文件**: `src/services/gemini_reasoning.py`

```python
from langchain_google_genai import ChatGoogleGenerativeAI

class GeminiReasoningClient:
    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview"):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2  # 低温度保持一致性
        )
```

### 2. 布局分析服务

**文件**: `src/services/layout_analysis.py`

```python
from langchain_google_genai import ChatGoogleGenerativeAI

class LayoutAnalysisService:
    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview"):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1  # 更低温度用于结构化输出
        )
```

### 3. 测试脚本

**文件**: `test_workflow_integration.py`

```python
reasoning_client = GeminiReasoningClient(
    api_key=api_key,
    model_name="gemini-3-flash-preview"
)
```

---

## 速率限制策略

### 当前实现

**问题**: 之前使用的 `gemini-2.0-flash-exp` 每分钟只能 10 次请求，导致频繁触发 429 错误。

**解决方案**: 切换到 `gemini-3-flash-preview`，配额提升 50%（15 次/分钟）。

### 建议的优化策略

#### 1. 智能重试

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60)
)
async def call_gemini_api():
    # API 调用
    pass
```

#### 2. 速率限制器

```python
import time

class RateLimiter:
    def __init__(self, max_calls_per_minute: int = 15):
        self.max_calls = max_calls_per_minute
        self.calls = []
    
    def wait_if_needed(self):
        now = time.time()
        # 移除 1 分钟前的调用记录
        self.calls = [t for t in self.calls if now - t < 60]
        
        if len(self.calls) >= self.max_calls:
            # 等待到最早的调用过期
            sleep_time = 60 - (now - self.calls[0])
            time.sleep(sleep_time)
        
        self.calls.append(now)
```

#### 3. 批处理

```python
# 将多个请求合并为一个
async def batch_process(items: List[str]):
    # 合并多个问题到一个请求中
    combined_prompt = "\n\n".join(items)
    response = await llm.ainvoke(combined_prompt)
    return response
```

---

## 升级到付费层

### 为什么需要升级？

**当前限制** (免费层):
- 15 次/分钟 → 处理 49 页需要 ~10 分钟
- 1,500 次/天 → 每天最多处理 ~30 份试卷

**生产需求**:
- 日均处理千万级请求量
- 单题批改延迟 < 30 秒

### 付费层优势

**配额提升**:
- RPM: 15 → **1,000** (66倍提升)
- RPD: 1,500 → **无限制**
- TPM: 1,000,000 → **4,000,000** (4倍提升)

**成本**:
- 输入: $0.075 / 1M tokens
- 输出: $0.30 / 1M tokens
- 缓存输入: $0.01875 / 1M tokens (75% 折扣)

**预估成本** (单份 49 页试卷):
- 输入 tokens: ~50,000 (评分标准 + 图像)
- 输出 tokens: ~5,000 (评分结果)
- 成本: ~$0.005 (约 0.04 元人民币)

---

## 模型版本管理

### 固定版本 vs 最新版本

**最新版本** (推荐):
```python
model="gemini-3-flash-preview"  # 自动使用最新版本
```

**固定版本**:
```python
model="gemini-3-flash-preview-12-2025"  # 固定到特定版本
```

**建议**: 
- 开发环境: 使用最新版本，获取最新功能
- 生产环境: 固定版本，确保稳定性

---

## 故障排查

### 429 错误

**错误信息**:
```
429 RESOURCE_EXHAUSTED
You exceeded your current quota.
```

**解决方案**:
1. ✅ 确认使用 `gemini-3-flash-preview` 而不是 `gemini-2.0-flash-exp`
2. ✅ 实现速率限制器
3. ✅ 添加自动重试机制
4. ✅ 考虑升级到付费层

### 模型不存在错误

**错误信息**:
```
404 NOT_FOUND
Model not found: gemini-xxx
```

**解决方案**:
1. 检查模型名称拼写
2. 确认模型在你的地区可用
3. 查看最新的模型列表: https://ai.google.dev/gemini-api/docs/models

### 超时错误

**错误信息**:
```
DEADLINE_EXCEEDED
Request timeout
```

**解决方案**:
1. 增加超时时间
2. 减少输入 token 数量
3. 使用更快的模型（Flash 而不是 Pro）

---

## 参考资源

- [Gemini API 文档](https://ai.google.dev/gemini-api/docs)
- [模型列表](https://ai.google.dev/gemini-api/docs/models)
- [速率限制](https://ai.google.dev/gemini-api/docs/rate-limits)
- [定价](https://ai.google.dev/gemini-api/docs/pricing)
- [LangChain 集成](https://python.langchain.com/docs/integrations/chat/google_generative_ai)

---

**最后更新**: 2025-12-19  
**维护者**: AI 批改系统团队
