#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI智能批改系统 - 简洁版
整合calling_api.py和main.py的所有功能，去除无意义空框
"""

import streamlit as st
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import time
import re
import logging

logger = logging.getLogger(__name__)

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 页面配置
st.set_page_config(
    page_title="AI智能批改系统",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 旧版API已废弃,使用LangGraph系统
API_AVAILABLE = False

# 导入LangGraph集成 - 使用新的多模态工作流
try:
    from functions.langgraph.simple_ui_helper import (
        show_langgraph_placeholder,
        show_simple_history,
        show_simple_statistics
    )
    from functions.langgraph_integration import LangGraphIntegration
    # ✨ 使用新的多模态协作工作流
    from functions.langgraph.workflow_multimodal import run_multimodal_grading, get_multimodal_workflow
    LANGGRAPH_AVAILABLE = True
    st.success("多模态AI批改系统已就绪 (深度协作架构)")
except ImportError as e:
    show_langgraph_placeholder = None  # 设置为None避免未绑定变量警告
    show_simple_history = None
    show_simple_statistics = None
    LANGGRAPH_AVAILABLE = False
    st.warning(f"LangGraph系统未就绪：{str(e)}")

# 导入进度相关模块
try:
    from functions.progress_ui import show_progress_page, show_progress_modal
    from functions.correction_service import get_correction_service
    PROGRESS_AVAILABLE = True
except ImportError as e:
    show_progress_page = None  # 设置为None避免未绑定变量警告
    show_progress_modal = None
    get_correction_service = None
    PROGRESS_AVAILABLE = False
    st.warning(f"进度模块未就绪：{str(e)}")

# 导入图片处理库
try:
    from PIL import Image
    import base64
    from io import BytesIO
    PREVIEW_AVAILABLE = True
except ImportError:
    Image = None  # 设置为None避免未绑定变量警告
    PREVIEW_AVAILABLE = False

# 支持的8个Agent阶段
AGENT_STAGES = [
    {"name": "编排协调", "progress": 5},
    {"name": "多模态输入", "progress": 10},
    {"name": "并行理解", "progress": 25},
    {"name": "学生识别", "progress": 35},
    {"name": "批次规划", "progress": 40},
    {"name": "生成压缩包", "progress": 50},
    {"name": "批改作业", "progress": 75},
    {"name": "结果聚合", "progress": 90},
    {"name": "完成", "progress": 100}
]

# 常量设置
DATA_FILE = Path("user_data.json")
UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = ['txt', 'md', 'pdf', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']

# 确保目录存在
UPLOAD_DIR.mkdir(exist_ok=True)

# 黑白纯色CSS样式
st.markdown("""
<style>
    .stApp {
        background-color: #ffffff;
        color: #000000;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }

    #MainMenu, .stDeployButton, footer, header {visibility: hidden;}

    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #000000;
        text-align: center;
        margin-bottom: 1rem;
    }

    .stButton > button {
        background-color: #000000;
        color: white !important;
        border: 2px solid #000000;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        background-color: #333333;
        border-color: #333333;
        transform: translateY(-2px);
    }

    .result-container {
        background-color: #f5f5f5;
        border: 2px solid #000000;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    /* 分栏布局样式 - 黑白纯色 */
    .split-container {
        display: flex;
        gap: 1.5rem;
        height: 80vh;
        margin-top: 1rem;
        padding: 0;
    }

    .left-panel, .right-panel {
        background-color: #ffffff;
        border: 2px solid #000000;
        border-radius: 8px;
        padding: 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        flex: 1;
        position: relative;
        overflow: hidden;
    }

    .panel-header {
        background-color: #f0f0f0;
        border-bottom: 2px solid #000000;
        padding: 1rem 1.5rem;
        font-weight: 600;
        font-size: 1.1rem;
        color: #000000;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-radius: 6px 6px 0 0;
    }

    .panel-content {
        height: calc(100% - 4rem);
        overflow-y: auto;
        overflow-x: hidden;
        padding: 1.5rem;
        position: relative;
        color: #000000;
    }
    
    /* 自定义滚动条样式 */
    .panel-content::-webkit-scrollbar {
        width: 8px;
    }

    .panel-content::-webkit-scrollbar-track {
        background-color: #f0f0f0;
        border-radius: 4px;
    }

    .panel-content::-webkit-scrollbar-thumb {
        background-color: #666666;
        border-radius: 4px;
        transition: all 0.3s ease;
    }

    .panel-content::-webkit-scrollbar-thumb:hover {
        background-color: #333333;
    }

    /* 文件预览容器 */
    .file-preview-inner {
        background-color: #f5f5f5;
        border: 2px solid #cccccc;
        border-radius: 8px;
        padding: 1rem;
        min-height: 200px;
    }

    /* 批改结果容器 */
    .correction-result-inner {
        background-color: #f5f5f5;
        border: 2px solid #cccccc;
        border-radius: 8px;
        padding: 1.5rem;
        min-height: 200px;
        font-family: 'Consolas', 'Monaco', monospace;
        line-height: 1.6;
        color: #000000;
    }

    /* 文件切换器增强样式 */
    .file-selector-container {
        background-color: #f0f0f0;
        border: 2px solid #cccccc;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    /* 鼠标悬停效果 */
    .left-panel:hover, .right-panel:hover {
        border-color: #000000;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transform: translateY(-2px);
        transition: all 0.3s ease;
    }

    /* 确保容器可以正确滚动 */
    .stSelectbox > div > div,
    .stTextArea > div > div > textarea {
        background-color: #ffffff !important;
        border: 2px solid #cccccc !important;
        color: #000000 !important;
    }

    /* 确保独立滚动 */
    .panel-content {
        scroll-behavior: smooth;
    }

    /* 增强焦点效果 */
    .panel-content:focus-within {
        outline: 2px solid #000000;
        outline-offset: -2px;
    }

    /* 文件预览图片样式 */
    .file-preview-inner img {
        max-width: 100%;
        height: auto;
        border-radius: 8px;
        border: 2px solid #cccccc;
        transition: transform 0.3s ease;
    }

    .file-preview-inner img:hover {
        transform: scale(1.02);
    }

    /* 批改结果文本样式优化 */
    .correction-result-inner pre {
        font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
        font-size: 0.9rem;
        line-height: 1.6;
        color: #000000;
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    /* 响应式设计 */
    @media (max-width: 768px) {
        .split-container {
            flex-direction: column;
            height: auto;
        }

        .left-panel, .right-panel {
            min-height: 400px;
        }

        .panel-content {
            height: 400px;
        }
    }

    .file-switcher {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
        flex-wrap: wrap;
    }

    .file-switcher button {
        background-color: #e8e8e8 !important;
        color: #000000 !important;
        border: 2px solid #cccccc !important;
        border-radius: 6px !important;
        padding: 0.5rem 1rem !important;
        font-size: 0.9rem !important;
        transition: all 0.3s ease !important;
    }

    .file-switcher button:hover,
    .file-switcher button.active {
        background-color: #cccccc !important;
        color: #000000 !important;
        border-color: #000000 !important;
    }

    .stTextInput > div > div > input,
    .stSelectbox > div > div {
        background-color: #ffffff !important;
        border: 2px solid #cccccc !important;
        border-radius: 8px !important;
        color: #000000 !important;
    }

    .css-1d391kg {
        background-color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# 文件预览功能
def get_file_type(file_name):
    """获取文件类型"""
    ext = Path(file_name).suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return 'image'
    elif ext == '.pdf':
        return 'pdf'
    elif ext in ['.txt', '.md']:
        return 'text'
    elif ext in ['.doc', '.docx']:
        return 'document'
    else:
        return 'unknown'

def get_image_base64(image_path):
    """将图片文件转换为base64编码"""
    import base64
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"图片base64转换失败: {e}")
        return None

def preview_file(file_path, file_name):
    """预览文件内容"""
    try:
        file_type = get_file_type(file_name)
        
        if file_type == 'image' and PREVIEW_AVAILABLE and Image is not None:
            try:
                image = Image.open(file_path)
                st.image(image, caption=file_name, use_column_width=True)
            except Exception as e:
                st.error(f"图片预览失败: {e}")
                
        elif file_type == 'text':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if len(content) > 5000:
                    content = content[:5000] + "\n...(内容过长，已截断)"
                st.text_area("文本内容", content, height=400, disabled=True)
            except Exception as e:
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                    if len(content) > 5000:
                        content = content[:5000] + "\n...(内容过长，已截断)"
                    st.text_area("文本内容", content, height=400, disabled=True)
                except Exception as e2:
                    st.error(f"文本预览失败: {e2}")
                    
        elif file_type == 'pdf':
            st.info(f"📄 PDF文件: {file_name}")
            st.write("PDF文件预览需要额外的库支持")
            
        elif file_type == 'document':
            st.info(f"📄 Word文档: {file_name}")
            st.write("Word文档预览需要额外的库支持")
            
        else:
            st.info(f"📄 文件: {file_name}")
            st.write("暂不支持此类型文件的预览")
            
    except Exception as e:
        st.error(f"文件预览失败: {e}")

# 初始化session state
def init_session():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'page' not in st.session_state:
        st.session_state.page = "home"
    if 'correction_result' not in st.session_state:
        st.session_state.correction_result = None
    if 'uploaded_files_data' not in st.session_state:
        st.session_state.uploaded_files_data = []
    if 'current_file_index' not in st.session_state:
        st.session_state.current_file_index = 0
    if 'correction_settings' not in st.session_state:
        st.session_state.correction_settings = {}
    if 'current_task_id' not in st.session_state:
        st.session_state.current_task_id = None

# 数据管理
def read_users():
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
        # 确保demo用户存在
        if "demo" not in data:
            data["demo"] = {
                "password": hashlib.sha256("demo".encode()).hexdigest(),
                "email": "demo@example.com",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "records": []
            }
            save_users(data)
        
        return data
    except:
        return {}

def save_users(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存失败: {e}")

def save_files(files, username):
    user_dir = UPLOAD_DIR / username
    user_dir.mkdir(exist_ok=True)
    
    saved_paths = []
    for file in files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = Path(file.name).suffix
        safe_name = re.sub(r'[^\w\-_.]', '_', Path(file.name).stem)
        filename = f"{timestamp}_{safe_name}{file_ext}"
        
        file_path = user_dir / filename
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        
        saved_paths.append(str(file_path))
    
    return saved_paths

# 主页面
def show_home():
    st.markdown('<h1 class="main-title">🤖 AI智能批改系统</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #94a3b8; font-size: 1.1rem;">AI赋能教育，智能批改新纪元</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 立即批改", use_container_width=True, type="primary"):
            if st.session_state.logged_in:
                st.session_state.page = "grading"
                st.rerun()
            else:
                st.session_state.page = "login"
                st.rerun()
    
    with col2:
        if st.button("📚 查看历史", use_container_width=True):
            if st.session_state.logged_in:
                st.session_state.page = "history"
                st.rerun()
            else:
                st.session_state.page = "login"
                st.rerun()
    
    with col3:
        if st.button("👤 用户中心", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()
    
    # 功能介绍
    st.markdown("---")
    st.markdown("### 💡 系统特色")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🎯 智能批改**")
        st.write("• 支持多种文件格式")
        st.write("• 智能识别内容")
        st.write("• 详细错误分析")
    
    with col2:
        st.markdown("**📊 多种模式**")
        st.write("• 高效模式：快速批改")
        st.write("• 详细模式：深度分析")
        st.write("• 批量模式：批量处理")
    
    with col3:
        st.markdown("**💎 增值功能**")
        st.write("• 自动生成评分标准")
        st.write("• 多语言支持")
        st.write("• 历史记录管理")

# 登录页面
def show_login():
    st.markdown('<h2 class="main-title">🔐 用户中心</h2>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("用户名", placeholder="输入用户名")
            password = st.text_input("密码", type="password", placeholder="输入密码")
            
            col1, col2 = st.columns(2)
            with col1:
                login_btn = st.form_submit_button("登录", use_container_width=True)
            with col2:
                demo_btn = st.form_submit_button("演示登录", use_container_width=True)
            
            if login_btn or demo_btn:
                if demo_btn:
                    username, password = "demo", "demo"
                
                if username and password:
                    users = read_users()
                    stored_pwd = users.get(username, {}).get('password')
                    input_pwd = hashlib.sha256(password.encode()).hexdigest()
                    
                    if stored_pwd == input_pwd:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.page = "grading"
                        st.success(f"欢迎，{username}！")
                        st.rerun()
                    else:
                        st.error("用户名或密码错误")
                else:
                    st.error("请输入用户名和密码")
        
        st.info("💡 演示账户：demo/demo")
    
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("用户名")
            new_email = st.text_input("邮箱")
            new_password = st.text_input("密码", type="password")
            confirm_password = st.text_input("确认密码", type="password")
            
            register_btn = st.form_submit_button("注册", use_container_width=True)
            
            if register_btn:
                if all([new_username, new_password, confirm_password]):
                    if new_password == confirm_password:
                        users = read_users()
                        if new_username not in users:
                            users[new_username] = {
                                "password": hashlib.sha256(new_password.encode()).hexdigest(),
                                "email": new_email or f"{new_username}@example.com",
                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "records": []
                            }
                            save_users(users)
                            st.success("注册成功！请登录")
                        else:
                            st.error("用户名已存在")
                    else:
                        st.error("密码不一致")
                else:
                    st.error("请填写所有必填字段")

# 批改页面 - 仅显示生产级AI批改
def show_grading():
    if not st.session_state.logged_in:
        st.warning("请先登录")
        st.session_state.page = "login"
        st.rerun()
        return

    # ✨ 使用新的多模态协作工作流
    if LANGGRAPH_AVAILABLE:
        st.markdown('<h2 class="main-title">AI智能批改</h2>', unsafe_allow_html=True)
        st.info("正在使用深度协作多模态架构 - 8个Agent协同工作")
        
        # 固定文件路径
        current_dir = Path(__file__).parent
        answer_pdf = current_dir / "学生作答.pdf"
        marking_pdf = current_dir / "批改标准.pdf"
        
        # 检查文件是否存在
        if not answer_pdf.exists():
            st.error(f"找不到学生作答文件: {answer_pdf}")
            st.info("请确保文件存在于项目根目录")
            return
        
        if not marking_pdf.exists():
            st.error(f"找不到批改标准文件: {marking_pdf}")
            st.info("请确保文件存在于项目根目录")
            return
        
        # 显示文件信息
        col1, col2 = st.columns(2)
        with col1:
            st.success(f"学生作答文件: {answer_pdf.name}")
        with col2:
            st.success(f"批改标准文件: {marking_pdf.name}")
        
        # 批改按钮
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("开始批改", type="primary", use_container_width=True):
                # 清除之前的结果
                if 'grading_result' in st.session_state:
                    del st.session_state.grading_result
                if 'just_completed_grading' in st.session_state:
                    del st.session_state.just_completed_grading
                run_grading_in_streamlit(str(answer_pdf), str(marking_pdf))

        with col_btn2:
            if st.button("📊 加载测试数据", use_container_width=True):
                # 加载测试数据用于验证显示功能
                test_result = {
                    'total_score': 15.5,
                    'status': 'completed',
                    'grade_level': 'B',
                    'criteria_evaluations': [
                        # Q1 的评分点
                        {
                            'criterion_id': 'Q1_C1',
                            'score_earned': 2.0,
                            'max_score': 2.0,
                            'satisfaction_level': '完全满足',
                            'student_work': '学生正确使用了余弦定理公式 cosA = (b²+c²-a²)/(2bc)',
                            'justification': '学生完全正确地应用了余弦定理，公式使用正确，计算过程清晰',
                            'matched_criterion': '正确使用余弦定理',
                            'feedback': '非常好！继续保持',
                            'evidence': ['cosA = (b²+c²-a²)/(2bc)', '计算结果正确']
                        },
                        {
                            'criterion_id': 'Q1_C2',
                            'score_earned': 1.5,
                            'max_score': 2.0,
                            'satisfaction_level': '部分满足',
                            'student_work': '学生计算了 cos(π/2) 的值，但结果有误',
                            'justification': '学生理解了特殊角的概念，但计算结果不正确',
                            'matched_criterion': '计算特殊角的三角函数值',
                            'feedback': '需要复习特殊角的三角函数值，cos(π/2) = 0',
                            'evidence': ['cos(π/2) 计算错误']
                        },
                        # Q2 的评分点
                        {
                            'criterion_id': 'Q2_C1',
                            'score_earned': 3.0,
                            'max_score': 3.0,
                            'satisfaction_level': '完全满足',
                            'student_work': '学生正确证明了三角形全等',
                            'justification': '证明过程完整，逻辑清晰，符合评分标准',
                            'matched_criterion': '证明三角形全等',
                            'feedback': '证明过程非常完整，逻辑严密',
                            'evidence': ['使用了SAS全等定理', '证明步骤完整']
                        },
                        {
                            'criterion_id': 'Q2_C2',
                            'score_earned': 2.0,
                            'max_score': 3.0,
                            'satisfaction_level': '部分满足',
                            'student_work': '学生计算了角度，但过程不够详细',
                            'justification': '结果正确，但缺少详细的推导过程',
                            'matched_criterion': '计算角度',
                            'feedback': '建议在计算过程中写出更详细的步骤',
                            'evidence': ['最终答案正确', '缺少中间步骤']
                        },
                        # Q3 的评分点
                        {
                            'criterion_id': 'Q3_C1',
                            'score_earned': 4.0,
                            'max_score': 4.0,
                            'satisfaction_level': '完全满足',
                            'student_work': '学生正确化简了代数分数',
                            'justification': '化简过程完全正确，符合所有评分标准',
                            'matched_criterion': '化简代数分数',
                            'feedback': '化简过程非常规范，值得表扬',
                            'evidence': ['指数运算正确', '最终结果正确']
                        },
                        {
                            'criterion_id': 'Q3_C2',
                            'score_earned': 3.0,
                            'max_score': 4.0,
                            'satisfaction_level': '部分满足',
                            'student_work': '学生进行了因式分解，但有一处小错误',
                            'justification': '整体思路正确，但在因式分解的最后一步出现了符号错误',
                            'matched_criterion': '因式分解',
                            'feedback': '注意检查符号，特别是在提取公因式时',
                            'evidence': ['因式分解思路正确', '符号错误扣1分']
                        }
                    ],
                    'detailed_feedback': [
                        {'content': '总体表现良好，基础知识掌握扎实'},
                        {'content': '在特殊角的三角函数值方面需要加强'},
                        {'content': '证明题的逻辑性很好，继续保持'},
                        {'content': '建议在计算过程中写出更详细的步骤'}
                    ],
                    'student_reports': [
                        {
                            'student_id': '20210001',
                            'student_name': '张三',
                            'total_score': 15.5,
                            'evaluations': []  # 将在下面填充
                        }
                    ]
                }

                # 将 criteria_evaluations 复制到 student_reports 中
                test_result['student_reports'][0]['evaluations'] = test_result['criteria_evaluations']

                # 保存到 session_state
                st.session_state.grading_result = test_result
                st.session_state.just_completed_grading = False  # 设置为 False，这样下面会显示结果
                st.success("✅ 测试数据已加载！")
        
        # 如果已有批改结果，显示结果（在按钮下方显示，避免重复）
        # 注意：结果会在run_grading_in_streamlit中显示，这里不需要重复显示
        # 但如果页面刷新，这里可以恢复显示
        if 'grading_result' in st.session_state and st.session_state.grading_result:
            # 检查是否刚刚完成批改（避免重复显示）
            if not st.session_state.get('just_completed_grading', False):
                display_grading_result(st.session_state.grading_result)
        
        # 显示架构亮点
        with st.expander("架构特性", expanded=False):
            st.markdown("""
            **深度协作机制**:
            - 无OCR依赖，直接使用LLM Vision能力
            - 基于学生的批次管理
            - Token优化：一次理解，多次使用
            - 并行处理，提升效率
            
            **8个Agent协作流程**:
            1. OrchestratorAgent - 编排协调
            2. MultiModalInputAgent - 多模态输入
            3. 并行理解 (Question/Answer/Rubric)
            4. StudentDetectionAgent - 学生识别
            5. BatchPlanningAgent - 批次规划
            6. RubricMasterAgent - 生成压缩评分包
            7. GradingWorkerAgent - 批改作业
            8. ResultAggregatorAgent - 结果聚合
            """)
    else:
        st.error("生产级批改系统未就绪，请检查系统配置")
        return


def run_grading_in_streamlit(answer_pdf: str, marking_pdf: str):
    """在Streamlit中运行批改流程，支持实时日志和进度显示"""
    import asyncio
    from functions.langgraph.workflow_multimodal import run_multimodal_grading
    from functions.langgraph.streamlit_logger import setup_streamlit_logger, get_streamlit_logs
    from datetime import datetime
    import time

    # 创建状态显示区域
    status_placeholder = st.empty()

    # 创建日志显示区域
    log_container = st.container()
    with log_container:
        st.markdown("### 📋 批改日志")
        log_code_area = st.empty()
        log_code_area.code("等待批改开始...", language='text')

    # 添加调试信息
    st.write("🔍 调试：日志区域已创建")

    # 设置日志处理器（简化版本，避免阻塞）
    try:
        st.write("🔍 调试：正在设置日志处理器...")
        # 暂时跳过日志处理器设置和logger调用，避免阻塞
        # log_handler = setup_streamlit_logger(log_container=None)
        # logger.info("开始批改流程（日志处理器已跳过）")
        st.write("🔍 调试：日志处理器设置已跳过，继续执行...")
    except Exception as e:
        # logger.error(f"设置日志处理器失败: {e}")
        st.error(f"⚠️ 日志处理器设置失败: {e}")
        st.write(f"🔍 调试：日志处理器设置失败 - {e}")

    # 进度回调函数（虽然由于asyncio.run()阻塞无法实时更新，但仍然记录日志）
    def progress_callback(state_dict, node_name):
        """进度回调函数 - 记录进度信息到日志"""
        try:
            progress = state_dict.get('progress_percentage', 0)
            current_step = state_dict.get('current_step', '处理中...')
            # logger.info(f"[进度 {progress:.1f}%] {current_step} (Agent: {node_name})")
            pass  # 暂时跳过logger调用
        except Exception as e:
            # logger.warning(f"进度回调失败: {e}")
            pass

    try:
        # 步骤1: 准备文件路径
        st.write("🔍 调试：开始准备文件路径...")
        # logger.info(f"开始批改流程，学生作答文件: {answer_pdf}, 批改标准文件: {marking_pdf}")

        # 检查文件是否存在（支持Path对象和字符串）
        answer_path = Path(answer_pdf) if isinstance(answer_pdf, str) else answer_pdf
        marking_path = Path(marking_pdf) if isinstance(marking_pdf, str) else marking_pdf

        st.write(f"🔍 调试：检查文件 - 学生作答: {answer_path}, 批改标准: {marking_path}")

        if not answer_path.exists():
            raise FileNotFoundError(f"学生作答文件不存在: {answer_path}")
        if not marking_path.exists():
            raise FileNotFoundError(f"批改标准文件不存在: {marking_path}")

        # 转换为字符串路径
        answer_pdf = str(answer_path)
        marking_pdf = str(marking_path)

        # logger.info("✅ 文件检查通过")
        st.write("🔍 调试：文件检查通过，准备启动批改工作流...")

        # 步骤2: 运行批改工作流
        st.write("🔍 调试：准备执行批改工作流...")

        # 直接执行批改，不使用 st.status()（避免可能的阻塞）
        try:
            st.write("🔍 调试：开始调用 asyncio.run()...")

            # 执行批改（注意：这会阻塞UI，但Streamlit的限制无法避免）
            # 设置超时时间（30分钟）
            try:
                result = asyncio.run(
                    asyncio.wait_for(
                        run_multimodal_grading(
                            task_id=f"streamlit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            user_id=st.session_state.get('user_id', 'streamlit_user'),
                            question_files=[],  # 题目文件（如果有）
                            answer_files=[answer_pdf],
                            marking_files=[marking_pdf],
                            strictness_level="中等",
                            language="zh",
                            progress_callback=progress_callback
                        ),
                        timeout=1800  # 30分钟超时
                    )
                )
            except asyncio.TimeoutError:
                raise TimeoutError("⏱️ 批改超时（超过30分钟），请检查文件大小或网络连接")

            st.write(f"🔍 调试：批改完成！状态: {result.get('status', 'unknown')}")

            if result is None:
                raise Exception("❌ 批改流程返回None，可能执行失败")

            # 验证结果完整性
            if not result.get('criteria_evaluations'):
                st.warning("⚠️ 批改结果中没有评估项，可能存在问题")

            st.success("✅ 批改完成！")

        except TimeoutError as timeout_err:
            error_msg = str(timeout_err)
            st.error(error_msg)
            # 显示已捕获的日志
            logs = get_streamlit_logs()
            if logs:
                recent_logs = logs[-200:]
                log_text = "\n".join([
                    f"[{log['timestamp']}] [{log['level']:7s}] {log['message']}"
                    for log in recent_logs
                ])
                log_code_area.code(f"批改超时\n\n已捕获的日志:\n{log_text}", language='text')
            return
        except Exception as workflow_error:
            error_msg = f"批改工作流执行失败: {str(workflow_error)}"
            st.error(error_msg)
            # 显示错误信息和已捕获的日志
            logs = get_streamlit_logs()
            if logs:
                recent_logs = logs[-200:]
                log_text = "\n".join([
                    f"[{log['timestamp']}] [{log['level']:7s}] {log['message']}"
                    for log in recent_logs
                ])
                log_code_area.code(f"错误: {error_msg}\n\n已捕获的日志:\n{log_text}", language='text')
            else:
                log_code_area.code(f"错误: {error_msg}\n\n未捕获到日志", language='text')
            raise

        # 显示完整日志
        logs = get_streamlit_logs()
        if logs:
            # 显示所有日志（最多500条）
            recent_logs = logs[-500:] if len(logs) > 500 else logs
            log_text = "\n".join([
                f"[{log['timestamp']}] [{log['level']:7s}] {log['message']}"
                for log in recent_logs
            ])
            log_code_area.code(log_text, language='text')
            # logger.info(f"📊 已显示 {len(recent_logs)} 条日志（共 {len(logs)} 条）")
            st.write(f"🔍 调试：已显示 {len(recent_logs)} 条日志（共 {len(logs)} 条）")
        else:
            log_code_area.code("⚠️ 未捕获到日志", language='text')
            # logger.warning("⚠️ 未捕获到任何日志")
            st.write("🔍 调试：未捕获到任何日志")

        # 保存结果到session_state
        st.session_state.grading_result = result
        st.session_state.just_completed_grading = True

        # 显示成功消息
        st.success("✅ 批改完成！结果已显示在下方。")

        # 显示结果
        display_grading_result(result)

    except Exception as e:
        # 记录错误
        # logger.error(f"❌ 批改过程异常: {e}", exc_info=True)

        # 确保错误信息可以正确编码
        try:
            error_msg = str(e).encode('utf-8', errors='replace').decode('utf-8')
        except Exception:
            error_msg = f"批改失败: {type(e).__name__}"

        st.error(f"❌ 批改失败: {error_msg}")

        # 显示错误详情
        import traceback
        error_traceback = traceback.format_exc()
        # logger.error(f"错误堆栈:\n{error_traceback}")
        st.write(f"🔍 调试：错误堆栈:\n{error_traceback}")

        with st.expander("🔍 错误详情", expanded=True):
            st.code(error_traceback)

        # 显示已捕获的日志
        logs = get_streamlit_logs()
        if logs:
            recent_logs = logs[-200:]
            log_text = "\n".join([
                f"[{log['timestamp']}] [{log['level']:7s}] {log['message']}"
                for log in recent_logs
            ])
            log_code_area.code(f"错误: {error_msg}\n\n已捕获的日志:\n{log_text}", language='text')
        else:
            log_code_area.code(f"错误: {error_msg}\n\n⚠️ 未捕获到日志", language='text')
            st.warning("⚠️ 未捕获到任何日志，可能日志处理器未正常工作")


def display_by_student(result: Dict):
    """按学生分组显示批改结果"""
    criteria_evaluations = result.get('criteria_evaluations', [])

    if not criteria_evaluations:
        st.warning("暂无详细批改数据")
        return

    st.markdown("### 👥 按学生分组显示")

    # 提取学生信息（从 student_reports 或 criteria_evaluations 中）
    student_reports = result.get('student_reports', [])

    if student_reports:
        # 如果有 student_reports，使用它
        for student_report in student_reports:
            student_id = student_report.get('student_id', 'unknown')
            student_name = student_report.get('student_name', '未知学生')
            total_score = student_report.get('total_score', 0)

            # 获取该学生的所有评估
            student_evals = student_report.get('evaluations', [])

            # 按题目分组
            questions = {}
            for eval_item in student_evals:
                criterion_id = eval_item.get('criterion_id', '')
                question_id = criterion_id.split('_')[0] if '_' in criterion_id else 'UNKNOWN'
                if question_id not in questions:
                    questions[question_id] = []
                questions[question_id].append(eval_item)

            # 显示学生信息
            with st.expander(f"👤 {student_name} ({student_id}) - 总分: {total_score}分", expanded=True):
                # 按题目显示
                sorted_questions = sorted(questions.items(), key=lambda x: x[0])

                for question_id, evals in sorted_questions:
                    # 计算该题得分
                    question_score = sum(e.get('score_earned', 0) for e in evals)
                    question_max_score = sum(e.get('max_score', 0) for e in evals)

                    # 使用可折叠的题目容器（支持缩放）
                    with st.expander(f"📝 {question_id} - {question_score}/{question_max_score}分", expanded=False):
                        # 显示该题的所有得分点
                        for i, eval_item in enumerate(evals, 1):
                            display_evaluation_item(eval_item, i)

                    st.markdown("---")
    else:
        # 如果没有 student_reports，尝试从 criteria_evaluations 中提取学生信息
        st.info("💡 当前批改结果中没有明确的学生分组信息，显示所有评分点")

        # 按题目分组显示（作为单个学生处理）
        questions = {}
        for eval_item in criteria_evaluations:
            criterion_id = eval_item.get('criterion_id', '')
            question_id = criterion_id.split('_')[0] if '_' in criterion_id else 'UNKNOWN'
            if question_id not in questions:
                questions[question_id] = []
            questions[question_id].append(eval_item)

        # 计算总分
        total_score = sum(e.get('score_earned', 0) for e in criteria_evaluations)
        max_score = sum(e.get('max_score', 0) for e in criteria_evaluations)

        with st.expander(f"👤 学生批改结果 - 总分: {total_score}/{max_score}分", expanded=True):
            sorted_questions = sorted(questions.items(), key=lambda x: x[0])

            for question_id, evals in sorted_questions:
                # 计算该题得分
                question_score = sum(e.get('score_earned', 0) for e in evals)
                question_max_score = sum(e.get('max_score', 0) for e in evals)

                st.markdown(f"#### 📝 {question_id} - {question_score}/{question_max_score}分")

                # 显示该题的所有得分点
                for i, eval_item in enumerate(evals, 1):
                    display_evaluation_item(eval_item, i)

                st.markdown("---")


def display_by_question(result: Dict):
    """按题目分组显示批改结果"""
    criteria_evaluations = result.get('criteria_evaluations', [])

    if not criteria_evaluations:
        st.warning("暂无详细批改数据")
        return

    st.markdown("### 📚 按题目分组显示")

    # 按题目分组
    questions = {}
    for eval_item in criteria_evaluations:
        criterion_id = eval_item.get('criterion_id', '')
        question_id = criterion_id.split('_')[0] if '_' in criterion_id else 'UNKNOWN'
        if question_id not in questions:
            questions[question_id] = []
        questions[question_id].append(eval_item)

    # 按题目顺序显示
    sorted_questions = sorted(questions.items(), key=lambda x: x[0])

    for question_id, evals in sorted_questions:
        # 计算该题统计信息
        question_score = sum(e.get('score_earned', 0) for e in evals)
        question_max_score = sum(e.get('max_score', 0) for e in evals)
        score_rate = (question_score / question_max_score * 100) if question_max_score > 0 else 0

        # 使用可折叠的题目容器（支持缩放），默认折叠
        with st.expander(f"📝 {question_id} - 共 {len(evals)} 个评分点 - 得分: {question_score}/{question_max_score}分 ({score_rate:.1f}%)", expanded=False):
            # 显示该题的所有得分点
            for i, eval_item in enumerate(evals, 1):
                display_evaluation_item(eval_item, i)

            # 显示该题统计信息
            st.markdown("---")
            st.markdown("#### 📊 该题统计")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总得分", f"{question_score:.1f}")
            with col2:
                st.metric("满分", f"{question_max_score:.1f}")
            with col3:
                st.metric("得分率", f"{score_rate:.1f}%")
            with col4:
                st.metric("评分点数", len(evals))


def display_evaluation_item(eval_item: Dict, index: int):
    """显示单个评分点的详细信息"""
    criterion_id = eval_item.get('criterion_id', 'N/A')
    score_earned = eval_item.get('score_earned', 0)
    max_score = eval_item.get('max_score', 0)
    satisfaction = eval_item.get('satisfaction_level', 'N/A')
    student_work = eval_item.get('student_work', '')
    justification = eval_item.get('justification', '')
    matched_criterion = eval_item.get('matched_criterion', '')
    feedback = eval_item.get('feedback', '')
    evidence = eval_item.get('evidence', [])

    # 根据满足程度选择颜色
    if satisfaction == '完全满足':
        satisfaction_color = '🟢'
    elif satisfaction == '部分满足':
        satisfaction_color = '🟡'
    else:
        satisfaction_color = '🔴'

    st.markdown(f"**{satisfaction_color} 评分点 {index}: {criterion_id}** - {score_earned}/{max_score}分 ({satisfaction})")

    # 使用列布局显示详细信息
    col1, col2 = st.columns([1, 1])

    with col1:
        # 学生作答情况
        if student_work:
            st.markdown("**✍️ 学生作答**:")
            st.text_area(f"学生作答_{index}", student_work, height=100, key=f"student_work_{criterion_id}_{index}", disabled=True, label_visibility="collapsed")

        # 符合评分标准的哪一项
        if matched_criterion:
            st.markdown(f"**✅ 符合标准**: {matched_criterion}")

    with col2:
        # 评分理由
        st.markdown("**📝 评分理由**:")
        st.text_area(f"评分理由_{index}", justification, height=100, key=f"justification_{criterion_id}_{index}", disabled=True, label_visibility="collapsed")

        # 反馈意见
        if feedback and feedback != "无":
            st.markdown("**💬 反馈意见**:")
            st.info(feedback)

    # 证据（具体步骤和结果）
    if evidence:
        st.markdown("**🔍 证据（具体步骤和结果）**:")
        for ev in evidence:
            st.write(f"- {ev}")

    st.markdown("---")


def display_grading_result(result: Dict):
    """显示批改结果（支持两种显示模式）"""
    if not result:
        st.warning("批改结果为空，无法显示")
        return

    st.markdown("---")
    st.markdown("## 📊 批改结果")

    # 总体信息
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("总分", f"{result.get('total_score', 0)}")
    with col2:
        st.metric("状态", result.get('status', 'N/A'))
    with col3:
        st.metric("等级", result.get('grade_level', 'N/A'))
    with col4:
        criteria_count = len(result.get('criteria_evaluations', []))
        st.metric("评分点数量", criteria_count)
    with col5:
        # 统计题目覆盖
        evals = result.get('criteria_evaluations', [])
        questions = set()
        for eval_item in evals:
            criterion_id = eval_item.get('criterion_id', '')
            if '_' in criterion_id:
                qid = criterion_id.split('_')[0]
                questions.add(qid)
        st.metric("题目数量", len(questions))

    # 显示模式切换
    st.markdown("---")
    display_mode = st.radio(
        "📋 选择显示模式",
        options=["按学生分组", "按题目分组"],
        horizontal=True,
        help="选择不同的显示方式来查看批改结果"
    )

    # 根据选择的模式显示结果
    if display_mode == "按学生分组":
        display_by_student(result)
    else:
        display_by_question(result)
    
    # 批改标准解析结果
    if 'rubric_parsing_result' in result and result['rubric_parsing_result']:
        st.markdown("### 批改标准解析结果")
        rubric_result = result['rubric_parsing_result']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**标准ID**: {rubric_result.get('rubric_id', 'N/A')}")
        with col2:
            st.write(f"**总分**: {rubric_result.get('total_points', 0)} 分")
        with col3:
            criteria_count = rubric_result.get('criteria_count', len(rubric_result.get('criteria', [])))
            st.write(f"**评分点数量**: {criteria_count}")
        
        # 统计题目覆盖
        criteria = rubric_result.get('criteria', [])
        if criteria:
            rubric_questions = set()
            for criterion in criteria:
                qid = criterion.get('question_id', '')
                if not qid and '_' in criterion.get('criterion_id', ''):
                    qid = criterion.get('criterion_id', '').split('_')[0]
                if qid:
                    rubric_questions.add(qid)
            if rubric_questions:
                st.write(f"**覆盖题目**: {len(rubric_questions)} 道题 - {', '.join(sorted(rubric_questions))}")
        
        # 评分点详情
        criteria = rubric_result.get('criteria', [])
        if criteria:
            with st.expander(f"查看所有评分点详情 ({len(criteria)}个)", expanded=False):
                for i, criterion in enumerate(criteria, 1):
                    st.markdown(f"#### 评分点 {i}: {criterion.get('criterion_id', 'N/A')}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**题目编号**: {criterion.get('question_id', 'N/A')}")
                        st.write(f"**分值**: {criterion.get('points', 0)} 分")
                        st.write(f"**评估方法**: {criterion.get('evaluation_method', 'N/A')}")
                    with col2:
                        if criterion.get('detailed_requirements'):
                            st.write(f"**详细要求**: {criterion.get('detailed_requirements')}")
                        if criterion.get('standard_answer'):
                            st.write(f"**标准答案**: {criterion.get('standard_answer')}")
                    
                    # 得分条件
                    scoring_criteria = criterion.get('scoring_criteria', {})
                    if scoring_criteria:
                        st.write("**得分条件**:")
                        if scoring_criteria.get('full_credit'):
                            st.write(f"- 满分: {scoring_criteria.get('full_credit')}")
                        if scoring_criteria.get('partial_credit'):
                            st.write(f"- 部分分: {scoring_criteria.get('partial_credit')}")
                        if scoring_criteria.get('no_credit'):
                            st.write(f"- 不得分: {scoring_criteria.get('no_credit')}")
                    
                    # 另类解法
                    if criterion.get('alternative_methods'):
                        st.write("**另类解法**:")
                        for method in criterion.get('alternative_methods', []):
                            st.write(f"- {method}")
                    
                    # 常见错误
                    if criterion.get('common_mistakes'):
                        st.write("**常见错误**:")
                        for mistake in criterion.get('common_mistakes', []):
                            st.write(f"- {mistake}")
                    
                    st.markdown("---")
    
    # Agent协作过程
    st.markdown("---")
    if 'agent_collaboration' in result:
        with st.expander("🤖 Agent协作过程", expanded=False):
            collab = result['agent_collaboration']

            col1, col2 = st.columns(2)
            with col1:
                st.write("**RubricInterpreterAgent**:")
                rubric_info = collab.get('rubric_interpreter', {})
                st.write(f"- 状态: {rubric_info.get('status', 'N/A')}")
                st.write(f"- 提取评分点数量: {rubric_info.get('criteria_extracted', 0)}")
                st.write(f"- 总分: {rubric_info.get('total_points', 0)} 分")

            with col2:
                st.write("**GradingWorkerAgent**:")
                grading_info = collab.get('grading_worker', {})
                st.write(f"- 状态: {grading_info.get('status', 'N/A')}")
                st.write(f"- 批改学生数量: {grading_info.get('students_graded', 0)}")
                st.write(f"- 评估数量: {grading_info.get('evaluations_count', 0)}")
    
    # 总体反馈
    if result.get('detailed_feedback'):
        st.markdown("### 💬 总体反馈")
        feedback_list = result.get('detailed_feedback', [])
        for i, feedback in enumerate(feedback_list, 1):
            if isinstance(feedback, dict):
                st.write(f"{i}. {feedback.get('content', str(feedback))}")
            else:
                st.write(f"{i}. {feedback}")
    
    # 错误和警告
    errors = result.get('errors', [])
    warnings = result.get('warnings', [])
    
    if errors or warnings:
        st.markdown("### ⚠️ 错误和警告")
        
        if errors:
            st.error("**错误**:")
            for i, error in enumerate(errors, 1):
                if isinstance(error, dict):
                    st.write(f"{i}. [{error.get('step', 'unknown')}] {error.get('error', str(error))}")
                else:
                    st.write(f"{i}. {error}")
        
        if warnings:
            st.warning("**警告**:")
            for i, warning in enumerate(warnings, 1):
                if isinstance(warning, dict):
                    st.write(f"{i}. [{warning.get('step', 'unknown')}] {warning.get('warning', str(warning))}")
                else:
                    st.write(f"{i}. {warning}")


# 批改结果展示页面 - 左右对照布局
def show_result():
    if not st.session_state.logged_in:
        st.warning("请先登录")
        st.session_state.page = "login"
        st.rerun()
        return
    
    if not st.session_state.correction_result or not st.session_state.uploaded_files_data:
        st.warning("没有批改结果数据")
        st.session_state.page = "grading"
        st.rerun()
        return
    
    st.markdown('<h2 class="main-title">📊 批改结果对照</h2>', unsafe_allow_html=True)
    
    # 顶部操作栏
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        settings = st.session_state.correction_settings
        st.markdown(f"**设置：** {settings.get('mode', 'N/A')} | {settings.get('strictness', 'N/A')} | {settings.get('language', 'zh')}")
    
    with col2:
        if st.button("🔄 重新批改"):
            st.session_state.page = "grading"
            st.rerun()
    
    with col3:
        filename = f"correction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button("💾 下载结果", 
                         data=st.session_state.correction_result, 
                         file_name=filename, 
                         mime="text/plain")
    
    with col4:
        if st.button("🏠 返回首页"):
            st.session_state.page = "home"
            st.rerun()
    
    st.markdown("---")
    
        # 使用Streamlit原生组件的简化版本
    # 创建左右两列
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("### 📁 文件预览")
        
        # 文件预览容器
        preview_container = st.container()
        
        with preview_container:
            if st.session_state.uploaded_files_data:
                # 确保索引在有效范围内
                if st.session_state.current_file_index >= len(st.session_state.uploaded_files_data):
                    st.session_state.current_file_index = 0
                
                current_file = st.session_state.uploaded_files_data[st.session_state.current_file_index]
                
                # 显示当前文件信息
                st.info(f"📄 **{current_file['name']}** ({current_file['type']})")
                
                # 文件预览 - 固定高度与批改结果区域一致
                if current_file['path'] and Path(current_file['path']).exists():
                    file_type = get_file_type(current_file['name'])
                    
                    if file_type == 'image':
                        try:
                            # 获取图片的base64编码
                            image_base64 = get_image_base64(current_file['path'])
                            if image_base64:
                                # 使用容器和CSS创建固定高度的图片预览区域
                                st.markdown(f"""
                                <div style="
                                    height: 500px; 
                                    overflow: auto; 
                                    border: 1px solid #404040;
                                    border-radius: 8px;
                                    padding: 10px;
                                    background-color: #262730;
                                    display: flex;
                                    justify-content: center;
                                    align-items: flex-start;
                                ">
                                    <img src="data:image/jpeg;base64,{image_base64}" 
                                         style="max-width: 100%; height: auto; object-fit: contain;" 
                                         alt="{current_file['name']}" />
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                raise Exception("图片base64转换失败")
                        except Exception as e:
                            # 如果base64转换失败，使用st.image但限制高度
                            try:
                                # 创建一个固定高度的容器来包含图片
                                with st.container():
                                    st.markdown("""
                                    <style>
                                    .fixed-height-image {
                                        height: 500px;
                                        overflow: auto;
                                        border: 1px solid #404040;
                                        border-radius: 8px;
                                        padding: 10px;
                                        background-color: #262730;
                                    }
                                    </style>
                                    """, unsafe_allow_html=True)
                                    
                                    st.markdown('<div class="fixed-height-image">', unsafe_allow_html=True)
                                    st.image(current_file['path'], caption=current_file['name'], width=400)
                                    st.markdown('</div>', unsafe_allow_html=True)
                            except Exception as e2:
                                st.error(f"📷 图片预览失败: {str(e2)}")
                    
                    elif file_type == 'text':
                        try:
                            with open(current_file['path'], 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            if len(content) > 5000:
                                content = content[:5000] + "\n\n...(内容已截断，可滚动查看)"
                            
                            # 使用st.text_area显示文本内容，高度与批改结果一致
                            st.text_area("文件内容", content, height=500, disabled=True, label_visibility="collapsed")
                            
                        except Exception as e:
                            st.error(f"📄 文本预览失败: {str(e)}")
                    
                    else:
                        # 为其他文件类型创建一个固定高度的信息容器
                        st.markdown(f"""
                        <div style="
                            height: 500px; 
                            overflow: auto; 
                            border: 1px solid #404040;
                            border-radius: 8px;
                            padding: 20px;
                            background-color: #262730;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            text-align: center;
                        ">
                            <h3>📄 {file_type.upper()} 文件</h3>
                            <p><strong>文件名:</strong> {current_file['name']}</p>
                            <p style="color: #94a3b8;">此文件类型暂不支持预览</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    # 为文件预览不可用创建一个固定高度的提示容器
                    warning_msg = "💡 历史记录，原始文件可能已被清理" if not current_file['path'] else "⚠️ 原始文件不存在"
                    st.markdown(f"""
                    <div style="
                        height: 500px; 
                        overflow: auto; 
                        border: 1px solid #404040;
                        border-radius: 8px;
                        padding: 20px;
                        background-color: #262730;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                        text-align: center;
                    ">
                        <h3 style="color: #f59e0b;">⚠️ 文件预览不可用</h3>
                        <p style="color: #94a3b8;">{warning_msg}</p>
                        <p style="color: #6b7280; font-size: 0.9rem;">文件名: {current_file['name']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                # 为没有可预览文件创建一个固定高度的提示容器
                st.markdown("""
                <div style="
                    height: 500px; 
                    overflow: auto; 
                    border: 1px solid #404040;
                    border-radius: 8px;
                    padding: 20px;
                    background-color: #262730;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    text-align: center;
                ">
                    <h3 style="color: #3b82f6;">📁 没有可预览的文件</h3>
                    <p style="color: #94a3b8;">请先上传文件进行批改</p>
                </div>
                """, unsafe_allow_html=True)
    
    with col_right:
        st.markdown("### 📝 批改结果")

        # 检查是否有LangGraph结果
        if hasattr(st.session_state, 'langgraph_result') and st.session_state.langgraph_result:
            # 显示LangGraph增强结果
            st.markdown("#### 🧠 LangGraph智能分析")

            # 显示LangGraph特殊结果（功能待实现）
            # if LANGGRAPH_AVAILABLE:
            #     show_langgraph_results(st.session_state.langgraph_result)
            st.info("📊 LangGraph结构化结果展示功能即将推出")

            # 显示传统文本结果
            with st.expander("📄 查看详细文本结果", expanded=False):
                st.text_area(
                    "批改详情",
                    st.session_state.correction_result,
                    height=300,
                    disabled=True,
                    label_visibility="collapsed"
                )
        else:
            # 传统结果显示
            result_container = st.container()

            with result_container:
                if st.session_state.correction_result:
                    # 使用st.text_area显示批改结果，避免HTML解析问题
                    st.text_area(
                        "批改详情",
                        st.session_state.correction_result,
                        height=500,
                        disabled=True,
                        label_visibility="collapsed"
                    )
                else:
                    st.info("没有批改结果")
    

    
    # 文件切换功能 (在HTML渲染后提供交互)
    if len(st.session_state.uploaded_files_data) > 1:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            file_options = []
            for i, file_data in enumerate(st.session_state.uploaded_files_data):
                file_name = file_data['name']
                if 'question' in file_name.lower() or '题目' in file_name:
                    label = f"📋 题目: {file_name}"
                elif 'answer' in file_name.lower() or '答案' in file_name or '作答' in file_name:
                    label = f"✏️ 学生作答: {file_name}"
                elif 'scheme' in file_name.lower() or 'marking' in file_name.lower() or '标准' in file_name:
                    label = f"📊 评分标准: {file_name}"
                else:
                    label = f"📄 文件{i+1}: {file_name}"
                file_options.append(label)
            
            new_selection = st.selectbox(
                "快速切换文件:",
                options=range(len(file_options)),
                format_func=lambda x: file_options[x],
                index=st.session_state.current_file_index,
                key="file_switcher"
            )
            
            if new_selection != st.session_state.current_file_index:
                st.session_state.current_file_index = new_selection
                st.rerun()

# 历史页面
def show_history():
    if not st.session_state.logged_in:
        st.warning("请先登录")
        st.session_state.page = "login"
        st.rerun()
        return
    
    st.markdown('<h2 class="main-title">📚 批改历史</h2>', unsafe_allow_html=True)
    
    users = read_users()
    records = users.get(st.session_state.username, {}).get('records', [])
    
    if not records:
        st.info("暂无批改记录")
        if st.button("🚀 开始批改", use_container_width=True):
            st.session_state.page = "grading"
            st.rerun()
        return
    
    # 统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总批改次数", len(records))
    with col2:
        total_files = sum(r.get('files_count', 0) for r in records)
        st.metric("处理文件数", total_files)
    with col3:
        if st.button("🗑️ 清空历史"):
            users[st.session_state.username]['records'] = []
            save_users(users)
            st.rerun()
    
    st.markdown("---")
    
    # 记录列表
    for i, record in enumerate(reversed(records), 1):
        with st.expander(f"📋 记录 {i} - {record['timestamp']}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**文件：** {', '.join(record.get('files', []))}")
                settings = record.get('settings', {})
                st.write(f"**设置：** {settings.get('mode', 'N/A')} | {settings.get('strictness', 'N/A')}")
                
                preview = record.get('result', '')[:200]
                if preview:
                    st.text_area("结果预览", preview + ("..." if len(record.get('result', '')) > 200 else ""), height=100, disabled=True)
            
            with col2:
                if st.button("👁️ 查看", key=f"view_{i}"):
                    st.session_state.correction_result = record.get('result', '')
                    # 尝试重建文件数据用于结果页面展示
                    file_names = record.get('files', [])
                    if file_names:
                        # 构建文件数据 - 注意：历史记录可能没有实际文件路径
                        st.session_state.uploaded_files_data = [
                            {'name': name, 'path': None, 'type': get_file_type(name)} 
                            for name in file_names
                        ]
                        st.session_state.correction_settings = record.get('settings', {})
                        # 重置文件索引到第一个文件
                        st.session_state.current_file_index = 0
                        st.session_state.page = "result"
                    else:
                        # 如果没有文件信息，回到批改页面
                        st.session_state.page = "grading"
                    st.rerun()
                
                if record.get('result'):
                    st.download_button(
                        "💾 下载",
                        data=record.get('result', ''),
                        file_name=f"record_{i}.txt",
                        mime="text/plain",
                        key=f"download_{i}"
                    )

# 侧边栏
def show_sidebar():
    with st.sidebar:
        st.markdown('<h3 style="color: #000000;">🤖 AI批改系统</h3>', unsafe_allow_html=True)

        if st.session_state.logged_in:
            st.markdown(f"👋 **{st.session_state.username}**")
            st.markdown("---")

            # 导航菜单
            if st.button("🏠 首页", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()

            if st.button("📝 批改", use_container_width=True):
                st.session_state.page = "grading"
                st.rerun()

            if st.button("📊 进度", use_container_width=True):
                st.session_state.page = "progress"
                st.rerun()

            if st.button("📚 历史", use_container_width=True):
                st.session_state.page = "history"
                st.rerun()

            # 结果页面导航 (只在有结果时显示)
            if st.session_state.correction_result:
                if st.button("� 查看结果", use_container_width=True):
                    st.session_state.page = "result"
                    st.rerun()
            
            st.markdown("---")
            
            # 统计信息
            users = read_users()
            count = len(users.get(st.session_state.username, {}).get('records', []))
            st.metric("批改次数", count)
            
            st.markdown("---")
            
            # 系统状态
            if API_AVAILABLE:
                st.success("✅ AI引擎正常")
            else:
                st.warning("⚠️ 演示模式")
            
            st.markdown("---")
            
            # 退出按钮
            if st.button("🚪 退出登录", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.correction_result = None
                st.session_state.page = "home"
                st.rerun()
        else:
            # 未登录状态
            if st.button("👤 登录", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()
            
            st.markdown("---")
            st.markdown("### 💡 功能特色")
            st.markdown("""
            - 🎯 智能批改
            - 📊 多种模式
            - 📚 历史管理
            - 💾 结果导出
            """)
            
            st.markdown("---")
            
            # 系统状态
            if API_AVAILABLE:
                st.success("✅ 系统就绪")
            else:
                st.warning("⚠️ 演示模式")

# 主函数
def main():
    init_session()
    show_sidebar()

    # 页面路由
    if st.session_state.page == "home":
        show_home()
    elif st.session_state.page == "login":
        show_login()
    elif st.session_state.page == "grading":
        show_grading()
    elif st.session_state.page == "progress":
        if PROGRESS_AVAILABLE and show_progress_page is not None:
            show_progress_page()
        else:
            st.error("❌ 进度模块不可用")
    elif st.session_state.page == "history":
        show_history()
    elif st.session_state.page == "result":
        show_result()
    else:
        show_home()

if __name__ == "__main__":
    main() 