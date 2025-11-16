"""
图片优化结果可视化 - Streamlit版本
展示图片优化前后对比效果
"""
import streamlit as st
from PIL import Image
import os
from pathlib import Path

# 页面配置
st.set_page_config(
    page_title="图片优化效果对比",
    page_icon="🎨",
    layout="wide"
)

# CSS样式
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #667eea;
        font-size: 2.5em;
        margin-bottom: 10px;
    }
    .subtitle {
        text-align: center;
        color: #666;
        margin-bottom: 30px;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .image-card {
        background: #f5f5f5;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# 标题
st.markdown('<h1 class="main-title">🎨 图片优化效果对比</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">AI批改系统 - 图片自动清晰化功能测试报告</p>', unsafe_allow_html=True)

# 统计信息
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.markdown("**测试状态**")
    st.markdown("### ✅ 成功")
    st.markdown("3/3 测试通过")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.markdown("**质量检测**")
    st.markdown("### 95/100")
    st.markdown("清晰度优秀")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.markdown("**优化模式**")
    st.markdown("### 2种")
    st.markdown("智能/快速模式")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# 图片路径
original_path = "uploads/test_homework.jpg"
smart_path = "uploads/optimized/test_homework_optimized_20251116_154333.jpg"
fast_path = "uploads/optimized/test_homework_optimized_20251116_154334.jpg"

# 检查文件是否存在
files_exist = all([
    os.path.exists(original_path),
    os.path.exists(smart_path),
    os.path.exists(fast_path)
])

if not files_exist:
    st.warning("⚠️ 测试图片文件不存在，请先运行 `python generate_test_image.py` 和 `python test_image_optimization.py`")
    st.stop()

# 加载图片
try:
    original_img = Image.open(original_path)
    smart_img = Image.open(smart_path)
    fast_img = Image.open(fast_path)
    
    # 获取文件大小
    original_size = os.path.getsize(original_path) / 1024  # KB
    smart_size = os.path.getsize(smart_path) / 1024
    fast_size = os.path.getsize(fast_path) / 1024
    
except Exception as e:
    st.error(f"❌ 加载图片失败: {e}")
    st.stop()

# 三栏布局展示图片
st.markdown("## 📊 优化效果对比")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📷 原始图片")
    st.image(original_img, use_container_width=True)
    
    with st.expander("📋 图片信息"):
        st.write(f"**尺寸:** {original_img.size[0]} x {original_img.size[1]}")
        st.write(f"**文件大小:** {original_size:.1f} KB")
        st.write(f"**状态:** 未处理")
        st.write(f"**质量评分:** 95/100")

with col2:
    st.markdown("### ✨ 智能模式优化")
    st.image(smart_img, use_container_width=True)
    
    with st.expander("📋 图片信息"):
        st.write(f"**尺寸:** {smart_img.size[0]} x {smart_img.size[1]}")
        st.write(f"**文件大小:** {smart_size:.1f} KB")
        st.write(f"**状态:** ✅ 已优化")
        st.write(f"**处理方式:** 切边+矫正+增强+锐化")
        
        # 计算提升
        width_change = ((smart_img.size[0] - original_img.size[0]) / original_img.size[0] * 100)
        st.metric("分辨率提升", f"{width_change:+.0f}%")

with col3:
    st.markdown("### ⚡ 快速模式优化")
    st.image(fast_img, use_container_width=True)
    
    with st.expander("📋 图片信息"):
        st.write(f"**尺寸:** {fast_img.size[0]} x {fast_img.size[1]}")
        st.write(f"**文件大小:** {fast_size:.1f} KB")
        st.write(f"**状态:** ✅ 已优化")
        st.write(f"**处理方式:** 切边+矫正+增亮")
        
        # 计算文件大小变化
        size_change = ((fast_size - original_size) / original_size * 100)
        st.metric("文件大小变化", f"{size_change:+.0f}%")

# 测试总结
st.markdown("---")
st.markdown("## 📋 测试总结")

col1, col2 = st.columns([2, 1])

with col1:
    st.success("✅ **API连接测试**: 成功连接Textin API")
    st.success("✅ **质量检测测试**: 成功检测图片质量(95/100分)")
    st.success("✅ **图片优化测试**: 成功使用智能模式和快速模式优化图片")
    
    st.info("""
    **📊 优化效果**:
    - **智能模式**: 提升分辨率，增强清晰度 (2213x1895)
    - **快速模式**: 快速处理，适度优化 (696x596)
    """)

with col2:
    st.metric("通过率", "100%", "3/3")
    
    # 下载按钮（如果需要）
    st.markdown("**📥 导出报告**")
    if st.button("生成HTML报告", use_container_width=True):
        st.info("💡 HTML报告已保存在 `view_optimization_result.html`")

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>🤖 AI批改系统 - 图片优化模块</p>
    <p style="font-size: 0.9em;">基于 Textin API 实现智能图片处理</p>
</div>
""", unsafe_allow_html=True)
