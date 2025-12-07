"""
图片优化器
整合TextinClient和QualityChecker，实现完整的优化流程
"""
import os
import logging
from typing import List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import (
    OptimizationSettings,
    OptimizationResult,
    OptimizationMetadata,
    APIParameters
)
from .textin_client import TextinClient, TextinAPIError
from .quality_checker import QualityChecker

logger = logging.getLogger(__name__)


class ImageOptimizer:
    """
    图片优化器
    整合质量检测和API调用，提供完整的优化功能
    """
    
    def __init__(
        self,
        settings: Optional[OptimizationSettings] = None,
        output_dir: str = "temp/uploads/optimized"
    ):
        """
        初始化优化器
        
        Args:
            settings: 优化设置（默认使用智能模式）
            output_dir: 优化图片输出目录
        """
        self.settings = settings or OptimizationSettings.get_preset("smart")
        self.output_dir = output_dir
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化组件
        self.textin_client = TextinClient()
        self.quality_checker = QualityChecker()
        
        logger.info(f"ImageOptimizer初始化成功，输出目录: {self.output_dir}")
    
    def optimize_image(
        self,
        image_path: str,
        force: bool = False,
        params: Optional[APIParameters] = None
    ) -> OptimizationResult:
        """
        优化单张图片
        
        Args:
            image_path: 图片路径
            force: 是否强制优化（跳过质量预检）
            params: API参数（默认使用设置中的参数）
            
        Returns:
            优化结果
        """
        logger.info(f"开始优化图片: {image_path}, 强制={force}")
        
        result = OptimizationResult(original_path=image_path)
        
        try:
            # 质量预检（除非强制优化）
            if not force and self.settings.optimization_mode != "force":
                quality_report = self.quality_checker.check_quality(image_path)
                
                logger.info(
                    f"质量预检结果: 总分={quality_report.total_score:.1f}, "
                    f"建议={quality_report.recommendation}"
                )
                
                # 质量过差，建议重拍
                if quality_report.total_score < 30:
                    result.success = False
                    result.error_message = (
                        f"图片质量过差（评分: {quality_report.total_score:.0f}/100），"
                        "建议重新拍摄以获得更好效果"
                    )
                    return result
                
                # 质量良好，可选优化
                if quality_report.total_score >= 80 and not self.settings.auto_optimize:
                    logger.info("图片质量良好，跳过优化")
                    result.success = True
                    result.optimized_path = image_path  # 使用原图
                    result.metadata = OptimizationMetadata(
                        quality_scores={
                            'before': quality_report.total_score,
                            'after': quality_report.total_score,
                            'improvement': 0
                        }
                    )
                    return result
            
            # 使用API参数
            if params is None:
                params = self.settings.api_params
            
            # 调用Textin API
            logger.info(f"调用Textin API优化图片: {image_path}")
            image_binary, metadata = self.textin_client.optimize_image(image_path, params)
            
            # 保存优化后的图片
            optimized_path = self._save_optimized_image(image_path, image_binary)
            
            # 构建结果
            result.success = True
            result.optimized_path = optimized_path
            result.metadata = metadata
            
            # 如果做了质量预检，计算改进度
            if 'quality_report' in locals():
                after_score = self.quality_checker.calculate_score(optimized_path)
                metadata.quality_scores = {
                    'before': quality_report.total_score,
                    'after': after_score,
                    'improvement': after_score - quality_report.total_score
                }
                
                logger.info(
                    f"优化完成，质量提升: "
                    f"{quality_report.total_score:.1f} → {after_score:.1f} "
                    f"(+{metadata.quality_scores['improvement']:.1f})"
                )
            else:
                logger.info(f"优化完成: {optimized_path}")
            
            return result
            
        except TextinAPIError as e:
            logger.error(f"API调用失败: {e.message}")
            result.success = False
            result.error_message = f"API调用失败: {e.message}"
            return result
        
        except Exception as e:
            logger.error(f"优化图片失败: {image_path}, 错误: {e}", exc_info=True)
            result.success = False
            result.error_message = f"优化失败: {str(e)}"
            return result
    
    def optimize_batch(
        self,
        image_paths: List[str],
        max_workers: int = 3,
        force: bool = False
    ) -> List[OptimizationResult]:
        """
        批量优化图片
        
        Args:
            image_paths: 图片路径列表
            max_workers: 最大并发数
            force: 是否强制优化
            
        Returns:
            优化结果列表
        """
        logger.info(f"开始批量优化，共{len(image_paths)}张图片，并发数={max_workers}")
        
        results = []
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_path = {
                executor.submit(self.optimize_image, path, force): path
                for path in image_paths
            }
            
            # 收集结果
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    status = "成功" if result.success else "失败"
                    logger.info(f"图片优化{status}: {path}")
                    
                except Exception as e:
                    logger.error(f"处理图片异常: {path}, 错误: {e}")
                    results.append(OptimizationResult(
                        original_path=path,
                        success=False,
                        error_message=str(e)
                    ))
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"批量优化完成，成功: {success_count}/{len(results)}")
        
        return results
    
    def _save_optimized_image(self, original_path: str, image_binary: bytes) -> str:
        """
        保存优化后的图片
        
        Args:
            original_path: 原图路径
            image_binary: 图片二进制数据
            
        Returns:
            保存后的文件路径（规范化为正斜杠）
        """
        # 生成文件名
        basename = os.path.basename(original_path)
        name, ext = os.path.splitext(basename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_optimized_{timestamp}{ext}"
        
        output_path = os.path.join(self.output_dir, filename)
        
        # 保存文件
        with open(output_path, 'wb') as f:
            f.write(image_binary)
        
        # 规范化路径（统一使用正斜杠，避免跨平台问题）
        normalized_path = output_path.replace('\\', '/')
        
        logger.debug(f"优化图片已保存: {normalized_path}")
        return normalized_path
    
    def check_api_status(self) -> bool:
        """
        检查API可用性
        
        Returns:
            API是否可用
        """
        return self.textin_client.check_api_status()
    
    def estimate_cost(self, image_count: int, cost_per_call: float = 0.01) -> float:
        """
        估算API调用成本
        
        Args:
            image_count: 图片数量
            cost_per_call: 单次调用成本（元）
            
        Returns:
            预估成本（元）
        """
        # 考虑质量预检可能跳过的图片（假设30%高质量图片跳过）
        estimated_calls = image_count * 0.7
        return estimated_calls * cost_per_call
    
    def close(self):
        """关闭资源"""
        if self.textin_client:
            self.textin_client.close()
        logger.info("ImageOptimizer资源已释放")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
