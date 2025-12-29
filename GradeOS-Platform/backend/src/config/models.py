"""全局模型配置

统一使用 Gemini 2.0 Flash 模型。
"""

import os

# ============================================================
# 统一模型配置 - Gemini 2.0 Flash
# ============================================================

# 从环境变量获取，默认使用 gemini-2.0-flash-exp
MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash-exp")

# 兼容别名
DEFAULT_MODEL = MODEL
LITE_MODEL = MODEL
CACHE_MODEL = MODEL
INDEX_MODEL = os.getenv("INDEX_MODEL", "gemini-3.0-flash")


def get_model() -> str:
    """获取模型名称
    
    Returns:
        模型名称
    """
    return MODEL


# 兼容旧接口
def get_default_model() -> str:
    """获取默认模型名称（兼容旧接口）"""
    return MODEL


def get_lite_model() -> str:
    """获取轻量模型名称（兼容旧接口，返回相同模型）"""
    return MODEL


def get_cache_model() -> str:
    """获取缓存模型名称（兼容旧接口，返回相同模型）"""
    return MODEL


def get_index_model() -> str:
    """获取索引模型名称"""
    return INDEX_MODEL


def get_model_for_task(task_type: str) -> str:
    """根据任务类型获取模型（兼容旧接口，所有任务返回相同模型）
    
    Args:
        task_type: 任务类型（忽略）
        
    Returns:
        模型名称
    """
    return MODEL


MODEL_INFO = {
    "gemini-2.0-flash-exp": {
        "description": "Gemini 2.0 Flash Experimental - 最新的多模态模型",
        "supports_vision": True,
        "supports_caching": True,
    },
    "gemini-1.5-flash": {
        "description": "Gemini 1.5 Flash - 稳定的多模态模型",
        "supports_vision": True,
        "supports_caching": True,
    }
}


def print_model_config():
    """打印当前模型配置"""
    print("=" * 50)
    print("Gemini 模型配置")
    print("=" * 50)
    print(f"模型: {MODEL}")
    print("=" * 50)
