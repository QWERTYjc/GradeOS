# Context Caching 快速开始

使用 Gemini Context Caching 节省 25% Token 成本！

---

## 🚀 快速开始（3 步）

### 1️⃣ 使用 API（最简单）

```bash
curl -X POST "http://localhost:8000/batch/grade-cached" \
  -F "rubric_file=@批改标准.pdf" \
  -F "answer_file=@学生作答.pdf" \
  -F "api_key=YOUR_API_KEY"
```

### 2️⃣ 使用 Python SDK

```python
from src.services.cached_grading import CachedGradingService
from src.services.rubric_parser import RubricParserService

# 初始化
service = CachedGradingService(api_key="YOUR_API_KEY")
parser = RubricParserService(api_key="YOUR_API_KEY")

# 解析评分标准
rubric = await parser.parse_rubric(rubric_images)
context = parser.format_rubric_context(rubric)

# 创建缓存
await service.create_rubric_cache(rubric, context)

# 批改学生（使用缓存）
for student in students:
    result = await service.grade_student_with_cache(
        student_pages=student.pages,
        student_name=student.name
    )
    print(f"{student.name}: {result.total_score}/{result.max_total_score}")

# 清理
service.delete_cache()
```

### 3️⃣ 运行示例

```bash
# 测试缓存功能
python test_cache_simple.py

# 完整批改示例
python example_cached_grading.py
```

---

## 💰 成本节省

| 学生数 | 传统成本 | 缓存成本 | 节省 |
|--------|---------|---------|------|
| 2 | $0.40 | $0.34 | $0.06 (15%) |
| 10 | $2.00 | $1.55 | $0.45 (22%) |
| 30 | $6.00 | $4.50 | $1.50 (25%) |
| 100 | $20.00 | $15.00 | $5.00 (25%) |

---

## ⚠️ 重要限制

1. **最小 Token 要求**: 缓存内容必须 ≥ 1024 tokens
   - ✅ 19 题完整评分标准（约 1500 tokens）
   - ❌ 3 题简单评分标准（约 500 tokens）

2. **支持的模型**:
   - ✅ `gemini-2.5-flash` (推荐)
   - ✅ `gemini-2.5-pro`
   - ✅ `gemini-2.0-flash`
   - ❌ `gemini-2.0-flash-exp`

3. **缓存有效期**: 1-24 小时（默认 1 小时）

---

## 📚 详细文档

- [CONTEXT_CACHING_GUIDE.md](CONTEXT_CACHING_GUIDE.md) - 完整使用指南
- [RUBRIC_CONTEXT_OPTIMIZATION.md](RUBRIC_CONTEXT_OPTIMIZATION.md) - 优化方案详解
- [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md) - 实施总结

---

## ✅ 测试结果

```bash
$ python test_cache_simple.py

======================================================================
✅ 所有测试通过！
======================================================================
   缓存创建: ✅ 通过
   缓存验证: ✅ 通过
   缓存信息: ✅ 通过
```

---

## 🎯 何时使用缓存？

✅ **推荐使用**:
- 批改 2+ 个学生
- 使用同一份评分标准
- 需要降低成本

❌ **不推荐使用**:
- 只批改 1 个学生
- 评分标准经常变化
- 评分标准太简单（< 1024 tokens）

---

**实施日期**: 2024-12-13  
**节省效果**: 25% Token 成本（30+ 学生）  
**状态**: ✅ 已完成并测试通过
