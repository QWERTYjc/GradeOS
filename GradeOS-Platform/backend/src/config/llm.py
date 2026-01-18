"""LLM 配置模块

统一管理 LLM 模型配置，支持 OpenRouter 和直连 Gemini API。
测试阶段使用 Gemini 3 Flash。
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional


class LLMProvider(Enum):
    """LLM 服务提供商"""
    OPENROUTER = "openrouter"
    GOOGLE = "google"  # 直连 Gemini API


@dataclass
class LLMConfig:
    """LLM 配置类"""
    
    provider: LLMProvider = LLMProvider.OPENROUTER
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    
    # 模型映射：不同用途使用的模型
    models: Dict[str, str] = field(default_factory=lambda: {
        "vision": "google/gemini-3-flash-preview",      # 视觉提取
        "text": "google/gemini-3-flash-preview",        # 文本批改
        "summary": "google/gemini-3-flash-preview",     # 总结生成
        "rubric": "google/gemini-3-flash-preview",      # 评分标准解析
    })
    
    # OpenRouter 额外 headers
    site_url: str = "https://gradeos.app"
    site_title: str = "GradeOS AI Grading"
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量加载配置
        
        优先级逻辑：
        1. 如果设置了 LLM_PROVIDER，使用指定的 provider
        2. 如果同时存在 GEMINI_API_KEY 和 OPENROUTER_API_KEY，默认使用 OpenRouter
        3. 如果只有其中一个，使用对应的 provider
        """
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        
        # 检查用户显式指定的 provider
        provider_str = os.getenv("LLM_PROVIDER", "").lower()
        
        if provider_str == "openrouter":
            provider = LLMProvider.OPENROUTER
            api_key = openrouter_key or gemini_key
            base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        elif provider_str == "google":
            provider = LLMProvider.GOOGLE
            api_key = gemini_key
            base_url = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        else:
            # 自动选择：优先 OpenRouter（如果两个都有）
            if openrouter_key:
                provider = LLMProvider.OPENROUTER
                api_key = openrouter_key
                base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
            elif gemini_key:
                provider = LLMProvider.GOOGLE
                api_key = gemini_key
                base_url = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
            else:
                # 没有任何 key，默认 OpenRouter 配置
                provider = LLMProvider.OPENROUTER
                api_key = ""
                base_url = "https://openrouter.ai/api/v1"
        
        # 允许自定义模型
        default_model = os.getenv("LLM_DEFAULT_MODEL", "google/gemini-3-flash-preview")
        
        return cls(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            models={
                "vision": os.getenv("LLM_VISION_MODEL", default_model),
                "text": os.getenv("LLM_TEXT_MODEL", default_model),
                "summary": os.getenv("LLM_SUMMARY_MODEL", default_model),
                "rubric": os.getenv("LLM_RUBRIC_MODEL", default_model),
            },
            site_url=os.getenv("LLM_SITE_URL", "https://gradeos.app"),
            site_title=os.getenv("LLM_SITE_TITLE", "GradeOS AI Grading"),
        )
    
    def get_model(self, purpose: str) -> str:
        """获取指定用途的模型名称"""
        return self.models.get(purpose, self.models.get("text", "google/gemini-3-flash-preview"))
    
    def get_headers(self) -> Dict[str, str]:
        """获取 OpenRouter 需要的额外 headers"""
        if self.provider == LLMProvider.OPENROUTER:
            return {
                "HTTP-Referer": self.site_url,
                "X-Title": self.site_title,
            }
        return {}


# 全局 LLM 配置
_llm_config: Optional[LLMConfig] = None


def get_llm_config() -> LLMConfig:
    """获取 LLM 配置"""
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig.from_env()
    return _llm_config


def set_llm_config(config: LLMConfig) -> None:
    """设置 LLM 配置"""
    global _llm_config
    _llm_config = config
