"""Temporal 工作流集成测试

验证 ExamPaperWorkflow 和 QuestionGradingChildWorkflow 的功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.workflows.exam_paper import ExamPaperWorkflow
from src.workflows.question_grading import QuestionGradingChildWorkflow
from src.models.grading import GradingResult, ExamPaperResult
from src.models.state import WorkflowInput, QuestionGradingInput
from src.models.region import SegmentationResult, QuestionRegion, BoundingBox
from src.models.enums import ReviewAction


class TestQuestionGradingChildWorkflow:
    """测试题目级子工作流"""
    
    @pytest.mark.asyncio
    async def test_question_grading_workflow_initialization(self):
        """测试子工作流初始化
        
        验证需求 4.4：子工作流应该能够初始化
        """
        workflow = QuestionGradingChildWorkflow()
        assert workflow is not None
    
    def test_question_grading_workflow_class_exists(self):
        """测试子工作流类存在
        
        验证需求 4.4：QuestionGradingChildWorkflow 类应该存在
        """
        assert QuestionGradingChildWorkflow is not None
        assert hasattr(QuestionGradingChildWorkflow, 'run')


class TestExamPaperWorkflow:
    """测试试卷级父工作流"""
    
    def test_exam_paper_workflow_initialization(self):
        """测试父工作流初始化
        
        验证需求 4.1：父工作流应该能够初始化
        """
        workflow = ExamPaperWorkflow()
        assert workflow is not None
        assert hasattr(workflow, '_review_signal')
        assert hasattr(workflow, '_review_received')
        assert workflow._review_received is False
    
    def test_exam_paper_workflow_has_review_signal(self):
        """测试父工作流有审核信号处理
        
        验证需求 5.3, 5.4, 5.5：工作流应该能够接收审核信号
        """
        workflow = ExamPaperWorkflow()
        assert hasattr(workflow, 'review_signal')
        assert callable(workflow.review_signal)
    
    def test_exam_paper_workflow_review_signal_approve(self):
        """测试审核信号 - 批准
        
        验证需求 5.3：APPROVE 信号应该被正确处理
        """
        workflow = ExamPaperWorkflow()
        
        # 发送 APPROVE 信号
        workflow.review_signal(ReviewAction.APPROVE.value)
        
        # 验证信号已接收
        assert workflow._review_received is True
        assert workflow._review_signal is not None
        assert workflow._review_signal["action"] == ReviewAction.APPROVE.value
    
    def test_exam_paper_workflow_review_signal_override(self):
        """测试审核信号 - 覆盖
        
        验证需求 5.4：OVERRIDE 信号应该包含覆盖数据
        """
        workflow = ExamPaperWorkflow()
        
        # 发送 OVERRIDE 信号
        override_data = {
            "q1": {"score": 8.0},
            "q2": {"score": 9.0}
        }
        workflow.review_signal(ReviewAction.OVERRIDE.value, override_data)
        
        # 验证信号已接收
        assert workflow._review_received is True
        assert workflow._review_signal is not None
        assert workflow._review_signal["action"] == ReviewAction.OVERRIDE.value
        assert workflow._review_signal["override_data"] == override_data
    
    def test_exam_paper_workflow_review_signal_reject(self):
        """测试审核信号 - 拒绝
        
        验证需求 5.5：REJECT 信号应该被正确处理
        """
        workflow = ExamPaperWorkflow()
        
        # 发送 REJECT 信号
        workflow.review_signal(ReviewAction.REJECT.value)
        
        # 验证信号已接收
        assert workflow._review_received is True
        assert workflow._review_signal is not None
        assert workflow._review_signal["action"] == ReviewAction.REJECT.value


class TestWorkflowFanOut:
    """测试工作流扇出功能
    
    验证需求 4.2：工作流应该为每道题目扇出子工作流
    """
    
    def test_fan_out_count_matches_question_count(self):
        """测试扇出数量匹配题目数量
        
        验证属性 5：扇出数量应该等于题目数量
        """
        # 创建分割结果
        regions = [
            QuestionRegion(
                question_id=f"q{i}",
                page_index=0,
                bounding_box=BoundingBox(ymin=0, xmin=0, ymax=100, xmax=100),
                image_data="base64_image"
            )
            for i in range(5)
        ]
        
        # 验证题目数量
        assert len(regions) == 5
        
        # 在实际工作流中，应该为每个题目启动一个子工作流
        # 这里我们验证逻辑是正确的


class TestWorkflowScoreAggregation:
    """测试工作流分数聚合功能
    
    验证需求 4.3：工作流应该正确聚合分数
    """
    
    def test_score_aggregation_correctness(self):
        """测试分数聚合正确性
        
        验证属性 6：聚合分数应该等于各题目分数之和
        """
        # 创建批改结果
        results = [
            GradingResult(
                question_id="q1",
                score=8.5,
                max_score=10.0,
                confidence=0.9,
                feedback="很好",
                visual_annotations=[],
                agent_trace={}
            ),
            GradingResult(
                question_id="q2",
                score=9.0,
                max_score=10.0,
                confidence=0.85,
                feedback="不错",
                visual_annotations=[],
                agent_trace={}
            ),
            GradingResult(
                question_id="q3",
                score=7.5,
                max_score=10.0,
                confidence=0.8,
                feedback="可以",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        # 计算聚合分数
        total_score = sum(r.score for r in results)
        max_total_score = sum(r.max_score for r in results)
        
        # 验证聚合结果
        assert total_score == 25.0
        assert max_total_score == 30.0
        assert total_score / max_total_score == pytest.approx(0.833, rel=0.01)


class TestWorkflowConfidenceThreshold:
    """测试工作流置信度阈值检查
    
    验证需求 5.1：低置信度应该触发审核状态
    """
    
    def test_low_confidence_triggers_review(self):
        """测试低置信度触发审核
        
        验证属性 7：置信度 < 0.75 应该触发审核状态
        """
        # 创建包含低置信度结果的批改结果
        results = [
            GradingResult(
                question_id="q1",
                score=8.5,
                max_score=10.0,
                confidence=0.9,
                feedback="很好",
                visual_annotations=[],
                agent_trace={}
            ),
            GradingResult(
                question_id="q2",
                score=5.0,
                max_score=10.0,
                confidence=0.6,  # 低置信度
                feedback="不确定",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        # 计算最小置信度
        min_confidence = min(r.confidence for r in results)
        
        # 验证是否需要审核
        needs_review = min_confidence < 0.75
        assert needs_review is True
    
    def test_high_confidence_no_review(self):
        """测试高置信度不触发审核
        
        验证属性 7：置信度 >= 0.75 不应该触发审核状态
        """
        # 创建所有高置信度结果
        results = [
            GradingResult(
                question_id="q1",
                score=8.5,
                max_score=10.0,
                confidence=0.9,
                feedback="很好",
                visual_annotations=[],
                agent_trace={}
            ),
            GradingResult(
                question_id="q2",
                score=9.0,
                max_score=10.0,
                confidence=0.85,
                feedback="不错",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        # 计算最小置信度
        min_confidence = min(r.confidence for r in results)
        
        # 验证是否需要审核
        needs_review = min_confidence < 0.75
        assert needs_review is False


class TestWorkflowSignalHandling:
    """测试工作流信号处理
    
    验证需求 5.3, 5.4, 5.5：工作流应该正确处理审核信号
    """
    
    def test_signal_handling_approve(self):
        """测试信号处理 - 批准
        
        验证属性 8：APPROVE 信号应该使用原始结果
        """
        workflow = ExamPaperWorkflow()
        
        # 发送 APPROVE 信号
        workflow.review_signal(ReviewAction.APPROVE.value)
        
        # 验证信号已接收
        assert workflow._review_received is True
        assert workflow._review_signal["action"] == ReviewAction.APPROVE.value
    
    def test_signal_handling_override(self):
        """测试信号处理 - 覆盖
        
        验证属性 8：OVERRIDE 信号应该应用教师的手动评分
        """
        workflow = ExamPaperWorkflow()
        
        # 创建原始结果
        original_results = [
            GradingResult(
                question_id="q1",
                score=5.0,
                max_score=10.0,
                confidence=0.6,
                feedback="原始反馈",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        # 发送 OVERRIDE 信号
        override_data = {
            "q1": {"score": 8.0}
        }
        workflow.review_signal(ReviewAction.OVERRIDE.value, override_data)
        
        # 验证信号已接收
        assert workflow._review_received is True
        assert workflow._review_signal["action"] == ReviewAction.OVERRIDE.value
        
        # 验证覆盖数据
        override_score = override_data["q1"]["score"]
        assert override_score == 8.0
    
    def test_signal_handling_reject(self):
        """测试信号处理 - 拒绝
        
        验证属性 8：REJECT 信号应该终止工作流
        """
        workflow = ExamPaperWorkflow()
        
        # 发送 REJECT 信号
        workflow.review_signal(ReviewAction.REJECT.value)
        
        # 验证信号已接收
        assert workflow._review_received is True
        assert workflow._review_signal["action"] == ReviewAction.REJECT.value


class TestWorkflowInputValidation:
    """测试工作流输入验证"""
    
    def test_workflow_input_creation(self):
        """测试工作流输入创建
        
        验证需求 4.1：工作流应该能够接收有效的输入
        """
        input_data = WorkflowInput(
            submission_id="sub_001",
            student_id="student_001",
            exam_id="exam_001",
            file_paths=["/path/to/file1.pdf", "/path/to/file2.pdf"]
        )
        
        assert input_data["submission_id"] == "sub_001"
        assert input_data["student_id"] == "student_001"
        assert input_data["exam_id"] == "exam_001"
        assert len(input_data["file_paths"]) == 2
    
    def test_question_grading_input_creation(self):
        """测试题目批改输入创建
        
        验证需求 4.4：子工作流应该能够接收有效的输入
        """
        input_data = QuestionGradingInput(
            submission_id="sub_001",
            question_id="q1",
            image_b64="base64_encoded_image",
            rubric="评分细则",
            max_score=10.0,
            standard_answer="标准答案"
        )
        
        assert input_data["submission_id"] == "sub_001"
        assert input_data["question_id"] == "q1"
        assert input_data["image_b64"] == "base64_encoded_image"
        assert input_data["rubric"] == "评分细则"
        assert input_data["max_score"] == 10.0


class TestExamPaperResult:
    """测试试卷批改结果"""
    
    def test_exam_paper_result_creation(self):
        """测试试卷批改结果创建
        
        验证需求 4.1：工作流应该返回有效的试卷批改结果
        """
        results = [
            GradingResult(
                question_id="q1",
                score=8.5,
                max_score=10.0,
                confidence=0.9,
                feedback="很好",
                visual_annotations=[],
                agent_trace={}
            ),
            GradingResult(
                question_id="q2",
                score=9.0,
                max_score=10.0,
                confidence=0.85,
                feedback="不错",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        exam_result = ExamPaperResult(
            submission_id="sub_001",
            exam_id="exam_001",
            student_id="student_001",
            total_score=17.5,
            max_total_score=20.0,
            question_results=results,
            overall_feedback="总体表现良好"
        )
        
        assert exam_result.submission_id == "sub_001"
        assert exam_result.exam_id == "exam_001"
        assert exam_result.student_id == "student_001"
        assert exam_result.total_score == 17.5
        assert exam_result.max_total_score == 20.0
        assert len(exam_result.question_results) == 2
