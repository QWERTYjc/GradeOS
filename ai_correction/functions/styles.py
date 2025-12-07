
import streamlit as st
from contextlib import contextmanager

def load_custom_css():
    """
    加载前卫、大胆、冲突配色风格的自定义CSS
    包含丰富的动画和触碰反馈
    """
    st.markdown("""
    <style>
        /* === 字体引入 === */
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&family=Bangers&family=Press+Start+2P&display=swap');

        :root {
            /* === 赛博波普核心配色 === */
            --hot-pink: #FF0099;      /* 热粉色 */
            --electric-cyan: #00F0FF; /* 电光蓝 */
            --acid-yellow: #EAFF00;   /* 酸性黄 */
            --void-black: #050505;    /* 虚空黑 */
            --pure-white: #FFFFFF;
            
            /* === 设计变量 === */
            --border-width: 4px;
            --border-color: var(--void-black);
            --shadow-hard: 8px 8px 0px var(--void-black);
            --shadow-hover: 4px 4px 0px var(--void-black);
            --glitch-offset: 3px;
        }

        /* === 全局背景与基础 === */
        .stApp {
            background-color: var(--pure-white);
            color: var(--void-black);
            font-family: 'Space Grotesk', sans-serif;
            
            /* 漫画网点纹理 (Halftone) */
            background-image: 
                radial-gradient(var(--void-black) 15%, transparent 16%),
                radial-gradient(var(--void-black) 15%, transparent 16%);
            background-size: 20px 20px;
            background-position: 0 0, 10px 10px;
            opacity: 1;
        }
        
        /* 孟菲斯风格漂浮几何体 (使用伪元素模拟) */
        .stApp::before {
            content: "";
            position: fixed;
            top: 10%;
            left: 5%;
            width: 100px;
            height: 100px;
            background: var(--acid-yellow);
            border: var(--border-width) solid var(--void-black);
            transform: rotate(15deg);
            box-shadow: var(--shadow-hard);
            z-index: 0;
            pointer-events: none;
        }
        
        .stApp::after {
            content: "";
            position: fixed;
            bottom: 15%;
            right: 10%;
            width: 150px;
            height: 150px;
            background: var(--hot-pink);
            border-radius: 50%;
            border: var(--border-width) solid var(--void-black);
            box-shadow: -8px 8px 0px var(--electric-cyan);
            z-index: 0;
            pointer-events: none;
        }

        /* === 标题样式 (Manga Style) === */
        h1, h2, h3 {
            font-family: 'Bangers', cursive; /* 漫画字体 */
            text-transform: uppercase;
            color: var(--void-black);
            text-shadow: 4px 4px 0px var(--electric-cyan);
            letter-spacing: 2px;
            transform: skew(-5deg); /* 速度感倾斜 */
        }
        
        h1 {
            font-size: 4.5rem !important;
            -webkit-text-stroke: 2px var(--void-black);
            color: var(--pure-white) !important;
            text-shadow: 
                5px 5px 0px var(--hot-pink),
                10px 10px 0px var(--void-black);
        }

        /* === 按钮：叛逆交互 (Glitch & Bounce) === */
        .stButton > button {
            background-color: var(--pure-white);
            color: var(--void-black) !important;
            border: var(--border-width) solid var(--void-black);
            border-radius: 0px; /* 硬朗直角 */
            padding: 1rem 2rem;
            font-family: 'Press Start 2P', cursive; /* 像素风格字体 */
            font-size: 0.9rem;
            box-shadow: var(--shadow-hard);
            transition: all 0.1s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
        }

        /* 按钮 Hover: 剧烈回弹 + 颜色错位 */
        .stButton > button:hover {
            transform: translate(-4px, -4px);
            box-shadow: 12px 12px 0px var(--hot-pink);
            background-color: var(--acid-yellow);
            color: var(--void-black) !important;
        }

        /* 按钮 Active: 按压感 */
        .stButton > button:active {
            transform: translate(4px, 4px);
            box-shadow: 0px 0px 0px var(--void-black);
        }

        /* Primary 按钮特殊样式 */
        div[data-testid="stButton"] button[kind="primary"] {
            background-color: var(--hot-pink);
            color: var(--pure-white) !important;
            text-shadow: 2px 2px 0px var(--void-black);
        }
        
        div[data-testid="stButton"] button[kind="primary"]:hover {
            background-color: var(--electric-cyan);
            box-shadow: 12px 12px 0px var(--acid-yellow);
            color: var(--void-black) !important;
            text-shadow: none;
        }

        /* === 容器与卡片 (Manga Panels) === */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border: var(--border-width) solid var(--void-black) !important;
            border-radius: 0px !important; /* 漫画分镜框 */
            background-color: var(--pure-white);
            box-shadow: var(--shadow-hard);
            padding: 20px !important;
            margin-bottom: 20px;
            transition: transform 0.2s;
        }
        
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: rotate(-1deg) scale(1.01); /* 微微失衡的动感 */
            box-shadow: 12px 12px 0px var(--electric-cyan);
            z-index: 10;
        }

        /* === 输入框 === */
        .stTextInput > div > div > input {
            border: var(--border-width) solid var(--void-black) !important;
            border-radius: 0px !important;
            background-color: var(--pure-white);
            font-family: 'Space Grotesk', monospace;
            font-weight: bold;
            box-shadow: 4px 4px 0px rgba(0,0,0,0.2);
        }
        
        .stTextInput > div > div > input:focus {
            background-color: var(--acid-yellow);
            box-shadow: 8px 8px 0px var(--hot-pink);
            transform: scale(1.02);
        }

        /* === 进度条 === */
        .stProgress > div > div > div > div {
            background-color: var(--electric-cyan);
            border: 2px solid var(--void-black);
        }

        /* === 动画：故障效果 (Glitch) === */
        @keyframes glitch-skew {
            0% { transform: skew(0deg); }
            20% { transform: skew(-10deg); }
            40% { transform: skew(10deg); }
            60% { transform: skew(-5deg); }
            80% { transform: skew(5deg); }
            100% { transform: skew(0deg); }
        }

        .hero-title:hover {
            animation: glitch-skew 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94) both infinite;
            color: var(--hot-pink);
        }
        
        /* === 速度线背景 (Speed Lines) - 可选类 === */
        .speed-lines {
            background: repeating-linear-gradient(
                90deg,
                transparent,
                transparent 50px,
                rgba(0, 0, 0, 0.1) 50px,
                rgba(0, 0, 0, 0.1) 52px
            );
        }

    </style>
    """, unsafe_allow_html=True)

@contextmanager
def neo_card_container(color_class=""):
    """
    使用 Streamlit 原生容器配合 CSS 实现卡片效果
    color_class 参数暂时保留接口但无法直接传给 container，
    后续可通过特定的 key 或 CSS 选择器 hack 实现不同颜色。
    """
    # 使用 border=True 创建一个可被 CSS 选中的容器
    with st.container(border=True):
        yield

def animated_title(title, subtitle=""):
    """渲染带动画的标题"""
    html = f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <div class="hero-title">{title}</div>
    """
    if subtitle:
        html += f"""<br><div class="hero-subtitle">{subtitle}</div>"""
    
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
