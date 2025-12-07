"""
图片优化模块集成助手
提供简单的接口用于在main.py中集成图片优化功能
"""
import streamlit as st
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

# 导入图片优化模块
try:
    from functions.image_optimization import (
        ImageOptimizer,
        OptimizationSettings,
        OptimizationUI,
        QualityChecker
    )
    OPTIMIZATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"图片优化模块导入失败: {e}")
    OPTIMIZATION_AVAILABLE = False


class ImageOptimizationIntegration:
    """
    图片优化集成类
    封装图片优化功能的集成逻辑
    """
    
    @staticmethod
    def init_session_state():
        """初始化session state"""
        if 'optimization_enabled' not in st.session_state:
            st.session_state.optimization_enabled = False
        if 'optimization_settings' not in st.session_state:
            st.session_state.optimization_settings = None
        if 'optimization_results' not in st.session_state:
            st.session_state.optimization_results = {}
        if 'optimized_file_paths' not in st.session_state:
            st.session_state.optimized_file_paths = []
    
    @staticmethod
    def render_settings_sidebar():
        """
        在侧边栏渲染设置面板
        
        Returns:
            是否启用优化
        """
        if not OPTIMIZATION_AVAILABLE:
            return False
        
        ImageOptimizationIntegration.init_session_state()
        
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 📷 图片优化")
            
            # 渲染设置面板
            settings = OptimizationUI.render_settings_panel()
            
            if settings.enable_optimization:
                st.session_state.optimization_enabled = True
                st.session_state.optimization_settings = settings
                return True
            else:
                st.session_state.optimization_enabled = False
                return False
    
    @staticmethod
    def optimize_uploaded_files(
        uploaded_files: List[Any],
        file_paths: List[str]
    ) -> List[str]:
        """
        优化上传的文件
        
        Args:
            uploaded_files: Streamlit上传文件对象列表
            file_paths: 保存的文件路径列表
            
        Returns:
            最终使用的文件路径列表（优化后或原始）
        """
        if not OPTIMIZATION_AVAILABLE or not st.session_state.get('optimization_enabled', False):
            return file_paths
        
        # 过滤出图片文件
        image_paths = []
        non_image_paths = []
        
        for i, path in enumerate(file_paths):
            file_ext = Path(path).suffix.lower()
            if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif']:
                image_paths.append(path)
            else:
                non_image_paths.append(path)
        
        if not image_paths:
            st.info("📝 未检测到图片文件，跳过优化")
            return file_paths
        
        st.info(f"🔍 检测到 {len(image_paths)} 张图片，开始优化...")
        
        # 创建优化器
        settings = st.session_state.optimization_settings
        optimizer = ImageOptimizer(settings=settings)
        
        # 显示进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        final_image_paths = []
        
        try:
            # 批量优化
            results = optimizer.optimize_batch(
                image_paths,
                max_workers=3,
                force=False
            )
            
            # 处理每个结果
            for idx, result in enumerate(results):
                progress = (idx + 1) / len(results)
                progress_bar.progress(progress)
                status_text.text(f"处理中... ({idx + 1}/{len(results)})")
                
                # 保存结果
                st.session_state.optimization_results[result.original_path] = result
                
                # 根据设置决定使用哪个文件
                if settings.auto_optimize and result.success and result.optimized_path:
                    final_image_paths.append(result.optimized_path)
                    
                    # 显示优化效果对比
                    _show_optimization_comparison(result, idx + 1)
                else:
                    # 需要用户确认
                    if result.success and result.optimized_path:
                        # 显示预览并获取用户选择
                        choice = OptimizationUI.render_preview_panel(result)
                        
                        if choice == 'optimized':
                            final_image_paths.append(result.optimized_path)
                        elif choice == 'original':
                            final_image_paths.append(result.original_path)
                        elif choice == 'retake':
                            st.info("请重新上传图片")
                            return []  # 返回空列表表示需要重新上传
                        else:
                            # 默认使用原图
                            final_image_paths.append(result.original_path)
                    else:
                        # 优化失败，使用原图
                        final_image_paths.append(result.original_path)
            
            progress_bar.progress(1.0)
            status_text.text("✅ 优化完成！")
            
            # 保存优化后的路径
            st.session_state.optimized_file_paths = final_image_paths
            
            # 合并非图片文件
            final_paths = final_image_paths + non_image_paths
            
            st.success(f"✅ 已优化 {len(final_image_paths)} 张图片")
            
            return final_paths
            
        except Exception as e:
            st.error(f"❌ 优化过程出错: {e}")
            logging.error(f"图片优化失败: {e}", exc_info=True)
            return file_paths  # 出错时返回原始路径
        
        finally:
            optimizer.close()
    
    @staticmethod
    def show_optimization_status():
        """显示优化状态信息"""
        if not OPTIMIZATION_AVAILABLE:
            return
        
        if st.session_state.get('optimization_enabled', False):
            results = st.session_state.get('optimization_results', {})
            if results:
                success_count = sum(1 for r in results.values() if r.success)
                total_count = len(results)
                
                st.info(f"📊 图片优化: {success_count}/{total_count} 成功")
                
                # 显示详细信息
                with st.expander("查看优化详情", expanded=False):
                    for path, result in results.items():
                        if result.success:
                            st.success(f"✅ {Path(path).name}")
                            if result.metadata and result.metadata.quality_scores:
                                improvement = result.metadata.quality_scores.get('improvement', 0)
                                st.caption(f"质量提升: {improvement:+.1f}分")
                        else:
                            st.error(f"❌ {Path(path).name}: {result.error_message}")


