"""
图片优化模块数据模型
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class OptimizationMode(str, Enum):
    """优化模式枚举"""
    SMART = "smart"  # 智能模式（推荐）
    FAST = "fast"    # 快速模式
    DEEP = "deep"    # 深度优化
    CROP_ONLY = "crop_only"  # 仅切边


class EnhanceMode(int, Enum):
    """增强模式枚举"""
    DISABLED = -1  # 禁用增强
    BRIGHTEN = 1   # 增亮
    ENHANCE_SHARPEN = 2  # 增强并锐化（推荐）
    BLACK_WHITE = 3  # 黑白
    GRAYSCALE = 4   # 灰度
    SHADOW_REMOVAL = 5  # 去阴影增强
    DOT_MATRIX = 6  # 点阵图


@dataclass
class APIParameters:
    """Textin API调用参数"""
    enhance_mode: int = EnhanceMode.ENHANCE_SHARPEN.value  # 增强模式
    crop_image: int = 1  # 切边开关（1-开启，0-关闭）
    dewarp_image: int = 1  # 矫正开关
    deblur_image: int = 1  # 去模糊开关
    correct_direction: int = 1  # 方向校正
    jpeg_quality: int = 85  # 压缩质量（65-100）
    
    def to_query_string(self) -> str:
        """转换为URL查询字符串"""
        params = asdict(self)
        return '&'.join([f"{k}={v}" for k, v in params.items()])
    
    def to_dict(self) -> Dict[str, int]:
        """转换为字典"""
        return asdict(self)


@dataclass
class OptimizationSettings:
    """优化设置配置"""
    enable_optimization: bool = False  # 全局优化开关
    auto_optimize: bool = False  # 自动应用优化
    optimization_mode: str = OptimizationMode.SMART.value  # 优化模式
    enhancement_level: int = 2  # 增强级别（对应enhance_mode）
    keep_original: bool = True  # 保留原图备份
    api_params: APIParameters = field(default_factory=APIParameters)  # API参数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['api_params'] = self.api_params.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OptimizationSettings':
        """从字典创建"""
        api_params_data = data.pop('api_params', {})
        api_params = APIParameters(**api_params_data) if api_params_data else APIParameters()
        return cls(api_params=api_params, **data)
    
    @classmethod
    def get_preset(cls, mode: str) -> 'OptimizationSettings':
        """获取预设方案"""
        presets = {
            OptimizationMode.SMART.value: cls(
                enable_optimization=True,
                optimization_mode=OptimizationMode.SMART.value,
                api_params=APIParameters(
                    enhance_mode=EnhanceMode.ENHANCE_SHARPEN.value,
                    crop_image=1,
                    dewarp_image=1,
                    deblur_image=1,
                    correct_direction=1,
                    jpeg_quality=85
                )
            ),
            OptimizationMode.FAST.value: cls(
                enable_optimization=True,
                optimization_mode=OptimizationMode.FAST.value,
                api_params=APIParameters(
                    enhance_mode=EnhanceMode.BRIGHTEN.value,
                    crop_image=1,
                    dewarp_image=1,
                    deblur_image=0,
                    correct_direction=0,
                    jpeg_quality=85
                )
            ),
            OptimizationMode.DEEP.value: cls(
                enable_optimization=True,
                optimization_mode=OptimizationMode.DEEP.value,
                api_params=APIParameters(
                    enhance_mode=EnhanceMode.SHADOW_REMOVAL.value,
                    crop_image=1,
                    dewarp_image=1,
                    deblur_image=1,
                    correct_direction=1,
                    jpeg_quality=90
                )
            ),
            OptimizationMode.CROP_ONLY.value: cls(
                enable_optimization=True,
                optimization_mode=OptimizationMode.CROP_ONLY.value,
                api_params=APIParameters(
                    enhance_mode=EnhanceMode.DISABLED.value,
                    crop_image=1,
                    dewarp_image=0,
                    deblur_image=0,
                    correct_direction=0,
                    jpeg_quality=85
                )
            )
        }
        return presets.get(mode, presets[OptimizationMode.SMART.value])


@dataclass
class OptimizationMetadata:
    """优化元数据"""
    origin_width: int = 0  # 原始宽度
    origin_height: int = 0  # 原始高度
    cropped_width: int = 0  # 裁剪后宽度
    cropped_height: int = 0  # 裁剪后高度
    position: List[int] = field(default_factory=list)  # 切边坐标 [x1,y1,x2,y2,x3,y3,x4,y4]
    angle: int = 0  # 矫正角度（0/90/180/270）
    duration: float = 0.0  # API处理耗时（毫秒）
    quality_scores: Dict[str, float] = field(default_factory=dict)  # 质量评分
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class OptimizationResult:
    """优化结果"""
    original_path: str  # 原图路径
    optimized_path: Optional[str] = None  # 优化后图片路径
    metadata: Optional[OptimizationMetadata] = None  # 优化元数据
    success: bool = False  # 是否优化成功
    error_message: Optional[str] = None  # 错误信息
    created_at: datetime = field(default_factory=datetime.now)  # 优化时间
    
    def get_comparison_data(self) -> Dict[str, Any]:
        """获取对比数据"""
        if not self.metadata:
            return {}
        
        return {
            'original_path': self.original_path,
            'optimized_path': self.optimized_path,
            'size_reduction': f"{self.metadata.origin_width}x{self.metadata.origin_height} → "
                            f"{self.metadata.cropped_width}x{self.metadata.cropped_height}",
            'angle': self.metadata.angle,
            'duration': f"{self.metadata.duration:.0f}ms",
            'quality_improvement': self.metadata.quality_scores.get('improvement', 0)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        if self.metadata:
            data['metadata'] = self.metadata.to_dict()
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class QualityReport:
    """图片质量检测报告"""
    image_path: str  # 图片路径
    total_score: float = 0.0  # 总分（0-100）
    clarity_score: float = 0.0  # 清晰度得分（0-40）
    tilt_score: float = 0.0  # 倾斜度得分（0-20）
    background_score: float = 0.0  # 背景得分（0-20）
    size_score: float = 0.0  # 尺寸得分（0-20）
    
    # 详细指标
    variance: float = 0.0  # 方差（清晰度指标）
    tilt_angle: float = 0.0  # 倾斜角度（度）
    edge_density: float = 0.0  # 边缘密度
    width: int = 0  # 宽度
    height: int = 0  # 高度
    file_size: int = 0  # 文件大小（字节）
    
    should_optimize: bool = False  # 是否需要优化
    recommendation: str = ""  # 优化建议
    
    def calculate_total_score(self):
        """计算总分"""
        self.total_score = (
            self.clarity_score + 
            self.tilt_score + 
            self.background_score + 
            self.size_score
        )
        
        # 判断是否需要优化
        if self.total_score < 60:
            self.should_optimize = True
            self.recommendation = "图片质量较差，强烈建议优化"
        elif self.total_score < 80:
            self.should_optimize = True
            self.recommendation = "图片质量一般，建议优化"
        else:
            self.should_optimize = False
            self.recommendation = "图片质量良好，可选择性优化"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
