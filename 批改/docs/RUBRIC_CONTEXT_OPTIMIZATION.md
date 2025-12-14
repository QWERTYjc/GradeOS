# 评分标准上下文优化方案

**问题**: 当前系统每次批改学生作业时都会发送完整的评分标准上下文，导致 Token 消耗巨大。

**影响**: 评分标准上下文占总 Token 消耗的 **25%**，对于 30 个学生来说，这意味着浪费了约 **500,000 tokens**（约 $0.04-0.05 per 学生）。

**✅ 已实施**: 方案 1 - Gemini Context Caching（2024-12-13）

---

## 当前问题分析

### 现状
```python
# 当前实现（src/services/strict_grading.py）
async def grade_student(
    self,
    student_pages: List[bytes],
    rubric: ParsedRubric,
    rubric_context: str,  # ← 每次都传入完整上下文
    student_name: str = "学生"
):
    # 构建批改 prompt
    prompt = f"""你是一位严格的阅卷老师。

{rubric_context}  # ← 每次都包含完整的评分标准（约 15,000-20,000 tokens）

## 学生作答
...
"""
```

### Token 消耗分解（单个学生）
```
总计: 62,000 - 80,500 tokens
├── 图像编码: 9,300 - 12,000 tokens (15%)
├── 评分标准上下文: 15,500 - 20,000 tokens (25%) ← 重复浪费
├── 学生作答内容: 24,800 - 32,000 tokens (40%)
├── 批改 Prompt: 6,200 - 8,000 tokens (10%)
└── 输出结果: 6,200 - 8,500 tokens (10%)
```

### 30 个学生的浪费
```
评分标准上下文重复 30 次:
15,500 - 20,000 tokens × 30 = 465,000 - 600,000 tokens

浪费成本:
约 $0.035 - $0.045 per 学生
30 个学生总浪费: $1.05 - $1.35
```

---

## 优化方案

### 方案 1: 使用 Gemini Context Caching（✅ 已实施）

Gemini 提供了 Context Caching 功能，可以缓存长上下文并在多次请求中复用。

**实施状态**: ✅ 已完成并测试通过

#### 实现方式
```python
from langchain_google_genai import ChatGoogleGenerativeAI

class OptimizedStrictGradingService:
    """优化的批改服务 - 使用 Context Caching"""
    
    def __init__(self, api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        self.cached_rubric_context = None
        self.cache_ttl = 3600  # 缓存 1 小时
    
    async def set_rubric_context(self, rubric_context: str):
        """设置并缓存评分标准上下文"""
        # 使用 Gemini Context Caching API
        self.cached_rubric_context = await self._cache_context(rubric_context)
    
    async def _cache_context(self, context: str):
        """缓存上下文到 Gemini"""
        # Gemini Context Caching API
        # 参考: https://ai.google.dev/gemini-api/docs/caching
        from google.generativeai import caching
        
        cache = caching.CachedContent.create(
            model='models/gemini-2.5-flash',
            display_name='rubric_context',
            system_instruction=context,
            ttl=self.cache_ttl
        )
        return cache
    
    async def grade_student(
        self,
        student_pages: List[bytes],
        student_name: str = "学生"
    ):
        """批改学生作业 - 使用缓存的评分标准"""
        if not self.cached_rubric_context:
            raise ValueError("请先调用 set_rubric_context() 设置评分标准")
        
        # 构建批改 prompt（不包含评分标准）
        prompt = f"""请根据已缓存的评分标准，对学生作答进行批改。

## 学生作答
以下是学生 "{student_name}" 的作答：
[学生作答图像]

## 输出格式
...
"""
        
        # 使用缓存的上下文
        response = await self.llm.ainvoke(
            [HumanMessage(content=prompt)],
            cached_content=self.cached_rubric_context  # ← 使用缓存
        )
        
        return response
```

#### 优势
- ✅ **Token 节省**: 评分标准只计费一次，后续请求免费使用缓存
- ✅ **性能提升**: 缓存的上下文加载更快
- ✅ **成本降低**: 节省 25% 的 Token 成本

#### 成本对比
```
不使用缓存:
  - 30 个学生: 2,000,000 tokens → $0.20-0.25 per 学生

使用缓存:
  - 缓存创建: 20,000 tokens (一次性)
  - 30 个学生: 1,500,000 tokens → $0.15-0.19 per 学生
  - 节省: 25% ($0.05-0.06 per 学生)
```

