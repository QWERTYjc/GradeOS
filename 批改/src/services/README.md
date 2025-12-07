# 服务层模块

## CacheService - 语义缓存服务

语义缓存服务提供基于 Redis 的批改结果缓存功能，通过感知哈希实现语义去重。

### 特性

- **感知哈希**：使用 pHash 算法计算图像的感知哈希，相似图像产生相同哈希
- **优雅降级**：所有 Redis 操作失败时返回 None/False，不影响正常批改流程
- **高置信度缓存**：仅缓存置信度 > 0.9 的结果
- **自动过期**：默认 30 天 TTL
- **缓存失效**：支持按评分细则批量失效缓存

### 使用示例

```python
import redis.asyncio as redis
from src.services.cache import CacheService
from src.models.grading import GradingResult

# 初始化 Redis 客户端
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=False
)

# 创建缓存服务
cache_service = CacheService(
    redis_client=redis_client,
    default_ttl_days=30
)

# 查询缓存
rubric_text = "1. 正确使用公式 (5分)\n2. 计算准确 (5分)"
image_data = open('question.png', 'rb').read()

cached_result = await cache_service.get_cached_result(rubric_text, image_data)

if cached_result:
    print(f"缓存命中: {cached_result.question_id}")
else:
    # 执行批改...
    result = GradingResult(
        question_id="q1",
        score=8.5,
        max_score=10.0,
        confidence=0.95,
        feedback="解题思路正确",
        visual_annotations=[],
        agent_trace={}
    )
    
    # 缓存结果（仅当 confidence > 0.9）
    success = await cache_service.cache_result(rubric_text, image_data, result)
    print(f"缓存存储: {'成功' if success else '失败'}")

# 评分细则更新时使缓存失效
deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
print(f"删除了 {deleted_count} 条缓存")

# 获取缓存统计
stats = await cache_service.get_cache_stats()
print(f"缓存命中率: {stats['hit_rate']:.2%}")
```

### 缓存键格式

```
grade_cache:v1:{rubric_hash}:{image_hash}
```

- `rubric_hash`: 评分细则的 SHA-256 哈希（64 位十六进制）
- `image_hash`: 图像的感知哈希（16 位十六进制）

### 错误处理

所有方法都实现了优雅降级：

- `get_cached_result()`: Redis 错误时返回 `None`，继续正常批改
- `cache_result()`: Redis 错误时返回 `False`，不影响批改结果
- `invalidate_by_rubric()`: Redis 错误时返回 `0`，记录日志

### 性能考虑

- 感知哈希计算：~10ms（100x100 图像）
- Redis 查询：~1-5ms（本地）
- Redis 存储：~1-5ms（本地）
- 缓存命中可节省 20-30 秒的 LLM 调用时间

### 验证需求

- 需求 6.1：感知哈希计算
- 需求 6.2：缓存命中返回缓存结果
- 需求 6.3：高置信度结果被缓存
- 需求 6.4：缓存失败不阻塞批改
- 需求 6.5：缓存条目 30 天过期
- 需求 9.4：评分细则更新使缓存失效


## RateLimiter - 限流器服务

限流器服务提供基于 Redis 的滑动窗口限流功能，用于保护 API 和外部服务调用。

### 特性

- **滑动窗口**：使用时间窗口对齐算法，精确控制请求速率
- **原子操作**：使用 Redis INCR + EXPIRE 保证并发安全
- **Fail-Open 策略**：Redis 错误时默认允许请求，保证服务可用性
- **分布式支持**：多实例共享限流状态
- **灵活配置**：支持不同的限流键、速率和窗口大小

### 使用示例

```python
import redis.asyncio as redis
from src.services.rate_limiter import RateLimiter

# 初始化 Redis 客户端
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=False
)

# 创建限流器实例
rate_limiter = RateLimiter(
    redis_client=redis_client,
    key_prefix="api_rate_limit"
)

# 尝试获取令牌
allowed = await rate_limiter.acquire(
    key="user_123",           # 限流标识（如 user_id, api_name）
    max_requests=100,         # 时间窗口内最大请求数
    window_seconds=60         # 时间窗口大小（秒）
)

if allowed:
    # 执行业务逻辑
    print("请求允许")
else:
    # 返回 429 Too Many Requests
    print("请求被限流")

# 查询剩余配额
remaining = await rate_limiter.get_remaining(
    key="user_123",
    max_requests=100,
    window_seconds=60
)
print(f"剩余配额: {remaining}")

# 获取详细限流信息
info = await rate_limiter.get_rate_limit_info(
    key="user_123",
    max_requests=100,
    window_seconds=60
)
print(f"已使用: {info['used']}/{info['limit']}")
print(f"窗口重置时间: {info['reset_at']}")

# 重置限流计数器（管理操作）
await rate_limiter.reset(key="user_123", window_seconds=60)
```

