#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式批改功能 - 实时展示批改进度
"""

import streamlit as st
import asyncio
from typing import Dict, Any, Generator
from datetime import datetime
import json


async def run_streaming_grading(
    task_id: str,
    user_id: str,
    answer_files: list,
    marking_files: list,
    strictness_level: str = "中等",
    language: str = "zh"
) -> Dict[str, Any]:
    """
    运行流式批改（带进度展示）
    
    Args:
        task_id: 任务ID
        user_id: 用户ID
        answer_files: 学生答案文件列表
        marking_files: 评分标准文件列表
        strictness_level: 严格程度
        language: 语言
    
    Returns:
        批改结果字典
    """
    from functions.langgraph.workflow_multimodal import run_multimodal_grading
    
    # 创建进度容器
    progress_container = st.empty()
    status_container = st.empty()
    
    # 显示初始状态
    with progress_container.container():
        st.markdown("### 🚀 AI 批改进行中...")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # 定义进度回调
    def progress_callback(step: str, progress: float, message: str = ""):
        """进度回调函数"""
        with progress_container.container():
            progress_bar.progress(min(progress, 1.0))
            status_text.markdown(f"**{step}**: {message}")
    
    try:
        # 运行批改
        result = await run_multimodal_grading(
            task_id=task_id,
            user_id=user_id,
            question_files=[],
            answer_files=answer_files,
            marking_files=marking_files,
            strictness_level=strictness_level,
            language=language,
            progress_callback=progress_callback
        )
        
        # 完成
        progress_bar.progress(1.0)
        status_text.markdown("**✅ 批改完成！**")
        
        return result
        
    except Exception as e:
        status_text.markdown(f"**❌ 批改失败**: {str(e)}")
        raise


def show_streaming_progress(step_name: str, stream_generator: Generator[str, None, None]):
    """
    显示流式进度（逐字展示）
    
    Args:
        step_name: 步骤名称
        stream_generator: 流式生成器
    """
    st.markdown(f"#### {step_name}")
    
    # 创建一个容器用于流式更新
    text_container = st.empty()
    full_text = ""
    
    # 逐块接收并显示
    for chunk in stream_generator:
        full_text += chunk
        text_container.markdown(full_text)
    
    return full_text


def show_criterion_stream(criterion_id: str, stream_generator: Generator[str, None, None]):
    """
    显示单个评分点的流式批改过程
    
    Args:
        criterion_id: 评分点ID
        stream_generator: 流式生成器
    """
    with st.expander(f"📝 {criterion_id} - 批改中...", expanded=True):
        text_container = st.empty()
        full_text = ""
        
        for chunk in stream_generator:
            full_text += chunk
            # 实时更新
            text_container.markdown(full_text)
        
        return full_text


def create_animated_score_display(score: float, max_score: float, duration: float = 1.0):
    """
    创建动画分数展示（数字递增效果）
    
    Args:
        score: 最终分数
        max_score: 满分
        duration: 动画持续时间（秒）
    """
    import time
    
    score_container = st.empty()
    steps = 20
    step_duration = duration / steps
    
    for i in range(steps + 1):
        current_score = (score / steps) * i
        percentage = (current_score / max_score * 100) if max_score > 0 else 0
        
        # 确定颜色
        if percentage >= 90:
            color = "#10b981"
        elif percentage >= 70:
            color = "#f59e0b"
        else:
            color = "#ef4444"
        
        score_container.markdown(f"""
        <div style="text-align: center; padding: 2rem;">
            <div style="font-size: 4rem; font-weight: 900; color: {color};">
                {current_score:.1f}
            </div>
            <div style="font-size: 1.5rem; color: #6b7280;">
                / {max_score}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if i < steps:
            time.sleep(step_duration)


def show_typing_effect(text: str, speed: float = 0.03):
    """
    打字机效果展示文本
    
    Args:
        text: 要展示的文本
        speed: 每个字符的延迟（秒）
    """
    import time
    
    text_container = st.empty()
    displayed_text = ""
    
    for char in text:
        displayed_text += char
        text_container.markdown(displayed_text)
        time.sleep(speed)
    
    return displayed_text


def show_loading_animation(message: str = "处理中..."):
    """
    显示加载动画
    
    Args:
        message: 加载消息
    """
    st.markdown(f"""
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    .loader {{
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 0 auto;
    }}
    </style>
    <div style="text-align: center; padding: 2rem;">
        <div class="loader"></div>
        <p style="margin-top: 1rem; color: #6b7280;">{message}</p>
    </div>
    """, unsafe_allow_html=True)