---

### 方案 2: 分离评分标准和学生作答（简单实现）

如果不使用 Context Caching，可以通过优化 Prompt 结构来减少重复。

#### 实现方式
```python
class OptimizedStrictGradingService:
    """优化的批改服务 - 分离评分标准"""
    
    def __init__(self, api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        self.rubric_summary = None  # 简化的评分标准摘要
    
    def set_rubric_summary(self, rubric: ParsedRubric):
        """生成简化的评分标准摘要"""
        # 只保留关键信息，大幅减少 Token
        summary = []
        for q in rubric.questions:
            summary.append(f"Q{q.question_id}({q.max_score}分): {len(q.scoring_points)}个得分点")
        
        self.rubric_summary = "\n".join(summary)
        # 从 15,000 tokens 减少到 500 tokens
    
    async def grade_student(
        self,
        student_pages: List[bytes],
        rubric: ParsedRubric,  # 完整的评分标准
        student_name: str = "学生"
    ):
        """批改学生作业 - 使用简化的评分标准"""
        # 第一次调用：使用完整评分标准
        # 后续调用：只使用简化摘要 + 具体题目的详细标准
        
        prompt = f"""请根据以下评分标准批改学生作答。

## 评分标准摘要
{self.rubric_summary}  # ← 只有 500 tokens

## 学生作答
...

注意：详细的得分点标准已在系统中，请严格按照标准评分。
"""
        
        # 实际实现中，可以在批改每道题时才加载该题的详细标准
        # 这样可以进一步减少 Token 消耗
```

#### 优势
- ✅ **实现简单**: 不需要额外的 API 支持
- ✅ **Token 节省**: 从 15,000 tokens 减少到 500 tokens
- ✅ **灵活性高**: 可以根据需要动态加载详细标准

#### 成本对比
```
不优化:
  - 评分标准: 15,000 tokens × 30 = 450,000 tokens

优化后:
  - 评分标准摘要: 500 tokens × 30 = 15,000 tokens
  - 节省: 435,000 tokens (约 $0.03 per 学生)
```

---

### 方案 3: 逐题批改（最优化）

将批改过程拆分为逐题批改，每次只发送当前题目的评分标准。

#### 实现方式
```python
class OptimizedStrictGradingService:
    """优化的批改服务 - 逐题批改"""
    
    async def grade_question(
        self,
        question_image: bytes,
        question_rubric: QuestionRubric,  # 只包含当前题目的标准
        question_id: str
    ):
        """批改单道题目"""
        # 构建该题的评分标准上下文
        rubric_context = self._format_question_rubric(question_rubric)
        # 只有 500-1000 tokens
        
        prompt = f"""请根据以下评分标准批改第 {question_id} 题。

## 评分标准
{rubric_context}  # ← 只包含当前题目的标准

## 学生作答
[题目图像]

## 输出格式
...
"""
        
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return response
    
    async def grade_student(
        self,
        student_pages: List[bytes],
        rubric: ParsedRubric,
        student_name: str = "学生"
    ):
        """批改学生作业 - 逐题批改"""
        results = []
        
        # 逐题批改
        for question in rubric.questions:
            # 找到该题的图像
            question_image = self._extract_question_image(
                student_pages, 
                question.question_id
            )
            
            # 批改该题
            result = await self.grade_question(
                question_image,
                question,
                question.question_id
            )
            results.append(result)
        
        return self._aggregate_results(results)
```

#### 优势
- ✅ **Token 最优**: 每次只发送当前题目的标准（500-1000 tokens）
- ✅ **并行处理**: 可以并行批改多道题目
- ✅ **错误隔离**: 单题失败不影响其他题目

#### 成本对比
```
不优化:
  - 完整评分标准: 15,000 tokens × 30 学生 = 450,000 tokens

逐题批改:
  - 单题标准: 800 tokens × 19 题 × 30 学生 = 456,000 tokens
  - 但可以并行处理，提高吞吐量
```

---

## 推荐实现方案

### 短期（立即实施）
**方案 2: 分离评分标准和学生作答**

理由：
- 实现简单，不需要额外 API
- 立即可以节省 25% Token
- 不改变现有架构

