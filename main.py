#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 智能教育平台 - 统一入口
集成 BookScan-AI 扫描引擎与智能批改系统
"""

import streamlit as st
import sys
from pathlib import Path
import os

# 添加 ai_correction 目录到 Python 路径
ai_correction_path = Path(__file__).parent / "ai_correction"
if str(ai_correction_path) not in sys.path:
    sys.path.insert(0, str(ai_correction_path))

# 导入服务模块
from services.bookscan_s

# 页面配置
st.set_page_config(
    page_title="AI GURU | 智能教育平台",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """主函数"""
    # 初始化 session state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "dashboard"
    
    # 主标题
    st.markdown("# 🎓 AI GURU 智能教育平台")
    st.markdown("集成 BookScan-AI 扫描引擎与多模态智能批改系统")
    
    # 侧边栏导航
    with st.sidebar:
        st.markdown("## 🎓 AI GURU")
        st.markdown("智能教育平台")
        
        st.markdown("---")
        
        # 主要功能
        if st.button("🏠 主仪表板", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.rerun()
        
        if st.button("📱 扫描引擎", use_container_width=True):
            st.session_state.current_page = "scanner"
            st.rerun()
        
        if st.button("📝 智能批改", use_container_width=True):
            st.session_state.current_page = "grading"
            st.rerun()
        
        if st.button("🔗 API 演示", use_container_width=True):
            st.session_state.current_page = "api_demo"
            st.rerun()
    
    # 主内容区域
    if st.session_state.current_page == "dashboard":
        show_dashboard()
    elif st.session_state.current_page == "scanner":
        show_scanner_page()
    elif st.session_state.current_page == "grading":
        show_grading_page()
    elif st.session_state.current_page == "api_demo":
        show_api_demo_page()

def show_dashboard():
    """显示主仪表板"""
    st.markdown("## 📊 系统概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("扫描引擎", "运行中", "✅")
    
    with col2:
        st.metric("批改引擎", "就绪", "🚀")
    
    with col3:
        st.metric("API 状态", "99.9%", "+0.1%")
    
    with col4:
        st.metric("响应时间", "234ms", "-12ms")
    
    st.markdown("---")
    
    # 功能介绍
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📱 BookScan-AI 扫描引擎")
        st.info("""
        **核心功能**：
        - 🔍 4096×2160 高分辨率支持
        - 📖 智能书本双页识别  
        - ⚡ 18帧稳定性检测
        - 🎨 AI 图像优化
        """)
        
        if st.button("🚀 启动扫描引擎", use_container_width=True, type="primary"):
            st.session_state.current_page = "scanner"
            st.rerun()
    
    with col2:
        st.markdown("### 🎯 智能批改系统")
        st.info("""
        **核心功能**：
        - 🤖 LangGraph 工作流引擎
        - 👁️ Gemini Vision 文档分析
        - 📊 实时进度跟踪
        - 📈 详细批改报告
        """)
        
        if st.button("📝 开始智能批改", use_container_width=True, type="secondary"):
            st.session_state.current_page = "grading"
            st.rerun()

def show_scanner_page():
    """显示扫描页面"""
    st.markdown("# 📱 BookScan-AI 扫描引擎")
    
    try:
        # 导入 ai_correction 的扫描功能
        from functions.bookscan_integration import show_bookscan_scanner
        
        scanned_images, ready = show_bookscan_scanner()
        
        if ready and scanned_images:
            st.success(f"✅ 已扫描 {len(scanned_images)} 张图像，可以进行批改")
            if st.button("🎯 立即开始批改", type="primary"):
                st.session_state.current_page = "grading"
                st.rerun()
                
    except ImportError as e:
        st.error(f"❌ 扫描模块加载失败: {e}")
        st.info("请确保 ai_correction 目录中的依赖已正确安装")

def show_grading_page():
    """显示批改页面"""
    st.markdown("# 📝 智能批改系统")
    
    try:
        # 导入 ai_correction 的主应用
        import main as ai_correction_main
        
        # 运行 ai_correction 的批改功能
        st.info("正在加载完整的批改系统...")
        
        # 这里可以调用 ai_correction 的具体批改功能
        st.markdown("### 🔄 批改工作流")
        st.markdown("""
        1. **📤 上传文件** - 支持 PDF、图片等格式
        2. **📋 设置评分标准** - 上传评分标准文档
        3. **🤖 AI 分析** - 多模态 AI 引擎处理
        4. **📊 生成报告** - 详细批改结果
        """)
        
        if st.button("📂 进入完整批改系统", type="primary"):
            st.info("请直接运行 ai_correction/main.py 获得完整功能")
            
    except ImportError as e:
        st.error(f"❌ 批改模块加载失败: {e}")

def show_api_demo_page():
    """显示 API 演示页面"""
    st.markdown("# 🔗 API 集成演示")
    
    try:
        from functions.bookscan_integration import show_api_integration_demo
        show_api_integration_demo()
        
    except ImportError as e:
        st.error(f"❌ API 演示模块加载失败: {e}")

if __name__ == "__main__":
    main()