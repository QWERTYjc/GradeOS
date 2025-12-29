#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI智能批改系统 - Neo Brutalism Design
前卫、大胆冲突配色、丰富动画、触碰反馈
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

from utils.question_scope import parse_question_scope, QuestionScopeError, format_question_list

# 加载环境变量 - 确保在导入 config 之前加载
from dotenv import load_dotenv
from pathlib import Path

# 优先加载 ai_correction/.env，然后是父目录的 .env
env_file = Path(__file__).parent / '.env'
parent_env = Path(__file__).parent.parent / '.env'

if env_file.exists():
    load_dotenv(env_file, override=True)
elif parent_env.exists():
    load_dotenv(parent_env, override=True)
else:
    load_dotenv(override=True)

# 页面配置
st.set_page_config(
    page_title="AI GURU | 智能批改",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 导入自定义样式
try:
    from functions.styles import load_custom_css, neo_card_container, animated_title
except ImportError:
    # Fallback if not found (during dev)
    def load_custom_css(): pass
    from contextlib import contextmanager
    @contextmanager
    def neo_card_container(c=""): 
        st.markdown("---")
        yield
        st.markdown("---")
    def animated_title(t, s=""): st.title(t); st.caption(s)

# 加载自定义CSS
load_custom_css()

logger = logging.getLogger(__name__)

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
except ImportError as e:
    show_langgraph_placeholder = None
    show_simple_history = None
    show_simple_statistics = None
    LANGGRAPH_AVAILABLE = False
    # st.warning(f"LangGraph系统未就绪：{str(e)}")

# 导入进度相关模块
try:
    from functions.progress_ui import show_progress_page, show_progress_modal
    from functions.correction_service import get_correction_service
    PROGRESS_AVAILABLE = True
except ImportError as e:
    show_progress_page = None
    show_progress_modal = None
    get_correction_service = None
    PROGRESS_AVAILABLE = False

# 导入图片处理库
try:
    from PIL import Image
    import base64
    from io import BytesIO
    PREVIEW_AVAILABLE = True
except ImportError:
    Image = None
    PREVIEW_AVAILABLE = False

# 导入图片优化模块
try:
    from functions.image_optimization_integration import (
        ImageOptimizationIntegration,
        process_uploaded_images,
        OPTIMIZATION_AVAILABLE,
        render_optimization_settings,
        init_image_optimization
    )
    if OPTIMIZATION_AVAILABLE:
        from functions.image_optimization import OptimizationSettings
except ImportError as e:
    OPTIMIZATION_AVAILABLE = False
    process_uploaded_images = None
    render_optimization_settings = None
    init_image_optimization = None
    logger.warning(f"图片优化模块加载失败: {e}")

# 导入 Bookscan 集成模块
try:
    from functions.bookscan_integration import (
        show_bookscan_scanner,
        show_api_integration_demo,
        BookScanIntegration
    )
    BOOKSCAN_AVAILABLE = True
except ImportError as e:
    BOOKSCAN_AVAILABLE = False
    show_bookscan_scanner = None
    show_api_integration_demo = None
    logger.warning(f"Bookscan 集成模块加载失败: {e}")

# 常量设置
DATA_FILE = Path("user_data.json")
UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = ['txt', 'md', 'pdf', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']

# 确保目录存在
UPLOAD_DIR.mkdir(exist_ok=True)

# === 辅助函数 ===

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
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"图片base64转换失败: {e}")
        return None

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
    # 新增：批改结果页面状态
    if 'current_view' not in st.session_state:
        st.session_state.current_view = "grading"  # "grading" 或 "result"
    if 'grading_result' not in st.session_state:
        st.session_state.grading_result = None
    if 'uploaded_file_paths' not in st.session_state:
        st.session_state.uploaded_file_paths = {}
    if 'question_scope' not in st.session_state:
        st.session_state.question_scope = {
            'raw': '',
            'questions': [],
            'normalized': '',
            'warnings': []
        }
    if 'question_scope_error' not in st.session_state:
        st.session_state.question_scope_error = None
    if 'selected_question_scope' not in st.session_state:
        st.session_state.selected_question_scope = {}

# 数据管理 (保持原逻辑)
def read_users():
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
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

# === 页面显示函数 ===

def show_home():
    # 动态标题
    animated_title("AI GURU", "NEXT GEN GRADING SYSTEM")
    
    # 主要行动区
    with neo_card_container("blue-shadow"):
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown("""
            ### 🚀 重新定义批改体验
            
            不再是枯燥的红笔圈画，而是**全维度的智能洞察**。
            
            - **多模态理解**: 无论是手写图片还是PDF文档。
            - **深度思维链**: 像专家一样分析解题步骤。
            - **极速反馈**: 秒级生成详细的评估报告。
            """)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("⚡ START GRADING NOW / 立即开始", use_container_width=True, type="primary"):
                st.session_state.page = "grading" if st.session_state.logged_in else "login"
                st.rerun()
    
    with col2:
            # 右侧放一个装饰性元素或统计
            st.markdown("""
            <div style="text-align: center; padding: 20px; border: var(--border-width) solid var(--void-black); border-radius: 50%; width: 200px; height: 200px; margin: 0 auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: var(--acid-yellow); box-shadow: var(--shadow-hard); animation: float 3s ease-in-out infinite;">
                <div style="font-size: 3rem; font-weight: 900; color: var(--void-black);">100%</div>
                <div style="font-weight: bold; color: var(--void-black);">AI POWERED</div>
            </div>
            """, unsafe_allow_html=True)

    # 功能卡片网格
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with neo_card_container():
            st.markdown("#### 🎯 精准识别")
            st.markdown("突破OCR限制，直接理解视觉信息。哪怕是潦草的手写体，也能通过上下文精准还原。")
            st.progress(95)
    
    with col2:
        with neo_card_container("green-shadow"):
            st.markdown("#### 🧠 深度推理")
            st.markdown("不仅仅是核对答案。系统会分析学生的解题逻辑，指出思维误区，提供针对性建议。")
            st.progress(88)
    
    with col3:
        with neo_card_container():
            st.markdown("#### 📊 数据洞察")
            st.markdown("自动生成班级学情分析报告，识别知识薄弱点，辅助教学决策。")
            st.progress(92)

    # 底部栏
    if st.button("👥 用户中心 / LOGIN", use_container_width=True):
        st.session_state.page = "login"
        st.rerun()

def show_login():
    animated_title("ACCESS CONTROL", "USER AUTHENTICATION")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with neo_card_container("blue-shadow"):
            tab1, tab2 = st.tabs(["LOGIN / 登录", "REGISTER / 注册"])
    
    with tab1:
        st.markdown("#### WELCOME BACK")
        with st.form("login_form"):
            username = st.text_input("USERNAME", placeholder="Enter your username")
            password = st.text_input("PASSWORD", type="password", placeholder="Enter your password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                login_btn = st.form_submit_button("🔓 ENTER SYSTEM", use_container_width=True, type="primary")
            with c2:
                demo_btn = st.form_submit_button("⚡ DEMO MODE", use_container_width=True)
        
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
                    st.success(f"ACCESS GRANTED: {username}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("ACCESS DENIED: Invalid credentials")
            else:
                st.warning("INPUT REQUIRED")
    
    with tab2:
        st.markdown("#### NEW USER")
        with st.form("register_form"):
            new_username = st.text_input("CHOOSE USERNAME")
            new_email = st.text_input("EMAIL ADDRESS")
            new_password = st.text_input("SET PASSWORD", type="password")
            confirm_password = st.text_input("CONFIRM PASSWORD", type="password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            submit_btn = st.form_submit_button("📝 CREATE ACCOUNT", use_container_width=True)
        
        if submit_btn:
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
                        st.success("REGISTRATION SUCCESSFUL")
                    else:
                        st.error("USERNAME TAKEN")
                else:
                    st.error("PASSWORD MISMATCH")
            else:
                st.error("MISSING FIELDS")

def show_grading():
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.rerun()
        return

    # 检查是否应该显示结果页面
    if st.session_state.current_view == "result":
        show_result_page()
        return

    # 初始化图片优化
    if OPTIMIZATION_AVAILABLE and init_image_optimization:
        init_image_optimization()
        # 确保默认启用优化
        if st.session_state.get('optimization_settings') is None:
            st.session_state.optimization_settings = OptimizationSettings(
                enable_optimization=True,
                auto_optimize=True
            )
            st.session_state.optimization_enabled = True

    # 显示批改设置页面
    animated_title("GRADING STATION", "AI AGENT WORKFLOW")

    if LANGGRAPH_AVAILABLE:
        st.markdown("""
        <div style="background: var(--acid-yellow); padding: 10px; border: var(--border-width) solid var(--void-black); text-align: center; font-weight: bold; margin-bottom: 20px; box-shadow: var(--shadow-hover); color: var(--void-black);">
            🚀 CORE ENGINE: MULTI-MODAL AGENT SWARM ACTIVATED
        </div>
        """, unsafe_allow_html=True)

        current_dir = Path(__file__).parent
        answer_pdf = current_dir / "学生作答.pdf"
        marking_pdf = current_dir / "批改标准.pdf"

        # 三大上传区：题目、答卷、标准
        final_question_files = []
        final_answer_files = []
        final_rubric_files = []

        # === 上传区布局 ===
        st.markdown("### 📤 FILE UPLOAD ZONE / 文件上传区")
        
        # --- 1. 题目上传（可选）---
        with neo_card_container():
            st.markdown("#### 📋 1. Question Files / 题目文件 (Optional)")
            st.caption("支持多张图片或 PDF，非必填项")
            
            uploaded_questions = st.file_uploader(
                "Drop question files here", 
                type=['jpg', 'jpeg', 'png', 'webp', 'pdf'], 
                accept_multiple_files=True,
                key="question_uploader",
                label_visibility="collapsed"
            )

            if uploaded_questions:
                saved_paths = []
                for idx, file in enumerate(uploaded_questions):
                    # 使用英文文件名避免编码问题
                    ext = Path(file.name).suffix
                    safe_name = f"question_{idx+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    save_path = UPLOAD_DIR / safe_name
                    with open(save_path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_paths.append(str(save_path))
                    logger.info(f"题目文件已保存: {file.name} -> {safe_name}")
                
                # 自动优化
                if OPTIMIZATION_AVAILABLE and process_uploaded_images:
                    with st.expander("🔍 Image Enhancement", expanded=False):
                        final_question_files = process_uploaded_images(uploaded_questions, saved_paths)
                else:
                    final_question_files = saved_paths
                
                st.success(f"✅ Loaded {len(final_question_files)} question file(s)")
            else:
                st.info("💡 题目文件为可选项，可留空")

        # --- 2. 学生答卷（必填）---
        with neo_card_container("blue-shadow"):
            st.markdown("#### ✍️ 2. Student Answer / 学生答卷 (Required)")
            st.caption("支持多张图片或 PDF，**必填**")
            
            uploaded_answers = st.file_uploader(
                "Drop answer sheets here", 
                type=['jpg', 'jpeg', 'png', 'webp', 'pdf'], 
                accept_multiple_files=True,
                key="answer_uploader",
                label_visibility="collapsed"
            )

            if uploaded_answers:
                saved_paths = []
                for idx, file in enumerate(uploaded_answers):
                    # 使用英文文件名避免编码问题
                    ext = Path(file.name).suffix
                    safe_name = f"answer_{idx+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    save_path = UPLOAD_DIR / safe_name
                    with open(save_path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_paths.append(str(save_path))
                    logger.info(f"答卷文件已保存: {file.name} -> {safe_name}")
                
                # 自动优化
                if OPTIMIZATION_AVAILABLE and process_uploaded_images:
                    with st.expander("🔍 Image Enhancement", expanded=False):
                        final_answer_files = process_uploaded_images(uploaded_answers, saved_paths)
                else:
                    final_answer_files = saved_paths
                
                st.success(f"✅ Loaded {len(final_answer_files)} answer file(s)")
            
            # Fallback to local file if no upload
            elif answer_pdf.exists():
                st.info(f"📁 Using local file: {answer_pdf.name}")
                final_answer_files = [str(answer_pdf)]
            else:
                st.warning("⚠️ Please upload student answer files")

        # --- 3. 评分标准（必填）---
        with neo_card_container("green-shadow"):
            st.markdown("#### 📊 3. Grading Rubric / 评分标准 (Required)")
            st.caption("支持多张图片或 PDF，**必填**")
            
            uploaded_rubrics = st.file_uploader(
                "Drop rubric files here", 
                type=['jpg', 'jpeg', 'png', 'webp', 'pdf'], 
                accept_multiple_files=True,
                key="rubric_uploader",
                label_visibility="collapsed"
            )

            if uploaded_rubrics:
                saved_paths = []
                for idx, file in enumerate(uploaded_rubrics):
                    # 使用英文文件名避免编码问题
                    ext = Path(file.name).suffix
                    safe_name = f"rubric_{idx+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    save_path = UPLOAD_DIR / safe_name
                    with open(save_path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_paths.append(str(save_path))
                    logger.info(f"评分标准文件已保存: {file.name} -> {safe_name}")
                
                # 自动优化
                if OPTIMIZATION_AVAILABLE and process_uploaded_images:
                    with st.expander("🔍 Image Enhancement", expanded=False):
                        final_rubric_files = process_uploaded_images(uploaded_rubrics, saved_paths)
                else:
                    final_rubric_files = saved_paths
                
                st.success(f"✅ Loaded {len(final_rubric_files)} rubric file(s)")
            
            # Fallback to local file if no upload
            elif marking_pdf.exists():
                st.info(f"📁 Using local file: {marking_pdf.name}")
                final_rubric_files = [str(marking_pdf)]
            else:
                st.warning("⚠️ Please upload grading rubric files")

        # === 控制区 ===
        st.markdown("---")
        with neo_card_container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("#### 🎮 READY TO START?")
                # 文件状态摘要
                status_cols = st.columns(3)
                with status_cols[0]:
                    q_status = "✅" if final_question_files else "➖"
                    st.caption(f"{q_status} Questions: {len(final_question_files)} (Optional)")
                with status_cols[1]:
                    a_status = "✅" if final_answer_files else "❌"
                    st.caption(f"{a_status} Answers: {len(final_answer_files)} (Required)")
                with status_cols[2]:
                    r_status = "✅" if final_rubric_files else "❌"
                    st.caption(f"{r_status} Rubrics: {len(final_rubric_files)} (Required)")
            
            with col2:
                # 优化设置入口 (Optional)
                if OPTIMIZATION_AVAILABLE and render_optimization_settings:
                    if st.button("⚙️ Settings", use_container_width=True):
                        st.session_state.show_optimization_settings = not st.session_state.get('show_optimization_settings', False)
        
        if st.session_state.get('show_optimization_settings', False):
            with st.expander("⚙️ Optimization Settings", expanded=True):
                if render_optimization_settings:
                    render_optimization_settings()
        
        st.markdown("<br>", unsafe_allow_html=True)

        with neo_card_container("pink-shadow"):
            st.markdown("#### 🎯 Question Scope / 批改题号范围")
            scope_placeholder = "例如 3,5-8,12"
            scope_input = st.text_input(
                "可选：仅批改指定题号（使用逗号或区间）",
                value=st.session_state.question_scope.get('raw', ''),
                placeholder=scope_placeholder,
                key="question_scope_input",
                help="留空则默认批改整份试卷。支持输入格式：3,5-8,12 或 Q1,Q3,Q5-Q7。"
            )

            scope_validation_error = None
            scope_result = None
            scope_input_clean = scope_input.strip()

            if scope_input_clean:
                try:
                    scope_result = parse_question_scope(scope_input_clean)
                    st.success(f"将优先批改 {len(scope_result.question_ids)} 道题：{format_question_list(scope_result.question_ids)}")
                    if scope_result.warnings:
                        for warn in scope_result.warnings:
                            st.info(f"⚠️ {warn}")
                except QuestionScopeError as exc:
                    scope_validation_error = str(exc)
                    st.error(f"❌ 题号范围无效：{scope_validation_error}")
            else:
                st.caption("未输入范围，将自动批改整份试卷。")

            st.session_state.question_scope = {
                'raw': scope_input,
                'questions': scope_result.question_ids if scope_result else [],
                'normalized': scope_result.normalized_expression if scope_result else '',
                'warnings': scope_result.warnings if scope_result else []
            }
            st.session_state.question_scope_error = scope_validation_error
        
        start_btn = st.button("🚀 INITIATE GRADING SEQUENCE", type="primary", use_container_width=True)
        
        if start_btn:
            # 验证必填项
            if st.session_state.question_scope_error:
                st.error(f"❌ 题号范围无效：{st.session_state.question_scope_error}")
            elif final_answer_files and final_rubric_files:
                print("按钮被点击了！启动批改...")  # 调试日志
                # 保存文件路径
                st.session_state.uploaded_file_paths = {
                    'question': final_question_files,  # 可能为空列表
                    'answer': final_answer_files,
                    'rubric': final_rubric_files
                }
                st.session_state.selected_question_scope = st.session_state.question_scope.copy()
                print(f"文件路径已保存: {st.session_state.uploaded_file_paths}")
                # 立即跳转到结果页面
                st.session_state.current_view = "result"
                st.rerun()
            else:
                if not final_answer_files:
                    st.error("❌ Missing Answer Files (Required)")
                if not final_rubric_files:
                    st.error("❌ Missing Rubric Files (Required)")

        # 架构说明
        with st.expander("🔌 SYSTEM ARCHITECTURE / 系统架构", expanded=False):
            st.markdown("""
            **8 AGENTS SWARM INTELLIGENCE**:
            1. `Orchestrator` - Mission Control
            2. `MultiModalInput` - Vision Processing
            3. `ParallelUnderstanding` - Context Analysis
            4. `StudentDetection` - Entity Recognition
            5. `BatchPlanning` - Workload Distribution
            6. `RubricMaster` - Criteria Standardization
            7. `GradingWorker` - Evaluation Engine
            8. `ResultAggregator` - Final Reporting
            """)

    else:
        st.error("SYSTEM FAILURE: AI Core Not Ready")


def show_result_page():
    """显示批改结果页面（新设计）"""
    from functions.grading_result_page import show_grading_result_page
    from functions.streaming_grading import run_streaming_grading, show_loading_animation
    import asyncio

    # 返回按钮
    if st.button("← 返回批改设置", type="secondary"):
        st.session_state.current_view = "grading"
        st.session_state.grading_result = None
        st.rerun()

    # 如果还没有批改结果，开始批改
    if not st.session_state.grading_result:
        st.markdown("### 🚀 AI 批改进行中...")

        # 显示加载动画
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 流式内容显示区域
        st.markdown("---")
        st.markdown("#### 💭 AI 思考过程（实时）")
        thought_container = st.empty()
        text_container = st.empty()

        # 用于存储流式内容
        thought_buffer = []
        text_buffer = []

        try:
            # 获取文件路径
            question_data = st.session_state.uploaded_file_paths.get('question', [])
            answer_data = st.session_state.uploaded_file_paths.get('answer')
            rubric_data = st.session_state.uploaded_file_paths.get('rubric')

            if not answer_data or not rubric_data:
                st.error("文件路径丢失，请重新上传")
                return
            
            # 处理多文件列表
            if isinstance(question_data, list):
                question_files = question_data
            else:
                question_files = [str(question_data)] if question_data else []
            
            if isinstance(answer_data, list):
                answer_files = answer_data
            else:
                answer_files = [str(answer_data)]
            
            if isinstance(rubric_data, list):
                rubric_files = rubric_data
            else:
                rubric_files = [str(rubric_data)]

            scope_payload = st.session_state.get('selected_question_scope') or st.session_state.get('question_scope', {})
            target_questions = scope_payload.get('questions', []) if isinstance(scope_payload, dict) else []
            scope_description = scope_payload.get('normalized') or scope_payload.get('raw', '')
            scope_warnings = scope_payload.get('warnings', [])

            # 运行批改
            from functions.langgraph.workflow_multimodal import run_multimodal_grading

            # 定义进度回调函数
            def update_progress(state_value, current_node):
                """更新进度条和状态文本"""
                if isinstance(state_value, dict):
                    progress = state_value.get('progress_percentage', 0) / 100.0
                    progress_bar.progress(min(progress, 1.0))
                    status_text.markdown(f"**当前步骤**: {current_node} ({progress*100:.0f}%)")

            # 定义流式内容回调函数
            def streaming_callback(chunk):
                """处理流式传输的内容"""
                chunk_type = chunk.get("type", "text")
                chunk_content = chunk.get("content", "")
                student = chunk.get("student", "")

                if chunk_type == "thought":
                    # 思考内容
                    thought_buffer.append(chunk_content)
                    # 实时更新显示
                    thought_container.markdown(
                        f"**💭 思考中...** ({student})\n\n" + "".join(thought_buffer[-500:]),  # 只显示最后 500 字符
                        unsafe_allow_html=True
                    )
                elif chunk_type == "text":
                    # 文本内容
                    text_buffer.append(chunk_content)
                    # 实时更新显示
                    text_container.markdown(
                        f"**📝 生成中...** ({student})\n\n```json\n" + "".join(text_buffer[-1000:]) + "\n```",  # 只显示最后 1000 字符
                        unsafe_allow_html=True
                    )

            result = asyncio.run(
                run_multimodal_grading(
                    task_id=f"streamlit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    user_id=st.session_state.get('user_id', 'streamlit_user'),
                    question_files=question_files,  # 支持题目文件
                    answer_files=answer_files,
                    marking_files=rubric_files,  # 支持多个评分标准文件
                    strictness_level="中等",
                    language="zh",
                    target_questions=target_questions,
                    scope_description=scope_description,
                    scope_warnings=scope_warnings,
                    progress_callback=update_progress,
                    streaming_callback=streaming_callback  # 传递流式回调
                )
            )

            # 保存结果
            st.session_state.grading_result = result
            progress_bar.progress(1.0)
            status_text.markdown("**✅ 批改完成！**")
            st.balloons()

            # 刷新页面显示结果
            st.rerun()

        except Exception as e:
            st.error(f"❌ 批改失败: {str(e)}")
            import traceback
            with st.expander("查看错误详情"):
                st.code(traceback.format_exc(), language='text')
    else:
        # 显示批改结果
        show_grading_result_page(
            result=st.session_state.grading_result,
            uploaded_files=st.session_state.uploaded_file_paths
        )

def run_grading_in_streamlit(answer_pdf: str, marking_pdf: str):
    """在Streamlit中运行批改流程 - 简化版本，直接执行"""
    import asyncio
    from functions.langgraph.workflow_multimodal import run_multimodal_grading

    # 文件路径处理
    answer_path = Path(answer_pdf) if isinstance(answer_pdf, str) else answer_pdf
    marking_path = Path(marking_pdf) if isinstance(marking_pdf, str) else marking_pdf

    if not answer_path.exists() or not marking_path.exists():
        st.error("❌ 文件不存在！")
        return

    # 使用 spinner 显示进度
    with st.spinner("🚀 AI 批改进行中...这可能需要 2-3 分钟，请耐心等待..."):
        try:
            # 直接运行异步函数
            result = asyncio.run(
                run_multimodal_grading(
                    task_id=f"streamlit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    user_id=st.session_state.get('user_id', 'streamlit_user'),
                    question_files=[],
                    answer_files=[str(answer_path)],
                    marking_files=[str(marking_path)],
                    strictness_level="中等",
                    language="zh",
                    target_questions=[],
                    scope_description="",
                    scope_warnings=[],
                    progress_callback=None  # 暂时不使用回调
                )
            )

            # 保存结果并显示
            st.session_state.grading_result = result
            st.session_state.just_completed_grading = True
            st.success("✅ 批改完成！")
            st.balloons()
            display_grading_result(result)

        except Exception as e:
            st.error(f"❌ 批改失败: {str(e)}")
            import traceback
            with st.expander("查看错误详情"):
                st.code(traceback.format_exc(), language='text')

def display_grading_result(result: Dict):
    """显示批改结果"""
    if not result:
        st.warning("批改结果为空")
        return

    st.markdown("---")
    animated_title("ANALYSIS REPORT", "GRADING OUTCOME")

    # 检查是否有错误
    errors = result.get('errors', [])
    warnings = result.get('warnings', [])
    
    if errors:
        with neo_card_container():
            st.error("### ❌ 批改过程中出现错误")
            for i, error in enumerate(errors, 1):
                if isinstance(error, dict):
                    st.write(f"{i}. [{error.get('step', 'unknown')}] {error.get('error', str(error))}")
                else:
                    st.write(f"{i}. {error}")
        
    if warnings:
        with neo_card_container():
            st.warning("### ⚠️ 警告信息")
            for i, warning in enumerate(warnings, 1):
                if isinstance(warning, dict):
                    st.write(f"{i}. [{warning.get('step', 'unknown')}] {warning.get('warning', str(warning))}")
                else:
                    st.write(f"{i}. {warning}")

    # 核心指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("TOTAL SCORE", f"{result.get('total_score', 0)}")
    with col2:
        st.metric("STATUS", result.get('status', 'N/A'))
    with col3:
        st.metric("GRADE", result.get('grade_level', 'N/A'))
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 检查是否有评估结果
    criteria_evaluations = result.get('criteria_evaluations', [])
    student_reports = result.get('student_reports', [])
    
    if not criteria_evaluations and not student_reports:
        with neo_card_container():
            st.warning("### ⚠️ 没有找到批改评估结果")
            st.markdown("""
            可能的原因：
            1. 批改过程中出现错误，但已标记为完成
            2. PDF文件解析失败
            3. 评分标准解析失败
            4. 没有找到学生答案
            
            请检查终端日志获取更多信息。
            """)
    else:
        # 详细评估
        display_by_student(result)
    
    # LLM处理过程
    display_llm_process(result.get('step_results'))
    
    # 反馈
    if result.get('detailed_feedback'):
        with neo_card_container("green-shadow"):
            st.markdown("### 💬 AI FEEDBACK")
            for feedback in result.get('detailed_feedback', []):
                content = feedback.get('content', str(feedback)) if isinstance(feedback, dict) else str(feedback)
                st.markdown(f"- {content}")

def display_by_student(result):
    """按学生显示"""
    student_reports = result.get('student_reports', [])
    
    # 如果没有学生报告，尝试构造一个临时的
    if not student_reports and result.get('criteria_evaluations'):
        student_reports = [{
            'student_name': 'Current Student', 
            'student_id': '001', 
            'total_score': result.get('total_score'),
            'evaluations': result.get('criteria_evaluations')
        }]
        
    for student in student_reports:
        with st.expander(f"👤 {student.get('student_name')} - SCORE: {student.get('total_score')}", expanded=True):
            for i, eval_item in enumerate(student.get('evaluations', []), 1):
                score = eval_item.get('score_earned', 0)
                max_score = eval_item.get('max_score', 0)
                satisfaction = eval_item.get('satisfaction_level', '')
                
                # 标签样式
                tag_class = "success" if score == max_score else "warning" if score > 0 else "error"
                
                st.markdown(f"""
                <div style="margin-bottom: 10px; padding: 10px; border-left: 4px solid black; background: #f9f9f9;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>POINT {i}: {eval_item.get('criterion_id')}</strong>
                        <span class="tag {tag_class}">{score}/{max_score}</span>
                    </div>
                    <div style="margin-top: 5px; font-size: 0.9rem;">
                        <div><strong>Reason:</strong> {eval_item.get('justification')}</div>
                        <div style="color: #666;"><em>Status: {satisfaction}</em></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)


def display_llm_process(step_results: Dict | None):
    """展示LLM处理过程"""
    if not step_results:
        return
    
    step_title_map = {
        "RubricInterpreterAgent": "评分标准解析",
        "rubric_interpretation": "评分标准解析",
        "GradingWorkerAgent": "批改引擎",
        "grading_worker": "批改引擎",
    }
    
    with neo_card_container("purple-shadow"):
        st.markdown("### 🧠 LLM PROCESS TIMELINE")
        st.caption("完整记录每一次LLM调用的模型、提示词与响应摘要，确保真实批改链路可追踪。")
        
        for step_key, payload in step_results.items():
            if payload is None:
                continue
            title = step_title_map.get(step_key, step_key)
            
            with st.expander(f"📡 {title}", expanded=False):
                if isinstance(payload, dict) and 'llm_calls' in payload:
                    for idx, call in enumerate(payload['llm_calls'], 1):
                        _render_llm_call(call, idx)
                else:
                    _render_llm_call(payload, 1)


def _render_llm_call(call_payload: Dict, idx: int):
    """渲染单次LLM调用"""
    if not isinstance(call_payload, dict):
        st.write(call_payload)
        return
    
    provider = call_payload.get('provider', 'unknown')
    model = call_payload.get('model', 'unknown')
    timestamp = call_payload.get('timestamp', '')
    summary = call_payload.get('summary', '')
    
    st.markdown(f"**LLM 调用 #{idx}** ｜ 模型：`{provider}:{model}` ｜ {timestamp}")
    if summary:
        st.markdown(f"> {summary}")
    
    meta_cols = st.columns(3)
    with meta_cols[0]:
        st.caption(f"温度：{call_payload.get('temperature', 'N/A')}")
    with meta_cols[1]:
        st.caption(f"思维强度：{call_payload.get('reasoning_effort', '默认')}")
    with meta_cols[2]:
        st.caption(f"消息数：{call_payload.get('message_count', 'N/A')}")
    
    prompt_preview = call_payload.get('prompt_preview')
    response_preview = call_payload.get('response_preview')
    
    if prompt_preview:
        st.markdown("**Prompt 片段**")
        st.code(prompt_preview, language='markdown')
    if response_preview:
        st.markdown("**LLM 响应片段**")
        st.code(response_preview, language='markdown')
    
def show_history():
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.rerun()
        return
    
    animated_title("ARCHIVES", "HISTORY RECORDS")
    
    users = read_users()
    records = users.get(st.session_state.username, {}).get('records', [])
    
    if not records:
        st.info("NO RECORDS FOUND")
        return
    
    for i, record in enumerate(reversed(records), 1):
        with neo_card_container():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**TIMESTAMP**: {record['timestamp']}")
                st.caption(f"Files: {len(record.get('files', []))}")
            with c2:
                if st.button("VIEW", key=f"hist_{i}"):
                    st.session_state.correction_result = record.get('result')
                    st.session_state.page = "result"
            st.rerun()
    
def show_result():
    # 简单的结果展示页面
    if not st.session_state.correction_result:
        st.session_state.page = "grading"
        st.rerun()
        return
        
    animated_title("RESULT VIEW", "DETAILED REPORT")
    
    if st.button("⬅ BACK TO GRADING"):
        st.session_state.page = "grading"
        st.rerun()
    
    display_grading_result(st.session_state.correction_result)

def show_scanner():
    """显示手机我会操作不了手机前端，所以这个会展示手机前端的路径"""
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.rerun()
        return
    
    animated_title("SCANNER INTEGRATION", "BOOKSCAN-AI POWERED")
    
    if BOOKSCAN_AVAILABLE and show_bookscan_scanner:
        scanned_images, ready = show_bookscan_scanner()
        
        st.markdown("---")
        
        if ready and scanned_images:
            if st.button("🚀 接级到批改水源", type="primary", use_container_width=True):
                # 准备批改数据
                st.session_state.uploaded_file_paths = {
                    'question': [],
                    'answer': [img['path'] for img in scanned_images],
                    'rubric': []
                }
                st.session_state.current_view = "result"
                st.session_state.page = "grading"
                st.info("📌 请先上传评分标准文件")
    else:
        st.error("⚠️ Bookscan 模块未就绪")

def show_api_integration():
    """显示 API 集成效果"""
    if not st.session_state.logged_in:
        st.session_state.page = "login"
        st.rerun()
        return
    
    animated_title("API INTEGRATION", "SYSTEM ARCHITECTURE")
    
    if BOOKSCAN_AVAILABLE and show_api_integration_demo:
        show_api_integration_demo()
    else:
        st.error("⚠️ API 演示模块未就绪")

def show_sidebar():
    with st.sidebar:
        st.markdown("### ⚡ AI GURU")

        if st.session_state.logged_in:
            st.success(f"USER: {st.session_state.username}")
            st.markdown("---")

            menu_items = {
                "home": "🏠 HOME",
                "grading": "📝 GRADING",
                "scanner": "📱 SCANNER",
                "api_demo": "🔗 API DEMO",
                "history": "📚 HISTORY",
            }
            
            for page_id, label in menu_items.items():
                if st.button(label, use_container_width=True, type="primary" if st.session_state.page == page_id else "secondary"):
                    st.session_state.page = page_id
                    st.rerun()
            
            st.markdown("---")
            if st.button("🚪 LOGOUT", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.page = "home"
                st.rerun()
                
        else:
            if st.button("🔑 LOGIN", use_container_width=True, type="primary"):
                st.session_state.page = "login"
                st.rerun()
            
def main():
    init_session()
    show_sidebar()

    pages = {
        "home": show_home,
        "login": show_login,
        "grading": show_grading,
        "scanner": show_scanner,
        "api_demo": show_api_integration,
        "history": show_history,
        "result": show_result
    }
    
    current_page = pages.get(st.session_state.page, show_home)
    current_page()

if __name__ == "__main__":
    main() 
