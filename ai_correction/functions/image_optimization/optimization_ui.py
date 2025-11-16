"""
图片优化UI组件
提供Streamlit界面组件，包括设置面板、预览对比、批量操作
"""
import streamlit as st
from typing import List, Optional, Dict, Any
from PIL import Image
import os

from .models import (
    OptimizationSettings,
    OptimizationResult,
    OptimizationMode,
    EnhanceMode
)


class OptimizationUI:
    """
    图片优化UI组件
    封装Streamlit界面元素
    """
    
    @staticmethod
    def render_settings_panel() -> OptimizationSettings:
        """
        渲染设置面板
        
        Returns:
            优化设置对象
        """
        st.subheader("⚙️ 图片优化设置")
        
        # 主开关
        enable_optimization = st.checkbox(
            "启用图片优化",
            value=st.session_state.get('enable_optimization', False),
            help="开启后将自动优化上传的图片，提升AI识别准确率"
        )
        
        if not enable_optimization:
            st.info("💡 图片优化功能已关闭，将直接使用原图进行批改")
            return OptimizationSettings(enable_optimization=False)
        
        # 优化模式选择
        st.write("**优化模式**")
        mode_options = {
            "智能模式（推荐）": OptimizationMode.SMART.value,
            "快速模式": OptimizationMode.FAST.value,
            "深度优化": OptimizationMode.DEEP.value,
            "仅切边": OptimizationMode.CROP_ONLY.value
        }
        
        mode_descriptions = {
            "智能模式（推荐）": "全面优化，适合大部分场景（切边+矫正+增强+锐化）",
            "快速模式": "快速处理，适合质量较好的图片（切边+矫正+增亮）",
            "深度优化": "深度处理，适合复杂背景或手写图片（去阴影+全面增强）",
            "仅切边": "只去除背景，保留原图其他特征"
        }
        
        selected_mode_name = st.radio(
            "选择优化方案",
            options=list(mode_options.keys()),
            help="不同模式适用于不同场景"
        )
        
        optimization_mode = mode_options[selected_mode_name]
        
        # 显示模式说明
        st.caption(f"📝 {mode_descriptions[selected_mode_name]}")
        
        # 高级设置（可折叠）
        with st.expander("🔧 高级设置", expanded=False):
            auto_optimize = st.checkbox(
                "自动应用优化",
                value=False,
                help="开启后将自动应用优化结果，无需手动确认"
            )
            
            keep_original = st.checkbox(
                "保留原图备份",
                value=True,
                help="保留原图以便需要时使用"
            )
            
            # 增强级别
            enhancement_level = st.select_slider(
                "增强级别",
                options=[
                    ("禁用", EnhanceMode.DISABLED.value),
                    ("增亮", EnhanceMode.BRIGHTEN.value),
                    ("增强锐化", EnhanceMode.ENHANCE_SHARPEN.value),
                    ("黑白", EnhanceMode.BLACK_WHITE.value),
                    ("去阴影", EnhanceMode.SHADOW_REMOVAL.value)
                ],
                value=("增强锐化", EnhanceMode.ENHANCE_SHARPEN.value),
                format_func=lambda x: x[0],
                help="选择图片增强的强度"
            )
        
        # 构建设置对象
        settings = OptimizationSettings.get_preset(optimization_mode)
        settings.enable_optimization = enable_optimization
        
        if 'auto_optimize' in locals():
            settings.auto_optimize = auto_optimize
            settings.keep_original = keep_original
            settings.api_params.enhance_mode = enhancement_level[1]
        
        # 保存到session state
        st.session_state['optimization_settings'] = settings
        st.session_state['enable_optimization'] = enable_optimization
        
        return settings
    
    @staticmethod
    def render_preview_panel(result: OptimizationResult) -> str:
        """
        渲染预览面板
        
        Args:
            result: 优化结果
            
        Returns:
            用户选择（'optimized' | 'original' | 'retake' | 'adjust'）
        """
        if not result.success:
            st.error(f"❌ 优化失败: {result.error_message}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 重新拍摄", use_container_width=True):
                    return 'retake'
            with col2:
                if st.button("📁 使用原图", use_container_width=True):
                    return 'original'
            
            return 'original'  # 默认使用原图
        
        st.success("✅ 图片优化完成")
        
        # 对比视图
        st.write("**📊 优化效果对比**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**原图**")
            try:
                original_img = Image.open(result.original_path)
                st.image(original_img, use_container_width=True)
            except Exception as e:
                st.error(f"无法加载原图: {e}")
        
        with col2:
            st.write("**优化后**")
            if result.optimized_path and os.path.exists(result.optimized_path):
                try:
                    optimized_img = Image.open(result.optimized_path)
                    st.image(optimized_img, use_container_width=True)
                except Exception as e:
                    st.error(f"无法加载优化图: {e}")
        
        # 优化信息
        if result.metadata:
            st.write("**📈 优化详情**")
            
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            
            with metrics_col1:
                st.metric(
                    "尺寸变化",
                    f"{result.metadata.cropped_width}x{result.metadata.cropped_height}",
                    f"从 {result.metadata.origin_width}x{result.metadata.origin_height}"
                )
            
            with metrics_col2:
                st.metric(
                    "处理时间",
                    f"{result.metadata.duration:.0f}ms"
                )
            
            with metrics_col3:
                if result.metadata.quality_scores:
                    improvement = result.metadata.quality_scores.get('improvement', 0)
                    st.metric(
                        "质量提升",
                        f"{improvement:+.1f}分",
                        delta_color="normal" if improvement > 0 else "inverse"
                    )
        
        # 操作按钮
        st.write("**选择操作**")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ 使用优化图", use_container_width=True, type="primary"):
                return 'optimized'
        
        with col2:
            if st.button("📁 使用原图", use_container_width=True):
                return 'original'
        
        with col3:
            if st.button("🔄 重新拍摄", use_container_width=True):
                return 'retake'
        
        with col4:
            if st.button("🔧 调整参数", use_container_width=True):
                return 'adjust'
        
        return 'pending'  # 等待用户选择
    
    @staticmethod
    def render_batch_results(results: List[OptimizationResult]) -> List[str]:
        """
        渲染批量优化结果
        
        Args:
            results: 优化结果列表
            
        Returns:
            最终使用的图片路径列表
        """
        st.subheader("📦 批量优化结果")
        
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        
        # 显示汇总信息
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("总数", total_count)
        
        with col2:
            st.metric("成功", success_count, delta=f"{success_count/total_count*100:.0f}%")
        
        with col3:
            st.metric("失败", total_count - success_count)
        
        # 详细列表
        final_paths = []
        
        for idx, result in enumerate(results, 1):
            with st.expander(f"图片 {idx}: {os.path.basename(result.original_path)}", expanded=False):
                if result.success:
                    st.success("✅ 优化成功")
                    
                    # 显示缩略图对比
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption("原图")
                        try:
                            img = Image.open(result.original_path)
                            st.image(img, width=200)
                        except:
                            pass
                    
                    with col2:
                        st.caption("优化后")
                        if result.optimized_path:
                            try:
                                img = Image.open(result.optimized_path)
                                st.image(img, width=200)
                            except:
                                pass
                    
                    # 选择使用哪张图
                    choice = st.radio(
                        "使用",
                        options=["优化图", "原图"],
                        key=f"choice_{idx}",
                        horizontal=True
                    )
                    
                    if choice == "优化图" and result.optimized_path:
                        final_paths.append(result.optimized_path)
                    else:
                        final_paths.append(result.original_path)
                else:
                    st.error(f"❌ 优化失败: {result.error_message}")
                    final_paths.append(result.original_path)
        
        # 批量操作
        st.write("**批量操作**")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ 全部使用优化图", use_container_width=True):
                final_paths = [
                    r.optimized_path if r.success and r.optimized_path else r.original_path
                    for r in results
                ]
        
        with col2:
            if st.button("📁 全部使用原图", use_container_width=True):
                final_paths = [r.original_path for r in results]
        
        return final_paths
    
    @staticmethod
    def render_progress_bar(current: int, total: int, status: str = ""):
        """
        渲染进度条
        
        Args:
            current: 当前进度
            total: 总数
            status: 状态文本
        """
        progress = current / total if total > 0 else 0
        st.progress(progress, text=f"{status} ({current}/{total})")
    
    @staticmethod
    def render_quality_report(report: Any):
        """
        渲染质量检测报告
        
        Args:
            report: 质量报告对象
        """
        st.write("**🔍 图片质量检测**")
        
        # 总分
        score_color = "🟢" if report.total_score >= 80 else "🟡" if report.total_score >= 60 else "🔴"
        st.metric(
            "质量评分",
            f"{score_color} {report.total_score:.0f}/100",
            report.recommendation
        )
        
        # 详细指标
        with st.expander("📊 详细指标", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("清晰度", f"{report.clarity_score:.1f}/40")
                st.metric("倾斜度", f"{report.tilt_score:.1f}/20")
            
            with col2:
                st.metric("背景", f"{report.background_score:.1f}/20")
                st.metric("尺寸", f"{report.size_score:.1f}/20")
            
            st.caption(f"📐 尺寸: {report.width}x{report.height}")
            st.caption(f"📏 倾斜角度: {report.tilt_angle:.1f}°")
            st.caption(f"🌫️ 清晰度方差: {report.variance:.0f}")
