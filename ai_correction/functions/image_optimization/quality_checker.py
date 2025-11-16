"""
图片质量检测器
实现清晰度、倾斜度、背景复杂度检测和质量评分
"""
import os
import logging
from typing import Optional
import cv2
import numpy as np
from PIL import Image

from .models import QualityReport

logger = logging.getLogger(__name__)


class QualityChecker:
    """
    图片质量检测器
    检测图片的清晰度、倾斜度、背景复杂度等指标
    """
    
    # 评分权重
    CLARITY_WEIGHT = 0.4  # 清晰度权重40%
    TILT_WEIGHT = 0.2     # 倾斜度权重20%
    BACKGROUND_WEIGHT = 0.2  # 背景权重20%
    SIZE_WEIGHT = 0.2     # 尺寸权重20%
    
    # 阈值设置
    MIN_CLARITY_VARIANCE = 100  # 最小清晰度方差
    MAX_TILT_ANGLE = 5.0       # 最大允许倾斜角度（度）
    MAX_EDGE_DENSITY = 0.3     # 最大边缘密度
    MIN_WIDTH = 500            # 最小宽度
    MIN_HEIGHT = 500           # 最小高度
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 最大文件大小（10MB）
    
    def __init__(self):
        """初始化质量检测器"""
        logger.info("QualityChecker初始化成功")
    
    def check_quality(self, image_path: str) -> QualityReport:
        """
        检测图片质量
        
        Args:
            image_path: 图片路径
            
        Returns:
            质量报告
        """
        logger.info(f"开始检测图片质量: {image_path}")
        
        # 创建报告
        report = QualityReport(image_path=image_path)
        
        try:
            # 读取图片
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"无法读取图片: {image_path}")
                report.recommendation = "无法读取图片文件"
                return report
            
            # 获取基本信息
            report.height, report.width = image.shape[:2]
            report.file_size = os.path.getsize(image_path)
            
            # 检测各项指标
            report.clarity_score = self._check_clarity(image, report)
            report.tilt_score = self._check_tilt(image, report)
            report.background_score = self._check_background(image, report)
            report.size_score = self._check_size(report)
            
            # 计算总分和建议
            report.calculate_total_score()
            
            logger.info(
                f"质量检测完成: {image_path}, "
                f"总分: {report.total_score:.1f}, "
                f"是否需要优化: {report.should_optimize}"
            )
            
            return report
            
        except Exception as e:
            logger.error(f"质量检测失败: {image_path}, 错误: {e}", exc_info=True)
            report.recommendation = f"质量检测失败: {str(e)}"
            return report
    
    def _check_clarity(self, image: np.ndarray, report: QualityReport) -> float:
        """
        检测清晰度（使用Laplacian方差）
        
        Args:
            image: OpenCV图像
            report: 质量报告（用于记录详细指标）
            
        Returns:
            清晰度得分（0-40）
        """
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 计算Laplacian方差
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        
        report.variance = variance
        
        # 评分：方差越大越清晰
        # 方差 < 100: 模糊，得分低
        # 方差 > 500: 清晰，得分高
        if variance < self.MIN_CLARITY_VARIANCE:
            score = (variance / self.MIN_CLARITY_VARIANCE) * 20  # 0-20分
        elif variance < 500:
            score = 20 + ((variance - self.MIN_CLARITY_VARIANCE) / 400) * 15  # 20-35分
        else:
            score = min(40, 35 + ((variance - 500) / 500) * 5)  # 35-40分
        
        logger.debug(f"清晰度检测: 方差={variance:.2f}, 得分={score:.1f}")
        return score
    
    def _check_tilt(self, image: np.ndarray, report: QualityReport) -> float:
        """
        检测倾斜度（使用Hough直线检测）
        
        Args:
            image: OpenCV图像
            report: 质量报告
            
        Returns:
            倾斜度得分（0-20）
        """
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 边缘检测
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Hough直线检测
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
            
            if lines is None or len(lines) == 0:
                # 没有检测到直线，可能是复杂图片，给中等分数
                report.tilt_angle = 0.0
                return 15.0
            
            # 计算主要直线的角度
            angles = []
            for line in lines[:10]:  # 只考虑前10条直线
                rho, theta = line[0]
                angle = np.abs(theta * 180 / np.pi - 90)  # 转换为与水平线的夹角
                if angle > 45:
                    angle = 90 - angle
                angles.append(angle)
            
            # 取中位数作为倾斜角度
            tilt_angle = np.median(angles) if angles else 0.0
            report.tilt_angle = tilt_angle
            
            # 评分：角度越小得分越高
            if tilt_angle <= self.MAX_TILT_ANGLE:
                score = 20.0
            elif tilt_angle <= 15:
                score = 20 - ((tilt_angle - self.MAX_TILT_ANGLE) / 10) * 10  # 10-20分
            else:
                score = max(0, 10 - ((tilt_angle - 15) / 15) * 10)  # 0-10分
            
            logger.debug(f"倾斜度检测: 角度={tilt_angle:.2f}°, 得分={score:.1f}")
            return score
            
        except Exception as e:
            logger.warning(f"倾斜度检测失败: {e}")
            return 15.0  # 失败时给中等分数
    
    def _check_background(self, image: np.ndarray, report: QualityReport) -> float:
        """
        检测背景复杂度（使用边缘密度）
        
        Args:
            image: OpenCV图像
            report: 质量报告
            
        Returns:
            背景得分（0-20）
        """
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 边缘检测
            edges = cv2.Canny(gray, 50, 150)
            
            # 计算边缘密度
            total_pixels = edges.size
            edge_pixels = np.count_nonzero(edges)
            edge_density = edge_pixels / total_pixels
            
            report.edge_density = edge_density
            
            # 评分：边缘密度越低得分越高（背景越简洁）
            if edge_density <= 0.1:
                score = 20.0  # 背景简洁
            elif edge_density <= self.MAX_EDGE_DENSITY:
                score = 20 - ((edge_density - 0.1) / 0.2) * 10  # 10-20分
            else:
                score = max(0, 10 - ((edge_density - self.MAX_EDGE_DENSITY) / 0.2) * 10)  # 0-10分
            
            logger.debug(f"背景复杂度检测: 边缘密度={edge_density:.3f}, 得分={score:.1f}")
            return score
            
        except Exception as e:
            logger.warning(f"背景复杂度检测失败: {e}")
            return 15.0  # 失败时给中等分数
    
    def _check_size(self, report: QualityReport) -> float:
        """
        检测图片尺寸
        
        Args:
            report: 质量报告
            
        Returns:
            尺寸得分（0-20）
        """
        width = report.width
        height = report.height
        file_size = report.file_size
        
        score = 20.0
        
        # 检查宽度
        if width < self.MIN_WIDTH:
            score -= 10
        
        # 检查高度
        if height < self.MIN_HEIGHT:
            score -= 10
        
        # 检查文件大小
        if file_size > self.MAX_FILE_SIZE:
            score -= 5
        elif file_size < 50 * 1024:  # 小于50KB可能质量不佳
            score -= 5
        
        logger.debug(
            f"尺寸检测: {width}x{height}, "
            f"文件大小={file_size/1024:.1f}KB, 得分={score:.1f}"
        )
        
        return max(0, score)
    
    def calculate_score(self, image_path: str) -> float:
        """
        计算图片质量评分
        
        Args:
            image_path: 图片路径
            
        Returns:
            质量评分（0-100）
        """
        report = self.check_quality(image_path)
        return report.total_score
    
    def should_optimize(self, image_path: str, threshold: float = 60.0) -> bool:
        """
        判断是否需要优化
        
        Args:
            image_path: 图片路径
            threshold: 评分阈值（低于此值需要优化）
            
        Returns:
            是否需要优化
        """
        score = self.calculate_score(image_path)
        return score < threshold
