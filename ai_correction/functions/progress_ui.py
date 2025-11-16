"""
批改进度 UI 模块
提供进度展示、状态更新等 UI 组件
"""

import streamlit as st
import time
from datetime import datetime
from .correction_service import (
    get_correction_service, TaskStatus, CorrectionPhase
)


def show_progress_page():
    """显示批改进度页面"""
    st.markdown('<h2 style="color: #000000; text-align: center;">📊 批改进度</h2>', 
                unsafe_allow_html=True)
    
    # 获取当前任务 ID
    task_id = st.session_state.get("current_task_id")
    
    if not task_id:
        st.info("📌 暂无进行中的批改任务")
        return
    
    service = get_correction_service(use_simulator=True)
    task = service.get_task_status(task_id)
    
    if not task:
        st.error("❌ 任务不存在")
        return
    
    # 创建三列布局
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.markdown("### 📋 任务信息")
        st.markdown(f"**任务 ID:** `{task.task_id}`")
        st.markdown(f"**文件数:** {len(task.files)}")
        st.markdown(f"**模式:** {task.mode}")
        st.markdown(f"**严格度:** {task.strictness}")
    
    with col2:
        st.markdown("### ⏱️ 进度详情")
        
        # 进度条
        st.markdown("**总体进度**")
        progress_bar = st.progress(task.progress / 100)
        st.markdown(f"<p style='text-align: center; color: #666666;'>{task.progress}%</p>", 
                   unsafe_allow_html=True)
        
        # 状态指示
        status_text = {
            TaskStatus.PENDING: "⏳ 待处理",
            TaskStatus.PROCESSING: "⚙️ 处理中",
            TaskStatus.COMPLETED: "✅ 已完成",
            TaskStatus.FAILED: "❌ 失败",
            TaskStatus.CANCELLED: "⛔ 已取消"
        }
        
        st.markdown(f"**状态:** {status_text.get(task.status, '未知')}")
    
    with col3:
        st.markdown("### ⏰ 时间信息")
        if task.started_at:
            elapsed = (datetime.now() - task.started_at).total_seconds()
            st.markdown(f"**耗时:** {int(elapsed)}s")
        
        if task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()
            st.markdown(f"**总耗时:** {int(duration)}s")
    
    st.markdown("---")
    
    # 阶段进度
    st.markdown("### 🔄 处理阶段")
    
    phases = [
        (CorrectionPhase.UPLOADING, "📤 文件上传"),
        (CorrectionPhase.ANALYZING, "🔍 题目分析"),
        (CorrectionPhase.CORRECTING, "✏️ 智能批改"),
        (CorrectionPhase.GENERATING, "📝 结果生成"),
        (CorrectionPhase.COMPLETED, "✅ 已完成")
    ]
    
    for phase, label in phases:
        if task.phase == phase or (task.phase.value > phase.value and task.status != TaskStatus.FAILED):
            # 已完成或当前阶段
            if task.phase == phase and task.status == TaskStatus.PROCESSING:
                st.markdown(f"<div style='padding: 10px; background-color: #f0f0f0; border-left: 4px solid #000000; margin: 5px 0;'><b>⏳ {label}</b></div>", 
                           unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='padding: 10px; background-color: #e8e8e8; border-left: 4px solid #000000; margin: 5px 0;'><b>✓ {label}</b></div>", 
                           unsafe_allow_html=True)
        else:
            # 未开始
            st.markdown(f"<div style='padding: 10px; background-color: #ffffff; border: 1px solid #cccccc; border-left: 4px solid #cccccc; margin: 5px 0;'>{label}</div>", 
                       unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 阶段消息
    st.markdown("### 📢 处理日志")
    
    if task.phase_messages:
        for msg in task.phase_messages:
            st.markdown(f"- {msg}")
    else:
        st.markdown("- 等待处理...")
    
    st.markdown("---")
    
    # 结果预览
    if task.status == TaskStatus.COMPLETED and task.result:
        st.markdown("### 📄 结果预览")
        st.text_area("批改结果", task.result, height=300, disabled=True)
        
        # 下载按钮
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "💾 下载结果",
                data=task.result,
                file_name=f"correction_{task.task_id}.txt",
                mime="text/plain"
            )
        with col2:
            if st.button("🔄 返回批改"):
                st.session_state.page = "grading"
                st.session_state.current_task_id = None
                st.rerun()
    
    elif task.status == TaskStatus.FAILED:
        st.error(f"❌ 批改失败: {task.error}")
        if st.button("🔄 返回批改"):
            st.session_state.page = "grading"
            st.session_state.current_task_id = None
            st.rerun()
    
    else:
        # 自动刷新
        st.markdown("---")
        st.info("⏳ 正在处理中，页面将自动刷新...")
        time.sleep(1)
        st.rerun()


def show_progress_modal(task_id: str):
    """显示进度模态框（用于在其他页面显示进度）"""
    service = get_correction_service(use_simulator=True)
    task = service.get_task_status(task_id)
    
    if not task:
        return
    
    # 创建进度显示
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.progress(task.progress / 100)
    
    with col2:
        status_emoji = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.PROCESSING: "⚙️",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "⛔"
        }
        st.markdown(f"<p style='text-align: center; font-size: 1.2rem;'>{status_emoji.get(task.status, '?')} {task.progress}%</p>", 
                   unsafe_allow_html=True)
    
    # 显示当前阶段
    phase_text = {
        CorrectionPhase.UPLOADING: "📤 上传中",
        CorrectionPhase.ANALYZING: "🔍 分析中",
        CorrectionPhase.CORRECTING: "✏️ 批改中",
        CorrectionPhase.GENERATING: "📝 生成中",
        CorrectionPhase.COMPLETED: "✅ 完成"
    }
    
    st.markdown(f"**当前阶段:** {phase_text.get(task.phase, '未知')}")

