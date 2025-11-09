#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph Agents - 符合原始需求的 Agent 架构
集成到 ai_correction 中，与现有 calling_api.py 和 ai_recognition.py 协作
"""

# 延迟导入，避免缺少依赖时报错
__all__ = []

try:
    from .upload_validator import UploadValidator
    __all__.append('UploadValidator')
except ImportError:
    pass

try:
    from .ocr_vision_agent import OCRVisionAgent
    __all__.append('OCRVisionAgent')
except ImportError:
    pass

try:
    from .rubric_interpreter import RubricInterpreter
    __all__.append('RubricInterpreter')
except ImportError:
    pass

try:
    from .scoring_agent import ScoringAgent
    __all__.append('ScoringAgent')
except ImportError:
    pass

try:
    from .annotation_builder import AnnotationBuilder
    __all__.append('AnnotationBuilder')
except ImportError:
    pass

try:
    from .knowledge_miner import KnowledgeMiner
    __all__.append('KnowledgeMiner')
except ImportError:
    pass

try:
    from .result_assembler import ResultAssembler
    __all__.append('ResultAssembler')
except ImportError:
    pass