### 常见使用场景

#### 1. API 端点限流

```python
from fastapi import FastAPI, HTTPException, Request
from src.services.rate_limiter import RateLimiter

app = FastAPI()
rate_limiter = RateLimiter(redis_client)

@app.post("/api/v1/submissions")
async def submit_grading(request: Request):
    # 按用户 ID 限流
    user_id = request.state.user_id
    
    allowed = await rate_limiter.acquire(
        key=f"user:{user_id}",
        max_requests=10,
        window_seconds=60
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试"
        )
    
    # 处理提交...
    return {"status": "success"}
```

#### 2. Gemini API 限流

```python
# 保护 Gemini API 调用速率
async def call_gemini_api(prompt: str):
    allowed = await rate_limiter.acquire(
        key="gemini_api",
        max_requests=60,      # 每分钟 60 次
        window_seconds=60
    )
    
    if not allowed:
        # 等待或返回错误
        raise Exception("Gemini API 速率限制")
    
    # 调用 Gemini API...
    return response
```

#### 3. 多级限流

```python
# 同时限制用户级和全局级
async def multi_level_rate_limit(user_id: str):
    # 用户级限流：每分钟 10 次
    user_allowed = await rate_limiter.acquire(
        key=f"user:{user_id}",
        max_requests=10,
        window_seconds=60
    )
    
    # 全局限流：每分钟 1000 次
    global_allowed = await rate_limiter.acquire(
        key="global",
        max_requests=1000,
        window_seconds=60
    )
    
    return user_allowed and global_allowed
```

### Redis 键格式

```
rate_limit:{key}:{window_start_timestamp}
```

- `key`: 限流标识（如 `user:123`, `gemini_api`）
- `window_start_timestamp`: 时间窗口起始时间戳（Unix 时间戳）

### 时间窗口对齐

限流器使用时间窗口对齐算法：

- 60 秒窗口：对齐到分钟边界（如 10:30:00, 10:31:00）
- 3600 秒窗口：对齐到小时边界（如 10:00:00, 11:00:00）

这确保了同一时间窗口内的所有请求使用相同的 Redis 键。

### 错误处理

所有方法都实现了 Fail-Open 策略：

- `acquire()`: Redis 错误时返回 `True`（允许请求）
- `get_remaining()`: Redis 错误时返回 `max_requests`（保守估计）
- `reset()`: Redis 错误时返回 `False`

这确保了即使 Redis 不可用，服务仍然可以继续运行（降级模式）。

### 性能考虑

- Redis INCR 操作：~1ms（本地）
- Pipeline 操作：~1-2ms（本地）
- 内存占用：每个窗口键约 100 字节
- 自动清理：通过 EXPIRE 自动删除过期键

### 验证需求

- 需求 8.3：使用滑动窗口算法限制请求速率

### 注意事项

1. **时钟同步**：分布式环境需要确保服务器时钟同步
2. **Redis 持久化**：建议使用 AOF 或 RDB 持久化，避免重启后限流状态丢失
3. **窗口边界**：在窗口切换时可能出现短暂的速率突增（最多 2x）
4. **Fail-Open vs Fail-Close**：当前实现为 Fail-Open，如需更严格的限流可改为 Fail-Close


## LayoutAnalysisService - 布局分析服务

布局分析服务使用 Gemini 2.5 Flash Lite 进行页面分割，识别试卷中的题目边界。

### 特性

- **纯视觉识别**：直接使用 VLM 识别题目边界，无需 OCR
- **结构化输出**：返回 JSON 格式的题目区域和边界框坐标
- **坐标转换**：自动将归一化坐标（0-1000）转换为像素坐标
- **空区域检测**：未识别到题目时抛出异常，标记为需要人工审核
- **低温度设置**：temperature=0.1 保持识别一致性