# 便捷函数
def init_image_optimization():
    """初始化图片优化功能"""
    ImageOptimizationIntegration.init_session_state()


def render_optimization_settings():
    """渲染优化设置面板"""
    return ImageOptimizationIntegration.render_settings_sidebar()


def process_uploaded_images(uploaded_files, file_paths):
    """处理上传的图片"""
    return ImageOptimizationIntegration.optimize_uploaded_files(uploaded_files, file_paths)


def show_optimization_info():
    """显示优化信息"""
    ImageOptimizationIntegration.show_optimization_status()


def _show_optimization_comparison(result, file_index: int):
    """
    显示单个文件的优化对比
    
    Args:
        result: OptimizationResult 对象
        file_index: 文件序号
    """
    from PIL import Image
    import os
    
    if not result.success or not result.optimized_path:
        return
    
    st.markdown(f"**✅ 已优化 {file_index} 张图片**")
    
    # 创建对比视图
    col1, col2 = st.columns(2)
    
    with col1:
        st.caption("📷 原图")
        try:
            if os.path.exists(result.original_path):
                original_img = Image.open(result.original_path)
                st.image(original_img, use_container_width=True)
        except Exception as e:
            st.error(f"无法加载原图: {e}")
    
    with col2:
        st.caption("✨ 增强后")
        try:
            if os.path.exists(result.optimized_path):
                optimized_img = Image.open(result.optimized_path)
                st.image(optimized_img, use_container_width=True)
        except Exception as e:
            st.error(f"无法加载优化图: {e}")
    
    # 显示优化指标
    if result.metadata:
        metrics_cols = st.columns(3)
        
        with metrics_cols[0]:
            if result.metadata.origin_width and result.metadata.cropped_width:
                st.caption(f"📐 尺寸: {result.metadata.origin_width}×{result.metadata.origin_height} → {result.metadata.cropped_width}×{result.metadata.cropped_height}")
        
        with metrics_cols[1]:
            if result.metadata.duration:
                st.caption(f"⏱️ 耗时: {result.metadata.duration:.0f}ms")
        
        with metrics_cols[2]:
            if result.metadata.quality_scores:
                improvement = result.metadata.quality_scores.get('improvement', 0)
                if improvement > 0:
                    st.caption(f"📈 质量提升: +{improvement:.1f}分")
                else:
                    st.caption(f"📊 质量: {result.metadata.quality_scores.get('after', 0):.1f}分")
    
    st.markdown("---")
