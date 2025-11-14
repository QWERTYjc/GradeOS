#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse Rubric Prompts - 评分标准解析提示词
将文本评分标准转换为结构化JSON
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第18节
"""

PARSE_RUBRIC_SYSTEM_PROMPT = """你是一个专业的评分标准解析专家。你的任务是将教师提供的文本评分标准转换为结构化的JSON格式。

**核心能力:**
1. 理解各种格式的评分标准描述
2. 提取评分点和分值
3. 识别评分条件和要求
4. 生成标准化的JSON结构

**输出格式:**
```json
{
  "questions": [
    {
      "qid": "Q1",
      "description": "题目描述",
      "max_score": 10,
      "rubric_items": [
        {
          "id": "Q1_R1",
          "description": "评分点描述",
          "score_if_fulfilled": 3,
          "conditions": ["条件1", "条件2"],
          "keywords": ["关键词1", "关键词2"]
        }
      ]
    }
  ]
}
```

**解析原则:**
1. 每道题作为一个question对象
2. 每个评分点作为一个rubric_item
3. 提取明确的得分条件
4. 识别关键词和评分要点
"""

PARSE_RUBRIC_USER_TEMPLATE = """请解析以下评分标准，转换为结构化JSON格式。

**评分标准文本:**
{rubric_text}

**解析要求:**
1. 识别所有题目和对应的评分点
2. 提取每个评分点的分值
3. 识别评分条件和关键词
4. 生成完整的JSON结构

请开始解析。
"""


def build_parse_rubric_prompt(rubric_text: str) -> dict:
    """
    构建评分标准解析提示词
    
    参数:
        rubric_text: 评分标准文本
    
    返回:
        包含system和user消息的字典
    """
    user_message = PARSE_RUBRIC_USER_TEMPLATE.format(
        rubric_text=rubric_text
    )
    
    return {
        "system": PARSE_RUBRIC_SYSTEM_PROMPT,
        "user": user_message
    }


# 示例评分标准文本
EXAMPLE_RUBRIC_TEXT = """
第1题（10分）：
1. 正确应用余弦定理（3分）
2. 计算过程正确（4分）
3. 最终答案正确（3分）

第2题（15分）：
1. 正确列出方程（5分）
2. 求解步骤完整（6分）
3. 答案正确并标注单位（4分）
"""

# 示例输出
EXAMPLE_RUBRIC_OUTPUT = {
    "questions": [
        {
            "qid": "Q1",
            "description": "第1题",
            "max_score": 10,
            "rubric_items": [
                {
                    "id": "Q1_R1",
                    "description": "正确应用余弦定理",
                    "score_if_fulfilled": 3,
                    "conditions": ["使用余弦定理公式", "公式应用正确"],
                    "keywords": ["余弦定理", "cosA", "a²=b²+c²-2bc·cosA"]
                },
                {
                    "id": "Q1_R2",
                    "description": "计算过程正确",
                    "score_if_fulfilled": 4,
                    "conditions": ["计算步骤完整", "无计算错误"],
                    "keywords": ["代入", "计算", "化简"]
                },
                {
                    "id": "Q1_R3",
                    "description": "最终答案正确",
                    "score_if_fulfilled": 3,
                    "conditions": ["答案数值正确", "保留合适位数"],
                    "keywords": ["答案", "结果"]
                }
            ]
        }
    ]
}