### 使用示例

```python
from src.services.layout_analysis import LayoutAnalysisService

# 初始化服务
service = LayoutAnalysisService(
    api_key="your_google_api_key",
    model_name="gemini-2.0-flash-exp"  # 默认值
)

# 读取图像
with open('exam_page.jpg', 'rb') as f:
    image_data = f.read()

# 分割文档
try:
    result = await service.segment_document(
        image_data=image_data,
        submission_id="sub_001",
        page_index=0
    )
    
    # 访问识别的题目区域
    print(f"识别到 {len(result.regions)} 道题目")
    for region in result.regions:
        print(f"题目 {region.question_id}:")
        print(f"  页面索引: {region.page_index}")
        print(f"  边界框: ymin={region.bounding_box.ymin}, "
              f"xmin={region.bounding_box.xmin}, "
              f"ymax={region.bounding_box.ymax}, "
              f"xmax={region.bounding_box.xmax}")
        
except ValueError as e:
    # 未识别到题目区域
    print(f"需要人工审核: {e}")
```

### 返回数据结构

```python
SegmentationResult(
    submission_id="sub_001",
    total_pages=1,
    regions=[
        QuestionRegion(
            question_id="q1",
            page_index=0,
            bounding_box=BoundingBox(
                ymin=108,   # 像素坐标
                xmin=384,
                ymax=540,
                xmax=1536
            ),
            image_data=None  # 可选：裁剪后的图像
        )
    ]
)
```

### 坐标系统

模型返回归一化坐标（0-1000 比例），服务自动转换为像素坐标：

```
归一化坐标: [100, 200, 500, 800]  (0-1000 比例)
图像尺寸: 1920x1080 像素
↓
像素坐标: ymin=108, xmin=384, ymax=540, xmax=1536
```

### 错误处理

- **ValueError**: 未识别到任何题目区域时抛出，需要人工审核
- **JSON 解析错误**: 模型返回格式不正确时抛出
- **图像格式错误**: 无法打开图像时抛出

### 性能考虑

- Gemini API 调用：~2-5 秒
- 坐标转换：<1ms
- 图像尺寸获取：~10ms

### 验证需求

- 需求 2.1：调用 Gemini 2.5 Flash Lite 识别题目边界
- 需求 2.2：返回结构化 JSON 包含 question_id 和边界框
- 需求 2.3：坐标转换（归一化 → 像素）
- 需求 2.4：空区域检测并标记为需要人工审核
- 需求 2.5：按顺序返回所有题目区域


## GeminiReasoningClient - Gemini 深度推理客户端

Gemini 深度推理客户端用于批改智能体的各个推理节点，提供视觉提取、评分映射和自我反思功能。

### 特性

- **视觉提取**：生成学生解题步骤的详细文字描述
- **评分映射**：将评分细则的每个评分点映射到学生答案中的证据
- **自我反思**：审查评分逻辑，识别潜在的评分错误
- **结构化输出**：支持 JSON 格式的结构化响应
- **温度控制**：temperature=0.2 保持评分一致性

### 使用示例

#### 1. 视觉提取

```python
from src.services.gemini_reasoning import GeminiReasoningClient
import base64

# 初始化客户端
client = GeminiReasoningClient(
    api_key="your_google_api_key",
    model_name="gemini-2.0-flash-exp"  # 默认值
)

# 读取图像并转换为 base64
with open('student_answer.jpg', 'rb') as f:
    image_b64 = base64.b64encode(f.read()).decode('utf-8')

# 视觉提取
vision_analysis = await client.vision_extraction(
    question_image_b64=image_b64,
    rubric="1. 正确使用公式 (5分)\n2. 计算准确 (5分)",
    standard_answer="答案：42"  # 可选
)

print("视觉分析结果:")
print(vision_analysis)
# 输出: "学生在第一行写出了正确的公式 F=ma，然后代入数值..."
```

#### 2. 评分映射

```python
# 评分映射
mapping_result = await client.rubric_mapping(
    vision_analysis=vision_analysis,
    rubric="1. 正确使用公式 (5分)\n2. 计算准确 (5分)",
    max_score=10.0,
    standard_answer="答案：42",  # 可选
    critique_feedback=None  # 首次评分时为 None
)

print("评分映射结果:")
print(f"初始分数: {mapping_result['initial_score']}")
print(f"评分理由: {mapping_result['reasoning']}")

for item in mapping_result['rubric_mapping']:
    print(f"  评分点: {item['rubric_point']}")
    print(f"  证据: {item['evidence']}")
    print(f"  得分: {item['score_awarded']}/{item['max_score']}")
```

