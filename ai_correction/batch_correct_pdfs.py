#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF批改脚本 - 使用LangGraph工作流进行批改并实时追踪问题
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import json

# Windows控制台UTF-8编码支持
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_correction.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 导入必要的模块
from functions.langgraph.workflow_multimodal import run_multimodal_grading, get_multimodal_workflow
from functions.file_processor import process_multimodal_file


class PDFCorrectionTracker:
    """PDF批改追踪器 - 实时追踪批改进度和问题"""
    
    def __init__(self):
        self.start_time = None
        self.errors = []
        self.warnings = []
        self.progress_history = []
        
    def log_progress(self, step: str, progress: float, message: str = ""):
        """记录进度"""
        timestamp = datetime.now()
        progress_info = {
            'timestamp': timestamp.isoformat(),
            'step': step,
            'progress': progress,
            'message': message
        }
        self.progress_history.append(progress_info)
        
        # 打印进度
        progress_bar = "█" * int(progress / 2) + "░" * (50 - int(progress / 2))
        print(f"\r[{progress_bar}] {progress:.1f}% - {step} {message}", end='', flush=True)
        
        logger.info(f"进度更新: {step} - {progress:.1f}% - {message}")
    
    def log_error(self, step: str, error: str, details: Dict = None):
        """记录错误"""
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'step': step,
            'error': error,
            'details': details or {}
        }
        self.errors.append(error_info)
        print(f"\n❌ 错误 [{step}]: {error}")
        logger.error(f"错误 [{step}]: {error}", extra={'details': details})
    
    def log_warning(self, step: str, warning: str, details: Dict = None):
        """记录警告"""
        warning_info = {
            'timestamp': datetime.now().isoformat(),
            'step': step,
            'warning': warning,
            'details': details or {}
        }
        self.warnings.append(warning_info)
        print(f"\n⚠️  警告 [{step}]: {warning}")
        logger.warning(f"警告 [{step}]: {warning}", extra={'details': details})
    
    def print_summary(self):
        """打印摘要"""
        print("\n" + "="*80)
        print("📊 批改摘要")
        print("="*80)
        
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            print(f"⏱️  总耗时: {duration:.2f} 秒")
        
        print(f"✅ 进度记录: {len(self.progress_history)} 条")
        print(f"❌ 错误数量: {len(self.errors)} 条")
        print(f"⚠️  警告数量: {len(self.warnings)} 条")
        
        if self.errors:
            print("\n❌ 错误详情:")
            for i, err in enumerate(self.errors, 1):
                print(f"  {i}. [{err['step']}] {err['error']}")
        
        if self.warnings:
            print("\n⚠️  警告详情:")
            for i, warn in enumerate(self.warnings, 1):
                print(f"  {i}. [{warn['step']}] {warn['warning']}")
        
        print("="*80)
    
    def save_report(self, output_path: str, result: Dict[str, Any]):
        """保存批改报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'result': result,
            'progress_history': self.progress_history,
            'errors': self.errors,
            'warnings': self.warnings,
            'summary': {
                'total_progress_records': len(self.progress_history),
                'total_errors': len(self.errors),
                'total_warnings': len(self.warnings),
                'duration_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已保存到: {output_path}")


async def monitor_workflow_progress(workflow, initial_state: Dict, task_id: str, tracker: PDFCorrectionTracker):
    """监控工作流进度 - 使用values模式避免并发更新错误"""
    config = {"configurable": {"thread_id": task_id}}
    
    try:
        # 使用values模式获取完整状态，避免并发更新错误
        async for state_update in workflow.graph.astream(initial_state, config=config, stream_mode='values'):
            # state_update格式: {node_name: state_dict} 或直接是state_dict
            if isinstance(state_update, dict):
                # 检查是否是完整状态字典
                if 'task_id' in state_update:
                    state = state_update
                else:
                    # 如果是节点更新字典，取第一个值
                    state = list(state_update.values())[0] if state_update else {}
                
                # 提取进度信息
                progress = state.get('progress_percentage', 0)
                current_step = state.get('current_step', 'processing')
                errors = state.get('errors', [])
                warnings = state.get('warnings', [])
                
                # 记录进度
                tracker.log_progress(current_step, progress, f"状态更新")
                
                # 记录错误
                for error in errors:
                    if isinstance(error, dict):
                        tracker.log_error(
                            error.get('step', 'unknown'),
                            error.get('error', str(error)),
                            error
                        )
                    else:
                        tracker.log_error('unknown', str(error))
                
                # 记录警告
                for warning in warnings:
                    if isinstance(warning, dict):
                        tracker.log_warning(
                            warning.get('step', 'unknown'),
                            warning.get('warning', str(warning)),
                            warning
                        )
                    else:
                        tracker.log_warning('unknown', str(warning))
        
        return True
    except Exception as e:
        tracker.log_error('workflow_monitoring', f"监控工作流失败: {str(e)}")
        import traceback
        tracker.log_error('workflow_monitoring', f"详细错误:\n{traceback.format_exc()}")
        return False


async def correct_pdfs_with_tracking(
    question_pdf: str,
    answer_pdf: str,
    marking_pdf: str = None,
    strictness_level: str = "中等",
    language: str = "zh"
) -> Dict[str, Any]:
    """
    使用LangGraph工作流批改PDF文件，并实时追踪问题
    
    Args:
        question_pdf: 题目PDF文件路径
        answer_pdf: 学生作答PDF文件路径
        marking_pdf: 批改标准PDF文件路径（可选）
        strictness_level: 严格程度
        language: 语言
        
    Returns:
        批改结果字典
    """
    tracker = PDFCorrectionTracker()
    tracker.start_time = datetime.now()
    
    print("="*80)
    print("🚀 开始PDF批改任务")
    print("="*80)
    print(f"📄 题目文件: {question_pdf}")
    print(f"✏️  学生作答: {answer_pdf}")
    if marking_pdf:
        print(f"📊 批改标准: {marking_pdf}")
    print("="*80)
    
    # 检查文件是否存在
    files_to_check = {
        '题目文件': question_pdf,
        '学生作答': answer_pdf
    }
    if marking_pdf:
        files_to_check['批改标准'] = marking_pdf
    
    for file_type, file_path in files_to_check.items():
        if not Path(file_path).exists():
            tracker.log_error('file_validation', f"{file_type}不存在: {file_path}")
            return {
                'success': False,
                'error': f"{file_type}不存在: {file_path}",
                'errors': tracker.errors
            }
    
    tracker.log_progress('文件验证', 5, "文件存在性检查通过")
    
    # 处理多模态文件
    try:
        tracker.log_progress('文件处理', 10, "开始处理PDF文件...")
        
        # PDF直接使用Vision API处理，不提取文本
        question_mm = process_multimodal_file(question_pdf, prefer_vision=True)
        tracker.log_progress('文件处理', 20, f"题目文件处理完成 - 类型: {question_mm['modality_type']}")
        
        answer_mm = process_multimodal_file(answer_pdf, prefer_vision=True)
        tracker.log_progress('文件处理', 30, f"学生作答处理完成 - 类型: {answer_mm['modality_type']}")
        
        marking_mm = None
        if marking_pdf:
            marking_mm = process_multimodal_file(marking_pdf, prefer_vision=True)
            tracker.log_progress('文件处理', 40, f"批改标准处理完成 - 类型: {marking_mm['modality_type']}")
        
        # 静默处理PDF类型，不显示转换提示
        # PDF会根据内容自动选择文本或图片模式，无需警告
        
    except Exception as e:
        tracker.log_error('文件处理', f"文件处理失败: {str(e)}", {'exception': str(e)})
        return {
            'success': False,
            'error': f"文件处理失败: {str(e)}",
            'errors': tracker.errors
        }
    
    # 生成任务ID
    task_id = f"pdf_correction_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    user_id = "batch_user"
    
    tracker.log_progress('工作流初始化', 50, f"任务ID: {task_id}")
    
    # 准备文件列表
    question_files = [question_pdf]
    answer_files = [answer_pdf]
    marking_files = [marking_pdf] if marking_pdf else []
    
    # 运行多模态批改工作流
    try:
        tracker.log_progress('工作流执行', 55, "启动LangGraph多模态工作流...")
        
        # 获取工作流实例用于监控
        workflow = get_multimodal_workflow()
        
        # 创建初始状态
        from functions.langgraph.state import GradingState
        # 重要：确保文件正确分离
        # question_files: 题目文件（如果题目和答案在同一文件，则使用答案文件作为题目参考）
        # answer_files: 学生作答文件
        # marking_files: 批改标准文件
        
        logger.info(f"📋 文件隔离检查:")
        logger.info(f"  题目文件: {question_files}")
        logger.info(f"  学生作答: {answer_files}")
        logger.info(f"  批改标准: {marking_files}")
        
        initial_state = GradingState(
            task_id=task_id,
            user_id=user_id,
            assignment_id=f"assignment_{task_id}",
            timestamp=datetime.now(),
            question_files=question_files,
            answer_files=answer_files,
            marking_files=marking_files,
            images=[],
            strictness_level=strictness_level,
            language=language,
            mode="auto",
            # 初始化其他必要字段
            mm_tokens=[],
            student_info={},
            ocr_results={},
            image_regions={},
            preprocessed_images={},
            rubric_text="",
            rubric_struct={},
            rubric_data={},
            scoring_criteria=[],
            questions=[],
            batches=[],
            evaluations=[],
            scoring_results={},
            detailed_feedback=[],
            annotations=[],
            coordinate_annotations=[],
            error_regions=[],
            cropped_regions=[],
            knowledge_points=[],
            error_analysis={},
            learning_suggestions=[],
            difficulty_assessment={},
            total_score=0.0,
            section_scores={},
            student_evaluation={},
            class_evaluation={},
            export_payload={},
            final_report={},
            export_data={},
            visualization_data={},
            current_step="",
            progress_percentage=0.0,
            completion_status="pending",
            completed_at="",
            errors=[],
            step_results={},
            final_score=0.0,
            grade_level="",
            warnings=[],
            processing_time=0.0,
            model_versions={},
            quality_metrics={},
            # 多模态文件（工作流会自动处理并填充）
            question_multimodal_files=[question_mm] if 'question_mm' in locals() else [],
            answer_multimodal_files=[answer_mm] if 'answer_mm' in locals() else [],
            marking_multimodal_files=[marking_mm] if marking_mm and 'marking_mm' in locals() else [],
            question_understanding=None,
            answer_understanding=None,
            rubric_understanding=None,
            criteria_evaluations=[]
        )
        
        logger.info(f"✅ 初始状态创建完成:")
        logger.info(f"  题目多模态文件数: {len(initial_state.get('question_multimodal_files', []))}")
        logger.info(f"  答案多模态文件数: {len(initial_state.get('answer_multimodal_files', []))}")
        logger.info(f"  批改标准多模态文件数: {len(initial_state.get('marking_multimodal_files', []))}")
        
        # 直接执行工作流（不使用监控任务，避免并发问题）
        # 工作流内部会更新进度，我们直接获取最终结果
        result = await run_multimodal_grading(
            task_id=task_id,
            user_id=user_id,
            question_files=question_files,
            answer_files=answer_files,
            marking_files=marking_files,
            strictness_level=strictness_level,
            language=language
        )
        
        # 手动更新进度（基于结果）
        if result.get('status') == 'completed':
            tracker.log_progress('批改完成', 100, "批改成功完成")
        else:
            tracker.log_progress('批改完成', 90, f"状态: {result.get('status')}")
        
        tracker.log_progress('工作流完成', 100, "批改任务完成")
        
        # 检查结果
        if result.get('status') == 'completed':
            print("\n✅ 批改成功完成！")
            print(f"📊 总分: {result.get('total_score', 'N/A')}")
            print(f"📝 等级: {result.get('grade_level', 'N/A')}")
        else:
            tracker.log_error('工作流执行', f"批改未成功完成，状态: {result.get('status')}")
        
        # 合并追踪信息到结果
        result['tracking'] = {
            'progress_history': tracker.progress_history,
            'errors': tracker.errors,
            'warnings': tracker.warnings,
            'duration_seconds': (datetime.now() - tracker.start_time).total_seconds() if tracker.start_time else 0
        }
        
        return result
        
    except Exception as e:
        tracker.log_error('工作流执行', f"工作流执行失败: {str(e)}", {'exception': str(e)})
        import traceback
        tracker.log_error('工作流执行', f"详细错误信息:\n{traceback.format_exc()}")
        
        return {
            'success': False,
            'error': f"工作流执行失败: {str(e)}",
            'errors': tracker.errors,
            'warnings': tracker.warnings
        }
    finally:
        tracker.print_summary()


async def main():
    """主函数"""
    # 文件路径（相对于项目根目录）
    project_root = Path(__file__).parent.parent
    
    question_pdf = project_root / "学生作答.pdf"
    answer_pdf = project_root / "批改标准.pdf"
    
    # 检查文件是否存在
    if not question_pdf.exists():
        print(f"❌ 错误: 找不到文件 {question_pdf}")
        print("请确保文件存在于项目根目录")
        return
    
    if not answer_pdf.exists():
        print(f"❌ 错误: 找不到文件 {answer_pdf}")
        print("请确保文件存在于项目根目录")
        return
    
    # 注意：根据文件名，看起来"学生作答.pdf"应该是答案文件
    # "批改标准.pdf"应该是评分标准文件
    # 但用户可能把题目和答案都放在了"学生作答.pdf"中
    # 这里我们假设：
    # - question_pdf: 题目（如果有单独的题目文件）
    # - answer_pdf: 学生作答
    # - marking_pdf: 批改标准
    
    # 根据实际文件名调整
    # 如果"学生作答.pdf"包含题目和答案，我们需要调整
    student_answer_pdf = project_root / "学生作答.pdf"
    marking_scheme_pdf = project_root / "批改标准.pdf"
    
    # 如果没有单独的题目文件，我们使用学生作答文件作为题目参考
    # 或者需要从学生作答中提取题目
    question_pdf_path = student_answer_pdf  # 临时使用，实际应该分开
    
    print("📋 文件配置:")
    print(f"  题目文件: {question_pdf_path}")
    print(f"  学生作答: {student_answer_pdf}")
    print(f"  批改标准: {marking_scheme_pdf}")
    print()
    
    # 检查API密钥配置（config.py会自动加载.env文件）
    import os
    from config import OPENROUTER_API_KEY, LLM_API_KEY, LLM_PROVIDER
    
    api_key = OPENROUTER_API_KEY or LLM_API_KEY
    if not api_key:
        print("⚠️  警告: 未检测到API密钥")
        print(f"当前LLM Provider: {LLM_PROVIDER}")
        print("请设置环境变量:")
        print("  - OPENROUTER_API_KEY (如果使用OpenRouter)")
        print("  - LLM_API_KEY (通用)")
        print("可以在 ai_correction/.env 文件或项目根目录 .env 文件中添加")
        print()
        print("继续执行批改（可能会失败）...")
        print()
    else:
        print(f"✅ API密钥已配置 (Provider: {LLM_PROVIDER})")
        print()
    
    # 执行批改
    result = await correct_pdfs_with_tracking(
        question_pdf=str(question_pdf_path),
        answer_pdf=str(student_answer_pdf),
        marking_pdf=str(marking_scheme_pdf) if marking_scheme_pdf.exists() else None,
        strictness_level="中等",
        language="zh"
    )
    
    # 保存结果
    output_dir = project_root / "correction_results"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = output_dir / f"correction_result_{timestamp}.json"
    
    # 保存JSON结果（确保包含所有字段）
    # 打印result的键，用于调试
    logger.info(f"结果字典包含的键: {list(result.keys())}")
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存到: {result_file}")
    
    # 保存文本格式的结果（包含详细信息和Agent协作过程）
    text_result_file = output_dir / f"correction_result_{timestamp}.txt"
    with open(text_result_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("PDF批改结果\n")
        f.write("="*80 + "\n\n")
        
        # 添加批改标准解析结果
        if 'rubric_parsing_result' in result:
            f.write("="*80 + "\n")
            f.write("📋 批改标准解析结果\n")
            f.write("="*80 + "\n\n")
            rubric_result = result['rubric_parsing_result']
            f.write(f"标准ID: {rubric_result.get('rubric_id', 'N/A')}\n")
            f.write(f"总分: {rubric_result.get('total_points', 0)} 分\n")
            f.write(f"评分点数量: {rubric_result.get('criteria_count', 0)}\n\n")
            
            f.write("评分点详情:\n")
            f.write("-"*80 + "\n")
            for i, criterion in enumerate(rubric_result.get('criteria', []), 1):
                f.write(f"\n评分点 {i}:\n")
                f.write(f"  ID: {criterion.get('criterion_id', 'N/A')}\n")
                f.write(f"  题目: {criterion.get('question_id', 'N/A')}\n")
                f.write(f"  描述: {criterion.get('description', 'N/A')}\n")
                f.write(f"  分值: {criterion.get('points', 0)} 分\n")
                
                # 添加详细要求
                if criterion.get('detailed_requirements'):
                    f.write(f"  详细要求: {criterion.get('detailed_requirements')}\n")
                
                # 添加标准答案
                if criterion.get('standard_answer'):
                    f.write(f"  标准答案: {criterion.get('standard_answer')}\n")
                
                # 添加评分细则
                if criterion.get('scoring_criteria'):
                    scoring = criterion.get('scoring_criteria', {})
                    f.write(f"  评分细则:\n")
                    if scoring.get('full_credit'):
                        f.write(f"    满分条件: {scoring.get('full_credit')}\n")
                    if scoring.get('partial_credit'):
                        f.write(f"    部分分条件: {scoring.get('partial_credit')}\n")
                    if scoring.get('no_credit'):
                        f.write(f"    不得分条件: {scoring.get('no_credit')}\n")
                
                # 添加另类解法
                if criterion.get('alternative_methods'):
                    methods = criterion.get('alternative_methods', [])
                    if methods:
                        f.write(f"  另类解法:\n")
                        for method in methods:
                            f.write(f"    - {method}\n")
                
                f.write(f"  评估方法: {criterion.get('evaluation_method', 'N/A')}\n")
                
                if criterion.get('keywords'):
                    f.write(f"  关键词: {', '.join(criterion.get('keywords', []))}\n")
                if criterion.get('required_elements'):
                    f.write(f"  必需元素: {', '.join(criterion.get('required_elements', []))}\n")
                if criterion.get('common_mistakes'):
                    mistakes = criterion.get('common_mistakes', [])
                    if mistakes:
                        f.write(f"  常见错误:\n")
                        for mistake in mistakes:
                            f.write(f"    - {mistake}\n")
            f.write("\n")
        
        # 添加Agent协作过程
        if 'agent_collaboration' in result:
            f.write("="*80 + "\n")
            f.write("🤖 Agent协作过程\n")
            f.write("="*80 + "\n\n")
            collab = result['agent_collaboration']
            
            f.write("1. RubricInterpreterAgent (评分标准解析Agent):\n")
            rubric_info = collab.get('rubric_interpreter', {})
            f.write(f"   状态: {rubric_info.get('status', 'N/A')}\n")
            f.write(f"   提取评分点数量: {rubric_info.get('criteria_extracted', 0)}\n")
            f.write(f"   总分: {rubric_info.get('total_points', 0)} 分\n\n")
            
            f.write("2. QuestionUnderstandingAgent (题目理解Agent):\n")
            question_info = collab.get('question_understanding', {})
            f.write(f"   状态: {question_info.get('status', 'N/A')}\n\n")
            
            f.write("3. AnswerUnderstandingAgent (答案理解Agent):\n")
            answer_info = collab.get('answer_understanding', {})
            f.write(f"   状态: {answer_info.get('status', 'N/A')}\n\n")
            
            f.write("4. GradingWorkerAgent (批改工作Agent):\n")
            grading_info = collab.get('grading_worker', {})
            f.write(f"   状态: {grading_info.get('status', 'N/A')}\n")
            f.write(f"   批改学生数量: {grading_info.get('students_graded', 0)}\n")
            f.write(f"   评估数量: {grading_info.get('evaluations_count', 0)}\n\n")
        
        # 添加批改结果
        f.write("="*80 + "\n")
        f.write("📊 批改结果\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"任务ID: {result.get('task_id', 'N/A')}\n")
        f.write(f"状态: {result.get('status', 'N/A')}\n")
        f.write(f"总分: {result.get('total_score', 'N/A')}\n")
        f.write(f"等级: {result.get('grade_level', 'N/A')}\n\n")
        
        # 添加详细的评分点评估
        criteria_evaluations = result.get('criteria_evaluations', [])
        if criteria_evaluations:
            f.write("="*80 + "\n")
            f.write("📝 详细批改详情（逐题逐项评估）\n")
            f.write("="*80 + "\n\n")
            
            # 按题目分组
            questions = {}
            for eval_item in criteria_evaluations:
                criterion_id = eval_item.get('criterion_id', '')
                # 提取题目编号（如Q1_C1 -> Q1）
                question_id = criterion_id.split('_')[0] if '_' in criterion_id else 'UNKNOWN'
                if question_id not in questions:
                    questions[question_id] = []
                questions[question_id].append(eval_item)
            
            # 按题目顺序输出
            sorted_questions = sorted(questions.items(), key=lambda x: x[0])
            
            for question_id, evals in sorted_questions:
                f.write(f"\n【{question_id}】\n")
                f.write("-"*80 + "\n")
                
            for i, eval_item in enumerate(evals, 1):
                criterion_id = eval_item.get('criterion_id', 'N/A')
                score_earned = eval_item.get('score_earned', 0)
                max_score = eval_item.get('max_score', 0)
                satisfaction = eval_item.get('satisfaction_level', 'N/A')
                student_work = eval_item.get('student_work', '')
                justification = eval_item.get('justification', '')
                matched_criterion = eval_item.get('matched_criterion', '')
                feedback = eval_item.get('feedback', '')
                evidence = eval_item.get('evidence', [])
                
                f.write(f"\n评分点 {i} ({criterion_id}): {score_earned}/{max_score}分 - {satisfaction}\n")
                if student_work:
                    f.write(f"  学生作答: {student_work}\n")
                if matched_criterion:
                    f.write(f"  符合标准: {matched_criterion}\n")
                f.write(f"  评分理由: {justification}\n")
                if feedback and feedback != "无":
                    f.write(f"  反馈意见: {feedback}\n")
                if evidence:
                    f.write(f"  证据:\n")
                    for ev in evidence:
                        f.write(f"    - {ev}\n")
                f.write("\n")
        else:
            f.write("暂无详细批改详情\n")
        
        f.write("\n详细反馈:\n")
        f.write("-"*80 + "\n")
        feedback_list = result.get('detailed_feedback', [])
        if feedback_list:
            for i, feedback in enumerate(feedback_list, 1):
                if isinstance(feedback, dict):
                    f.write(f"{i}. {feedback.get('content', str(feedback))}\n")
                else:
                    f.write(f"{i}. {feedback}\n")
        else:
            f.write("暂无详细反馈\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("错误和警告\n")
        f.write("="*80 + "\n\n")
        
        errors = result.get('errors', [])
        if errors:
            f.write("错误:\n")
            for i, error in enumerate(errors, 1):
                if isinstance(error, dict):
                    f.write(f"  {i}. [{error.get('step', 'unknown')}] {error.get('error', str(error))}\n")
                else:
                    f.write(f"  {i}. {error}\n")
        else:
            f.write("无错误\n")
        
        warnings = result.get('warnings', [])
        if warnings:
            f.write("\n警告:\n")
            for i, warning in enumerate(warnings, 1):
                if isinstance(warning, dict):
                    f.write(f"  {i}. [{warning.get('step', 'unknown')}] {warning.get('warning', str(warning))}\n")
                else:
                    f.write(f"  {i}. {warning}\n")
        else:
            f.write("\n无警告\n")
    
    print(f"📄 文本结果已保存到: {text_result_file}")
    
    # 打印关键结果
    print("\n" + "="*80)
    print("📊 批改结果摘要")
    print("="*80)
    print(f"状态: {result.get('status', 'N/A')}")
    print(f"总分: {result.get('total_score', 'N/A')}")
    print(f"等级: {result.get('grade_level', 'N/A')}")
    
    if result.get('errors'):
        print(f"\n❌ 发现 {len(result['errors'])} 个错误")
    if result.get('warnings'):
        print(f"⚠️  发现 {len(result['warnings'])} 个警告")
    
    print("="*80)


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())

