#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批改结果页面 - 流式展示 + 响应式设计
"""

import streamlit as st
import json
import base64
from pathlib import Path
from typing import Dict, Any, List
import time


def show_grading_result_page(result: Dict[str, Any], uploaded_files: Dict[str, str]):
    """
    显示批改结果页面（新设计）
    
    Args:
        result: 批改结果字典
        uploaded_files: 上传的文件路径 {"answer": "path/to/answer.pdf", "rubric": "path/to/rubric.pdf"}
    """
    # 页面标题
    st.markdown("""
    <style>
    .result-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        margin-bottom: 2rem;
    }
    .result-header h1 {
        font-size: 2.5rem;
        font-weight: 800;
        margin: 0;
    }
    .result-header p {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }
    </style>
    <div class="result-header">
        <h1>📊 批改结果</h1>
        <p>AI 智能批改已完成</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 核心指标卡片（响应式）
    show_score_cards(result)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 三大核心内容区域
    tab1, tab2, tab3 = st.tabs(["📝 批改详情", "📋 评分标准", "📄 原始文件"])
    
    with tab1:
        show_grading_details(result)
    
    with tab2:
        show_rubric_details(result)
    
    with tab3:
        show_uploaded_files(uploaded_files)


def show_score_cards(result: Dict[str, Any]):
    """显示核心指标卡片（响应式设计）"""
    total_score = result.get('total_score', 0)
    max_score = result.get('max_possible_score', 100)
    grade = result.get('grade_level', 'N/A')
    status = result.get('status', 'N/A')
    
    # 计算百分比
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    
    # 根据分数确定颜色
    if percentage >= 90:
        color = "#10b981"  # 绿色
        emoji = "🎉"
    elif percentage >= 70:
        color = "#f59e0b"  # 橙色
        emoji = "👍"
    elif percentage >= 60:
        color = "#ef4444"  # 红色
        emoji = "💪"
    else:
        color = "#6b7280"  # 灰色
        emoji = "📚"
    
    # 响应式卡片布局
    st.markdown(f"""
    <style>
    .score-container {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }}
    .score-card {{
        background: white;
        border: 3px solid black;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 6px 6px 0 black;
        transition: transform 0.2s;
    }}
    .score-card:hover {{
        transform: translate(-2px, -2px);
        box-shadow: 8px 8px 0 black;
    }}
    .score-value {{
        font-size: 2.5rem;
        font-weight: 900;
        color: {color};
        margin: 0.5rem 0;
    }}
    .score-label {{
        font-size: 0.9rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }}
    @media (max-width: 768px) {{
        .score-value {{
            font-size: 2rem;
        }}
    }}
    </style>
    <div class="score-container">
        <div class="score-card">
            <div class="score-label">总分</div>
            <div class="score-value">{emoji} {total_score:.1f}/{max_score}</div>
        </div>
        <div class="score-card">
            <div class="score-label">得分率</div>
            <div class="score-value">{percentage:.1f}%</div>
        </div>
        <div class="score-card">
            <div class="score-label">等级</div>
            <div class="score-value">{grade}</div>
        </div>
        <div class="score-card">
            <div class="score-label">状态</div>
            <div class="score-value" style="font-size: 1.5rem;">{status}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def show_grading_details(result: Dict[str, Any]):
    """显示批改详情（按题目分组）"""
    st.markdown("### 📝 详细评分")
    
    # 获取所有评估结果
    evaluations = result.get('criteria_evaluations', [])
    student_reports = result.get('student_reports', [])
    
    if student_reports:
        evaluations = student_reports[0].get('evaluations', [])
    
    if not evaluations:
        st.warning("暂无评分详情")
        return
    
    # 按题目分组
    questions_dict = {}
    for eval_item in evaluations:
        criterion_id = eval_item.get('criterion_id', '')
        # 提取题目编号 (例如 Q1_C1 -> Q1)
        question_id = criterion_id.split('_')[0] if '_' in criterion_id else 'Q0'

        if question_id not in questions_dict:
            questions_dict[question_id] = []
        questions_dict[question_id].append(eval_item)

    # 按题目展示
    for question_id in sorted(questions_dict.keys()):
        criteria = questions_dict[question_id]

        # 计算该题得分
        question_score = sum(c.get('score_earned', 0) for c in criteria)
        question_max = sum(c.get('max_score', 0) for c in criteria)

        with st.expander(f"**{question_id}** - {question_score:.1f}/{question_max} 分", expanded=True):
            for i, eval_item in enumerate(criteria, 1):
                show_criterion_card(eval_item, i)


def show_criterion_card(eval_item: Dict[str, Any], index: int):
    """显示单个评分点卡片"""
    criterion_id = eval_item.get('criterion_id', '')
    score = eval_item.get('score_earned', 0)
    max_score = eval_item.get('max_score', 0)
    justification = eval_item.get('justification', '')
    satisfaction = eval_item.get('satisfaction_level', '')

    # 确定颜色
    if score == max_score:
        border_color = "#10b981"  # 绿色
        bg_color = "#f0fdf4"
    elif score > 0:
        border_color = "#f59e0b"  # 橙色
        bg_color = "#fffbeb"
    else:
        border_color = "#ef4444"  # 红色
        bg_color = "#fef2f2"

    st.markdown(f"""
    <div style="
        border-left: 4px solid {border_color};
        background: {bg_color};
        padding: 1rem;
        margin-bottom: 0.8rem;
        border-radius: 4px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <strong style="font-size: 1.05rem;">{criterion_id}</strong>
            <span style="
                background: {border_color};
                color: white;
                padding: 0.25rem 0.75rem;
                border-radius: 12px;
                font-weight: 700;
                font-size: 0.9rem;
            ">{score}/{max_score}</span>
        </div>
        <div style="color: #374151; line-height: 1.6;">
            <strong>评语：</strong>{justification}
        </div>
        <div style="color: #6b7280; font-size: 0.9rem; margin-top: 0.5rem;">
            <em>状态：{satisfaction}</em>
        </div>
    </div>
    """, unsafe_allow_html=True)


def show_rubric_details(result: Dict[str, Any]):
    """显示评分标准详情"""
    st.markdown("### 📋 评分标准解析")

    rubric_result = result.get('rubric_parsing_result', {})
    criteria = rubric_result.get('criteria', [])

    if not criteria:
        st.warning("未找到评分标准解析结果")
        return

    st.info(f"共解析出 **{len(criteria)}** 个评分点")

    # 按题目分组
    questions_dict = {}
    for criterion in criteria:
        question_id = criterion.get('question_id', 'Q0')
        if question_id not in questions_dict:
            questions_dict[question_id] = []
        questions_dict[question_id].append(criterion)

    # 展示
    for question_id in sorted(questions_dict.keys()):
        criteria_list = questions_dict[question_id]
        total_points = sum(c.get('points', 0) for c in criteria_list)

        with st.expander(f"**{question_id}** - 共 {len(criteria_list)} 个评分点，总分 {total_points}", expanded=False):
            for criterion in criteria_list:
                st.markdown(f"""
                - **{criterion.get('criterion_id')}** ({criterion.get('points')} 分)
                  {criterion.get('description', '')}
                """)


def show_uploaded_files(uploaded_files: Dict[str, str]):
    """显示上传的原始文件"""
    st.markdown("### 📄 原始文件")

    if not uploaded_files:
        st.warning("未找到上传的文件")
        return

    col1, col2 = st.columns(2)

    with col1:
        if 'answer' in uploaded_files:
            st.markdown("#### 学生作答")
            show_pdf_preview(uploaded_files['answer'], "学生作答.pdf")

    with col2:
        if 'rubric' in uploaded_files:
            st.markdown("#### 批改标准")
            show_pdf_preview(uploaded_files['rubric'], "批改标准.pdf")


def show_pdf_preview(file_path: str, file_name: str):
    """显示 PDF 预览或下载按钮"""
    try:
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()

        # 提供下载按钮
        st.download_button(
            label=f"📥 下载 {file_name}",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf"
        )

        # 尝试嵌入预览（移动端可能不支持）
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"无法加载文件: {str(e)}")