#### 3. 自我反思

```python
# 自我反思
critique_result = await client.critique(
    vision_analysis=vision_analysis,
    rubric="1. 正确使用公式 (5分)\n2. 计算准确 (5分)",
    rubric_mapping=mapping_result['rubric_mapping'],
    initial_score=mapping_result['initial_score'],
    max_score=10.0,
    standard_answer="答案：42"  # 可选
)

print("反思结果:")
print(f"需要修正: {critique_result['needs_revision']}")
print(f"置信度: {critique_result['confidence']}")

if critique_result['critique_feedback']:
    print(f"反馈: {critique_result['critique_feedback']}")
    
    # 如果需要修正，带着反馈重新评分
    if critique_result['needs_revision']:
        revised_mapping = await client.rubric_mapping(
            vision_analysis=vision_analysis,
            rubric="1. 正确使用公式 (5分)\n2. 计算准确 (5分)",
            max_score=10.0,
            critique_feedback=critique_result['critique_feedback']
        )
        print(f"修正后分数: {revised_mapping['initial_score']}")
```

### 返回数据结构

#### vision_extraction 返回

```python
str: "学生在第一行写出了正确的公式 F=ma，然后代入数值 m=2kg, a=3m/s²，
     计算得到 F=6N。但在第三行的单位转换中出现了错误..."
```

#### rubric_mapping 返回

```python
{
    "rubric_mapping": [
        {
            "rubric_point": "正确使用公式",
            "evidence": "学生在第一行写出了正确的公式 F=ma",
            "score_awarded": 5.0,
            "max_score": 5.0
        },
        {
            "rubric_point": "计算准确",
            "evidence": "计算过程有误，单位转换错误",
            "score_awarded": 2.0,
            "max_score": 5.0
        }
    ],
    "initial_score": 7.0,
    "reasoning": "公式使用正确，但计算过程中单位转换有误"
}
```

#### critique 返回

```python
{
    "critique_feedback": "评分过于严格，学生的计算方法是正确的，
                         只是最后一步的单位转换有小错误，应该给 3 分而不是 2 分",
    "needs_revision": True,
    "confidence": 0.65
}
```

### 修正循环

客户端支持修正循环，通过 `critique_feedback` 参数传递反思反馈：

```python
# 第一次评分
mapping_1 = await client.rubric_mapping(
    vision_analysis=vision_analysis,
    rubric=rubric,
    max_score=10.0
)

# 反思
critique = await client.critique(
    vision_analysis=vision_analysis,
    rubric=rubric,
    rubric_mapping=mapping_1['rubric_mapping'],
    initial_score=mapping_1['initial_score'],
    max_score=10.0
)

# 如果需要修正，带着反馈重新评分
if critique['needs_revision']:
    mapping_2 = await client.rubric_mapping(
        vision_analysis=vision_analysis,
        rubric=rubric,
        max_score=10.0,
        critique_feedback=critique['critique_feedback']  # 传递反馈
    )
```

### JSON 提取

客户端自动处理模型返回的 JSON：

- 如果响应包含 ` ```json ` 代码块，自动提取
- 否则直接解析响应内容
- 解析失败时抛出 `json.JSONDecodeError`

### 性能考虑

- 视觉提取：~5-10 秒（包含图像分析）
- 评分映射：~3-5 秒
- 自我反思：~3-5 秒
- 总计（含一次修正）：~15-25 秒

### 验证需求

- 需求 3.2：视觉提取节点生成详细文字描述
- 需求 3.3：评分映射节点将评分点映射到证据
- 需求 3.4：反思节点识别评分错误并生成修正反馈

### 注意事项

1. **API 密钥**：确保 Google AI API 密钥有效且有足够配额
2. **图像格式**：支持 JPEG、PNG、WEBP 格式
3. **Base64 编码**：图像必须先转换为 base64 字符串
4. **温度设置**：temperature=0.2 是推荐值，可根据需要调整
5. **错误处理**：建议捕获 API 调用异常并实现重试逻辑
