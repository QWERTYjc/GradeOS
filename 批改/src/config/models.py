"""全局模型配置

统一管理所有 Gemini 模型的配置，方便切换和维护。
"""

import os
from typing import Optional


# ============================================================
# 全局默认模型配置
# ============================================================

# 主要模型 - 用于复杂推理任务（批改、评分标准解析等）
# 可选模型:
#   - gemini-3-flash-preview: Gemini 3 Flash Preview（最新预览版）
#   - gemini-2.5-flash: Gemini 2.5 Flash（稳定版）
#   - gemini-2.5-flash-preview-09-2025: Gemini 2.5 Flash Preview
#   - gemini-2.0-flash: Gemini 2.0 Flash
DEFAULT_MODEL = "gemini-3-flash-preview"

# 轻量模型 - 用于简单任务（学生识别、页面分析等）
LITE_MODEL = "gemini-3-flash-preview"

# 缓存模型 - 用于 Context Caching（必须支持缓存功能）
# 支持缓存的模型: gemini-2.5-flash, gemini-2.5-pro
CACHE_MODEL = "gemini-3-flash-preview"


# ============================================================
# 模型获取函数
# ============================================================

def get_default_model() -> str:
    """获取默认模型名称
    
    优先使用环境变量 GEMINI_MODEL，否则使用 DEFAULT_MODEL
    """
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def get_lite_model() -> str:
    """获取轻量模型名称
    
    优先使用环境变量 GEMINI_LITE_MODEL，否则使用 LITE_MODEL
    """
    return os.getenv("GEMINI_LITE_MODEL", LITE_MODEL)


def get_cache_model() -> str:
    """获取缓存模型名称
    
    优先使用环境变量 GEMINI_CACHE_MODEL，否则使用 CACHE_MODEL
    """
    return os.getenv("GEMINI_CACHE_MODEL", CACHE_MODEL)


def get_model_for_task(task_type: str) -> str:
    """根据任务类型获取推荐的模型
    
    Args:
        task_type: 任务类型，可选值:
            - "grading": 批改任务
            - "rubric_parsing": 评分标准解析
            - "student_identification": 学生识别
            - "layout_analysis": 布局分析
            - "reasoning": 深度推理
            - "cached": 需要缓存的任务
            
    Returns:
        推荐的模型名称
    """
    task_model_map = {
        "grading": get_default_model(),
        "rubric_parsing": get_default_model(),
        "student_identification": get_lite_model(),
        "layout_analysis": get_lite_model(),
        "reasoning": get_default_model(),
        "cached": get_cache_model(),
    }
    
    return task_model_map.get(task_type, get_default_model())


# ============================================================
# 模型信息
# ============================================================

MODEL_INFO = {
    "gemini-3-flash-preview": {
        "description": "Gemini 3 Flash Preview - 最新预览版，增强能力",
        "supports_vision": True,
        "supports_caching": False,  # Preview 版本可能不支持缓存
        "recommended_for": ["grading", "rubric_parsing", "reasoning"],
    },
    "gemini-2.5-flash": {
        "description": "Gemini 2.5 Flash - 稳定版，推荐用于生产环境",
        "supports_vision": True,
        "supports_caching": True,
        "recommended_for": ["grading", "rubric_parsing", "reasoning"],
    },
    "gemini-2.5-flash-preview-09-2025": {
        "description": "Gemini 2.5 Flash Preview - 预览版，早期访问新功能",
        "supports_vision": True,
        "supports_caching": True,
        "recommended_for": ["grading", "rubric_parsing", "reasoning"],
    },
    "gemini-2.5-flash-lite": {
        "description": "Gemini 2.5 Flash Lite - 轻量级模型，适合简单任务",
        "supports_vision": True,
        "supports_caching": False,
        "recommended_for": ["student_identification", "layout_analysis"],
    },
    "gemini-2.0-flash": {
        "description": "Gemini 2.0 Flash - 快速、高效的多模态模型",
        "supports_vision": True,
        "supports_caching": True,
        "recommended_for": ["grading", "rubric_parsing", "reasoning"],
    },
}


def print_model_config():
    """打印当前模型配置"""
    print("=" * 50)
    print("当前 Gemini 模型配置")
    print("=" * 50)
    print(f"默认模型: {get_default_model()}")
    print(f"轻量模型: {get_lite_model()}")
    print(f"缓存模型: {get_cache_model()}")
    print("=" * 50)
