"""全局模型配置

统一使用 Gemini 3 Flash Preview 模型。
"""

# ============================================================
# 统一模型配置 - Gemini 3 Flash Preview
# ============================================================

MODEL = "gemini-3-flash-preview"

# 兼容别名
DEFAULT_MODEL = MODEL
LITE_MODEL = MODEL
CACHE_MODEL = MODEL


def get_model() -> str:
    """获取模型名称
    
    Returns:
        模型名称（gemini-3-flash-preview）
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


def get_model_for_task(task_type: str) -> str:
    """根据任务类型获取模型（兼容旧接口，所有任务返回相同模型）
    
    Args:
        task_type: 任务类型（忽略）
        
    Returns:
        模型名称（gemini-3-flash-preview）
    """
    return MODEL


MODEL_INFO = {
    "gemini-3-flash-preview": {
        "description": "Gemini 3 Flash Preview - 统一使用的模型",
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
