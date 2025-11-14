#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract Via MM Prompts - 多模态提取提示词
用于文本提取和像素坐标标注
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第17节
"""

EXTRACT_MM_SYSTEM_PROMPT = """你是一个专业的多模态文档分析助手。你的任务是从学生作业图片中提取文本内容和像素坐标。

**核心能力:**
1. 精确识别图片中的所有文本内容
2. 为每个文本块标注像素级坐标（bbox）
3. 识别学生姓名和学号信息
4. 保持文本的原始布局和顺序

**输出要求:**
返回JSON格式，包含：
- mm_tokens: 文本token列表（每个token包含text和bbox）
- student_info: 学生信息（name, student_id）

**坐标格式:**
bbox使用 {x1, y1, x2, y2} 格式，其中：
- x1, y1: 左上角坐标
- x2, y2: 右下角坐标
- 坐标范围: 0-图片宽度/高度的像素值

**注意事项:**
1. 每个token代表一个连续的文本块（可以是一个词、一行或一个段落）
2. 行ID (line_id) 用于标识同一行的文本
3. 置信度 (conf) 表示识别准确度 (0.0-1.0)
4. 页码 (page) 从0开始
"""

EXTRACT_MM_USER_TEMPLATE = """请分析以下学生作业图片，提取所有文本内容和坐标信息。

**图片信息:**
- 图片数量: {image_count}
- 预期包含: 学生姓名、学号、答题内容

**提取要求:**
1. 识别并提取学生姓名和学号（如果存在）
2. 提取所有答题文本内容
3. 为每个文本块标注精确的bbox坐标
4. 按照阅读顺序排列文本

**输出格式:**
```json
{{
  "student_info": {{
    "name": "学生姓名",
    "student_id": "学号"
  }},
  "mm_tokens": [
    {{
      "id": "T0",
      "text": "文本内容",
      "page": 0,
      "bbox": {{"x1": 100, "y1": 50, "x2": 300, "y2": 80}},
      "conf": 0.95,
      "line_id": "L0"
    }}
  ]
}}
```

请开始分析图片。
"""


def build_extract_mm_prompt(images: list, page_numbers: list = None) -> dict:
    """
    构建多模态提取提示词
    
    参数:
        images: 图片列表（base64或URL）
        page_numbers: 页码列表
    
    返回:
        包含system和user消息的字典
    """
    image_count = len(images)
    
    user_message = EXTRACT_MM_USER_TEMPLATE.format(
        image_count=image_count
    )
    
    return {
        "system": EXTRACT_MM_SYSTEM_PROMPT,
        "user": user_message,
        "images": images
    }


# 示例输出格式
EXAMPLE_OUTPUT = {
    "student_info": {
        "name": "张三",
        "student_id": "20210001"
    },
    "mm_tokens": [
        {
            "id": "T0",
            "text": "姓名：张三",
            "page": 0,
            "bbox": {"x1": 50, "y1": 30, "x2": 200, "y2": 60},
            "conf": 0.98,
            "line_id": "L0"
        },
        {
            "id": "T1",
            "text": "学号：20210001",
            "page": 0,
            "bbox": {"x1": 50, "y1": 70, "x2": 250, "y2": 100},
            "conf": 0.97,
            "line_id": "L1"
        },
        {
            "id": "T2",
            "text": "1. 解：设三角形三边为a, b, c",
            "page": 0,
            "bbox": {"x1": 50, "y1": 150, "x2": 500, "y2": 180},
            "conf": 0.95,
            "line_id": "L2"
        }
    ]
}


# 高级提示词 - 针对不同场景
HANDWRITING_PROMPT_ADDON = """
**手写识别增强:**
- 对于手写文本，提高容错率
- 识别常见的手写字体变化
- 处理潦草字迹和连笔
"""

PRINTED_PROMPT_ADDON = """
**打印文本识别:**
- 精确识别打印字体
- 保持原始格式和排版
- 识别特殊符号和公式
"""

MIXED_PROMPT_ADDON = """
**混合内容识别:**
- 区分打印题目和手写答案
- 分别标注不同类型的文本
- 保持题目和答案的对应关系
"""