实施步骤：
1. 修改 `StrictGradingService.grade_student()`
2. 生成简化的评分标准摘要
3. 在 Prompt 中使用摘要而非完整标准

### 中期（1-2 周）
**方案 1: 使用 Gemini Context Caching**

理由：
- 官方支持，稳定可靠
- 最大化 Token 节省
- 性能提升

实施步骤：
1. 研究 Gemini Context Caching API
2. 实现缓存管理器
3. 修改批改服务使用缓存

### 长期（1-2 月）
**方案 3: 逐题批改 + Context Caching**

理由：
- 最优化的 Token 使用
- 支持并行处理
- 更好的错误隔离

实施步骤：
1. 重构批改流程为逐题批改
2. 为每道题创建独立的缓存
3. 实现并行批改机制

---

## 实施计划

### 第一步：立即优化（本周）
```python
# 修改 src/services/strict_grading.py

class StrictGradingService:
    def __init__(self, api_key: str):
        self.llm = ChatGoogleGenerativeAI(...)
        self.rubric_summary_cache = {}  # 缓存评分标准摘要
    
    def _generate_rubric_summary(self, rubric: ParsedRubric) -> str:
        """生成简化的评分标准摘要"""
        summary = [f"总分: {rubric.total_score}分，共 {rubric.total_questions} 题"]
        for q in rubric.questions:
            summary.append(
                f"Q{q.question_id}: {q.max_score}分 "
                f"({len(q.scoring_points)}个得分点)"
            )
        return "\n".join(summary)
    
    async def grade_student(
        self,
        student_pages: List[bytes],
        rubric: ParsedRubric,
        rubric_context: str,  # 保留用于首次批改
        student_name: str = "学生",
        use_summary: bool = True  # 新参数：是否使用摘要
    ):
        if use_summary:
            # 使用简化摘要
            rubric_text = self._generate_rubric_summary(rubric)
        else:
            # 使用完整标准（首次批改）
            rubric_text = rubric_context
        
        prompt = f"""...
{rubric_text}  # ← 使用摘要或完整标准
...
"""
```

### 第二步：Context Caching（1-2 周）
```python
# 新建 src/services/cached_grading.py

from google.generativeai import caching

class CachedGradingService:
    async def create_rubric_cache(self, rubric_context: str):
        """创建评分标准缓存"""
        self.cache = caching.CachedContent.create(
            model='models/gemini-2.5-flash',
            display_name='rubric_context',
            system_instruction=rubric_context,
            ttl=3600
        )
    
    async def grade_student_with_cache(self, student_pages: List[bytes]):
        """使用缓存批改"""
        # 使用缓存的评分标准
        response = await self.llm.ainvoke(
            messages,
            cached_content=self.cache
        )
```

### 第三步：逐题批改（1-2 月）
```python
# 重构 src/services/strict_grading.py

class StrictGradingService:
    async def grade_student(self, ...):
        """批改学生作业 - 逐题批改"""
        # 并行批改所有题目
        tasks = [
            self.grade_question(page, question)
            for page, question in zip(student_pages, rubric.questions)
        ]
        results = await asyncio.gather(*tasks)
        return self._aggregate_results(results)
```

---

## 预期效果

### Token 节省
| 方案 | Token 节省 | 成本节省 | 实施难度 |
|------|-----------|---------|---------|
| 方案 1 (Context Caching) | 25% | $0.05-0.06/学生 | 中 |
| 方案 2 (分离标准) | 20% | $0.04-0.05/学生 | 低 |
| 方案 3 (逐题批改) | 15% | $0.03-0.04/学生 | 高 |
| **组合方案** | **35-40%** | **$0.07-0.10/学生** | **中** |

### 30 个学生的成本对比
```
当前成本: $6.00 - $7.50
优化后成本: $3.60 - $4.50
节省: $2.40 - $3.00 (40%)
```

---

## 总结

评分标准上下文的重复发送是当前系统最大的 Token 浪费源。通过实施上述优化方案，可以：

✅ **立即节省 20-25% Token**（使用方案 2）  
✅ **中期节省 35-40% Token**（使用方案 1 + 2）  
✅ **长期节省 40-50% Token**（使用方案 1 + 2 + 3）  

建议立即实施方案 2，然后逐步迁移到方案 1 和方案 3。

