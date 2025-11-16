"""
图片优化模块 - Image Optimization Module

集成Textin API实现图片智能切边、矫正和增强功能
"""

from .models import (
    OptimizationSettings,
    OptimizationResult,
    OptimizationMetadata,
    QualityReport,
    APIParameters
)

from .textin_client import TextinClient
from .quality_checker import QualityChecker
from .image_optimizer import ImageOptimizer
from .optimization_ui import OptimizationUI

__all__ = [
    'OptimizationSettings',
    'OptimizationResult',
    'OptimizationMetadata',
    'QualityReport',
    'APIParameters',
    'TextinClient',
    'QualityChecker',
    'ImageOptimizer',
    'OptimizationUI'
]
