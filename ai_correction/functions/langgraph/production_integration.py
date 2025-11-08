#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产级 LangGraph 集成 - Streamlit 接口
"""

import streamlit as st
from typing import List, Dict, Any
from pathlib import Path
import time


def run_production_grading(
    question_files: List[str],
    answer_files: List[str],
    marking_files: List[str] = None,
    llm_api_key: str = None
) -> Dict[str, Any]:
    """
    运行生产级批改
    
    Args:
        question_files: 题目文件路径列表
        answer_files: 答案文件路径列表
        marking_files: 评分标准文件路径列表
        llm_api_key: LLM API 密钥
        
    Returns:
        批改结果
    """
    from .workflow_production import run_grading_workflow, format_grading_result
    
    # 创建进度容器
    progress_container = st.container()
    
    with progress_container:
        st.info("🚀 开始批改流程...")
        
        # 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 流式运行工作流
        total_steps = 6
        current_step = 0
        
        final_state = None
        
        try:
            for output in run_grading_workflow(
                question_files=question_files,
                answer_files=answer_files,
                marking_files=marking_files,
                stream=True
            ):
                # 更新进度
                if output:
                    current_step += 1
                    progress = current_step / total_steps
                    progress_bar.progress(progress)
                    
                    # 获取当前步骤
                    for node_name, node_state in output.items():
                        stream_outputs = node_state.get('stream_output', [])
                        
                        for stream_output in stream_outputs:
                            step = stream_output.get('step', 'unknown')
                            
                            if step == 'parse':
                                status_text.text("📄 解析输入文件...")
                            elif step == 'analyze':
                                status_text.text("🔍 分析题目特征...")
                            elif step == 'rubric':
                                status_text.text("📋 解析评分标准...")
                            elif step == 'grading':
                                q_id = stream_output.get('question_id')
                                progress_info = stream_output.get('progress', '')
                                status_text.text(f"✍️ 批改第 {q_id} 题 ({progress_info})...")
                            elif step == 'aggregate':
                                status_text.text("📊 聚合结果...")
                            elif step == 'persist':
                                status_text.text("💾 保存数据...")
                        
                        final_state = node_state
            
            # 完成
            progress_bar.progress(1.0)
            status_text.text("✅ 批改完成！")
            
            # 格式化结果
            if final_state:
                result_md = format_grading_result(final_state)
                return {
                    'status': 'success',
                    'result': result_md,
                    'state': final_state
                }
            else:
                return {
                    'status': 'error',
                    'message': '批改流程未完成'
                }
                
        except Exception as e:
            progress_bar.progress(0)
            status_text.text(f"❌ 批改失败: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }


def show_production_grading_ui():
    """显示生产级批改 UI"""
    st.header("🎓 生产级 AI 批改系统")
    
    st.markdown("""
    ### ✨ 功能特点
    - 📝 **逐题批改**: 精确定位每道题的错误
    - 📊 **数据分析**: 多维度统计分析
    - 💾 **数据持久化**: 自动保存到数据库
    - 🔄 **流式处理**: 实时反馈批改进度
    - 🎯 **智能策略**: 根据题型选择批改方法
    """)
    
    # 文件上传
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📄 题目文件")
        question_files = st.file_uploader(
            "上传题目文件",
            type=['txt', 'md', 'json'],
            accept_multiple_files=True,
            key='question_files'
        )
    
    with col2:
        st.subheader("✍️ 答案文件")
        answer_files = st.file_uploader(
            "上传答案文件",
            type=['txt', 'md', 'json'],
            accept_multiple_files=True,
            key='answer_files'
        )
    
    with col3:
        st.subheader("📋 评分标准（可选）")
        marking_files = st.file_uploader(
            "上传评分标准",
            type=['txt', 'md', 'json'],
            accept_multiple_files=True,
            key='marking_files'
        )
    
    # API 配置
    with st.expander("⚙️ 高级配置"):
        llm_api_key = st.text_input(
            "LLM API 密钥（可选）",
            type="password",
            help="如果不提供，将使用关键词匹配等简单策略"
        )
        
        db_type = st.selectbox(
            "数据库类型",
            ['postgresql', 'mysql', 'json'],
            help="选择数据存储方式"
        )
        
        if db_type != 'json':
            db_url = st.text_input(
                "数据库连接字符串",
                help="例如: postgresql://user:pass@localhost/dbname"
            )
    
    # 开始批改
    if st.button("🚀 开始批改", type="primary", use_container_width=True):
        if not question_files or not answer_files:
            st.error("❌ 请至少上传题目文件和答案文件")
            return
        
        # 保存上传的文件
        import tempfile
        import os
        
        temp_dir = tempfile.mkdtemp()
        
        question_paths = []
        for f in question_files:
            path = os.path.join(temp_dir, f.name)
            with open(path, 'wb') as fp:
                fp.write(f.read())
            question_paths.append(path)
        
        answer_paths = []
        for f in answer_files:
            path = os.path.join(temp_dir, f.name)
            with open(path, 'wb') as fp:
                fp.write(f.read())
            answer_paths.append(path)
        
        marking_paths = []
        if marking_files:
            for f in marking_files:
                path = os.path.join(temp_dir, f.name)
                with open(path, 'wb') as fp:
                    fp.write(f.read())
                marking_paths.append(path)
        
        # 运行批改
        result = run_production_grading(
            question_files=question_paths,
            answer_files=answer_paths,
            marking_files=marking_paths if marking_paths else None,
            llm_api_key=llm_api_key
        )
        
        # 显示结果
        if result['status'] == 'success':
            st.success("✅ 批改完成！")
            
            # 显示结果
            st.markdown(result['result'])
            
            # 下载按钮
            st.download_button(
                label="📥 下载批改结果",
                data=result['result'],
                file_name="grading_result.md",
                mime="text/markdown"
            )
            
            # 显示详细数据
            with st.expander("📊 查看详细数据"):
                st.json(result['state'].get('aggregated_results', {}))
        else:
            st.error(f"❌ 批改失败: {result.get('message', '未知错误')}")


def show_history_ui():
    """显示历史记录 UI"""
    st.header("📚 批改历史")
    
    from ..database import DatabaseManager
    
    db = DatabaseManager()
    
    # 学生查询
    student_id = st.text_input("输入学号查询历史记录")
    
    if student_id:
        history = db.get_student_history(student_id)
        
        if history:
            st.success(f"找到 {len(history)} 条记录")
            
            for record in history:
                with st.expander(f"📝 {record['subject']} - {record['created_at']}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("得分", f"{record['total_score']}/{record['max_score']}")
                    
                    with col2:
                        st.metric("等级", record['grade'])
                    
                    with col3:
                        st.metric("任务ID", record['task_id'])
        else:
            st.info("暂无历史记录")


def show_class_statistics_ui():
    """显示班级统计 UI"""
    st.header("📊 班级统计")
    
    from ..database import DatabaseManager
    
    db = DatabaseManager()
    
    # 班级查询
    class_name = st.text_input("输入班级名称")
    
    if class_name:
        stats = db.get_class_statistics(class_name)
        
        if stats['student_count'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("学生人数", stats['student_count'])
            
            with col2:
                st.metric("批改任务数", stats['total_tasks'])
            
            with col3:
                st.metric("平均分", f"{stats['average_score']:.1f}%")
            
            with col4:
                st.metric("班级", class_name)
        else:
            st.info("暂无数据")

