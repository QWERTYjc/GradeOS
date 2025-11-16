"""
单张图片优化结果展示
"""
import streamlit as st
from PIL import Image
import os
from pathlib import Path
import glob

# 页面配置
st.set_page_config(
    page_title="图片优化演示",
    page_icon="✨",
    layout="wide"
)

st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #667eea;
        font-size: 2.5em;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">✨ 图片智能优化演示</h1>', unsafe_allow_html=True)

# 查找最新的优化图片
optimized_dir = "uploads/optimized"
if os.path.exists(optimized_dir):
    optimized_files = sorted(glob.glob(f"{optimized_dir}/*.jpg"), key=os.path.getmtime, reverse=True)
    
    if optimized_files:
        # 使用最新的优化图片
        latest_optimized = optimized_files[0]
        
        # 尝试找到原图
        original_name = Path(latest_optimized).stem.replace('_optimized_' + Path(latest_optimized).stem.split('_optimized_')[-1], '')
        
        st.success(f"✅ 找到优化图片: {Path(latest_optimized).name}")
        
        # 显示结果
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📷 原始图片")
            original_path = r"D:\微信图片_20251116164359_54_7.jpg"
            original_size = 0.0
            
            if os.path.exists(original_path):
                try:
                    original_img = Image.open(original_path)
                    st.image(original_img, width=600)
                    
                    original_size = os.path.getsize(original_path) / 1024
                    st.info(f"""
                    **原图信息:**
                    - 尺寸: {original_img.size[0]} x {original_img.size[1]}
                    - 文件大小: {original_size:.1f} KB
                    """)
                except Exception as e:
                    st.error(f"无法加载原图: {e}")
            else:
                st.warning("原图文件不存在")
        
        with col2:
            st.markdown("### ✨ 优化后图片")
            
            try:
                optimized_img = Image.open(latest_optimized)
                st.image(optimized_img, width=600)
                
                optimized_size = os.path.getsize(latest_optimized) / 1024
                
                st.success(f"""
                **优化结果:**
                - 尺寸: {optimized_img.size[0]} x {optimized_img.size[1]}
                - 文件大小: {optimized_size:.1f} KB
                - 处理方式: 切边+矫正+增强+锐化
                """)
                
                # 计算改进
                if os.path.exists(original_path):
                    size_reduction = ((original_size - optimized_size) / original_size * 100)
                    st.metric("文件大小减少", f"{size_reduction:.0f}%")
                
            except Exception as e:
                st.error(f"无法加载优化图: {e}")
        
        # 下载按钮
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            with open(latest_optimized, "rb") as file:
                st.download_button(
                    label="📥 下载优化图片",
                    data=file,
                    file_name=Path(latest_optimized).name,
                    mime="image/jpeg",
                    use_container_width=True
                )
        
    else:
        st.warning("⚠️ 未找到优化图片，请先运行 `python demo_single_image.py`")
else:
    st.error("❌ 优化目录不存在")

# 使用说明
with st.expander("💡 使用说明"):
    st.markdown("""
    ### 如何使用图片优化功能：
    
    1. **优化图片**
       ```bash
       python demo_single_image.py
       ```
       
    2. **查看结果**
       ```bash
       streamlit run demo_view.py --server.port 8503
       ```
       
    3. **功能特性**
       - ✅ 智能切边去背景
       - ✅ 自动矫正倾斜
       - ✅ 图像增强和锐化
       - ✅ 文件大小优化
    """)
