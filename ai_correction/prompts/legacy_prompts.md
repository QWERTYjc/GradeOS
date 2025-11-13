# 旧批改系统提示词存档

本文件保存了旧批改系统的提示词，供参考和对比使用。

---

## 1. 旧版简单语义批改提示词

```
请批改以下答案，并以 JSON 格式返回结果：

题目：{question_text}
学生答案：{answer_text}

请返回 JSON 格式：
{
    "score": 得分（0-10分的整数）,
    "feedback": "详细反馈",
    "errors": ["错误点1", "错误点2"],
    "suggestions": ["改进建议1", "改进建议2"]
}
```

**问题**：
- 没有使用评分标准
- 没有细分评分点
- 反馈不够详细
- 评分不够精准

---

## 2. 旧版 calling_api.py 提示词

### 2.1 有评分标准的批改

```python
def correction_with_marking_scheme(marking_scheme, *answer_files, strictness_level='中等', language='zh'):
    """
    使用评分标准批改
    """
    prompt = f"""
    评分标准：
    {marking_scheme}
    
    学生答案：
    {answer_content}
    
    请根据评分标准批改，并给出详细反馈。
    """
```

### 2.2 无评分标准的批改

```python
def correction_without_marking_scheme(*answer_files, strictness_level='中等', language='zh'):
    """
    无评分标准批改
    """
    prompt = f"""
    学生答案：
    {answer_content}
    
    请批改并给出反馈。
    """
```

---

## 3. 旧版 ScoringAgent 提示词

位置：`ai_correction/functions/langgraph/agents/scoring_agent.py`

**特点**：
- 调用 calling_api.py 的函数
- 没有充分利用 RubricInterpreter 解析的评分标准
- 批改结果解析不够准确

---

## 4. 旧版默认评分标准

```python
default_criteria = {
    'accuracy': {'weight': 0.4, 'description': '答案准确性'},
    'method': {'weight': 0.3, 'description': '解题方法'},
    'process': {'weight': 0.2, 'description': '解题过程'},
    'presentation': {'weight': 0.1, 'description': '答题规范'}
}
```

**问题**：
- 过于通用，不适用于所有题型
- 没有细分评分点
- 权重固定，不够灵活

---

## 5. 保留的有价值内容

### 5.1 严格程度说明

```python
strictness_desc = {
    "loose": "宽松 - 对小错误容忍度高",
    "standard": "标准 - 按照常规标准批改",
    "strict": "严格 - 对细节要求高"
}
```

### 5.2 学科推断逻辑

```python
def _infer_subject(state):
    """推断学科"""
    keywords_map = {
        '数学': ['数学', 'math', '算'],
        '物理': ['物理', 'physics'],
        '化学': ['化学', 'chemistry'],
        '语文': ['语文', 'chinese', '作文'],
        '英语': ['英语', 'english']
    }
    # ... 推断逻辑
```

---

## 6. 改进方向

### 6.1 新提示词应该包含：
1. **明确的评分标准引用** - 逐条对照评分标准
2. **细分评分点** - 每个评分点单独评分
3. **详细的错误分析** - 指出具体错误位置和原因
4. **具体的改进建议** - 可操作的建议
5. **结构化输出** - 便于解析和展示

### 6.2 新批改流程应该：
1. **RubricInterpreter** 解析评分标准，提取细分评分点
2. **QuestionGraderAgent** 使用细分评分点逐一批改
3. **ResultAggregator** 汇总各评分点得分
4. **输出格式化** 生成美观的批改报告

---

**文档创建时间**: 2025-11-09  
**用途**: 存档旧提示词，供新系统设计参考

