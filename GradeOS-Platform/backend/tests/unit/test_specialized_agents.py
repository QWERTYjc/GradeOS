"""专业批改智能体单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.agents.specialized import (
    ObjectiveAgent,
    StepwiseAgent,
    EssayAgent,
    LabDesignAgent,
)
from src.agents.pool import AgentPool
from src.models.enums import QuestionType
from src.models.state import ContextPack


# ==================== ObjectiveAgent 测试 ====================

class TestObjectiveAgent:
    """ObjectiveAgent 单元测试"""
    
    def test_agent_type(self):
        """测试智能体类型标识"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            assert agent.agent_type == "objective"
    
    def test_supported_question_types(self):
        """测试支持的题型"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            assert QuestionType.OBJECTIVE in agent.supported_question_types
            assert len(agent.supported_question_types) == 1
    
    def test_can_handle(self):
        """测试 can_handle 方法"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            assert agent.can_handle(QuestionType.OBJECTIVE) is True
            assert agent.can_handle(QuestionType.STEPWISE) is False
            assert agent.can_handle(QuestionType.ESSAY) is False
    
    def test_normalize_answer_choice(self):
        """测试选择题答案标准化"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            
            # 测试选择题答案
            assert agent._normalize_answer("A") == "A"
            assert agent._normalize_answer("a") == "A"
            assert agent._normalize_answer(" B ") == "B"
            assert agent._normalize_answer("C.") == "C"
    
    def test_normalize_answer_true_false(self):
        """测试判断题答案标准化"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            
            # 测试判断题答案 - True 变体
            assert agent._normalize_answer("对") == "TRUE"
            assert agent._normalize_answer("√") == "TRUE"
            assert agent._normalize_answer("T") == "TRUE"
            assert agent._normalize_answer("TRUE") == "TRUE"
            assert agent._normalize_answer("正确") == "TRUE"
            
            # 测试判断题答案 - False 变体
            assert agent._normalize_answer("错") == "FALSE"
            assert agent._normalize_answer("×") == "FALSE"
            assert agent._normalize_answer("X") == "FALSE"
            assert agent._normalize_answer("F") == "FALSE"
            assert agent._normalize_answer("FALSE") == "FALSE"
            assert agent._normalize_answer("错误") == "FALSE"
    
    def test_compare_answers_correct(self):
        """测试答案比对 - 正确情况"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            
            result = agent._compare_answers("A", "A", 5.0)
            assert result["is_correct"] is True
            assert result["score"] == 5.0
    
    def test_compare_answers_incorrect(self):
        """测试答案比对 - 错误情况"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            
            result = agent._compare_answers("A", "B", 5.0)
            assert result["is_correct"] is False
            assert result["score"] == 0.0
    
    def test_build_evidence_chain(self):
        """测试证据链构建"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            
            evidence = agent._build_evidence_chain(
                student_answer="A",
                standard_answer="A",
                answer_location=[100, 200, 300, 400],
                score=5.0,
                max_score=5.0,
                rubric="选择正确答案"
            )
            
            assert len(evidence) == 1
            assert evidence[0]["scoring_point"] == "答案正确性判定"
            assert evidence[0]["image_region"] == [100, 200, 300, 400]
            assert evidence[0]["points_awarded"] == 5.0
    
    def test_generate_feedback_correct(self):
        """测试反馈生成 - 正确"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            
            feedback = agent._generate_feedback("A", "A", True)
            assert "正确" in feedback
            assert "A" in feedback
    
    def test_generate_feedback_incorrect(self):
        """测试反馈生成 - 错误"""
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: None):
            agent = ObjectiveAgent.__new__(ObjectiveAgent)
            agent._api_key = "test"
            
            feedback = agent._generate_feedback("A", "B", False)
            assert "错误" in feedback
            assert "A" in feedback
            assert "B" in feedback


# ==================== StepwiseAgent 测试 ====================

class TestStepwiseAgent:
    """StepwiseAgent 单元测试"""
    
    def test_agent_type(self):
        """测试智能体类型标识"""
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: None):
            agent = StepwiseAgent.__new__(StepwiseAgent)
            agent._api_key = "test"
            assert agent.agent_type == "stepwise"
    
    def test_supported_question_types(self):
        """测试支持的题型"""
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: None):
            agent = StepwiseAgent.__new__(StepwiseAgent)
            agent._api_key = "test"
            assert QuestionType.STEPWISE in agent.supported_question_types
    
    def test_extract_steps_from_json(self):
        """测试从 JSON 提取步骤"""
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: None):
            agent = StepwiseAgent.__new__(StepwiseAgent)
            agent._api_key = "test"
            
            json_input = json.dumps({
                "steps": [
                    {"step_number": 1, "content": "设 x = 5"},
                    {"step_number": 2, "content": "代入公式"}
                ]
            })
            
            steps = agent.extract_steps(json_input)
            assert len(steps) == 2
            assert steps[0]["step_number"] == 1
    
    def test_extract_steps_from_text(self):
        """测试从文本提取步骤"""
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: None):
            agent = StepwiseAgent.__new__(StepwiseAgent)
            agent._api_key = "test"
            
            text_input = """第一步：设 x = 5
第二步：代入公式 y = 2x + 3
第三步：计算得 y = 13"""
            
            steps = agent.extract_steps(text_input)
            assert len(steps) == 3
    
    def test_extract_steps_empty(self):
        """测试空输入"""
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: None):
            agent = StepwiseAgent.__new__(StepwiseAgent)
            agent._api_key = "test"
            
            steps = agent.extract_steps("")
            assert len(steps) == 0
    
    def test_build_evidence_chain(self):
        """测试证据链构建"""
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: None):
            agent = StepwiseAgent.__new__(StepwiseAgent)
            agent._api_key = "test"
            
            steps = [
                {
                    "step_name": "列方程",
                    "student_work": "x + 5 = 10",
                    "location": [0, 0, 100, 100],
                    "score": 2,
                    "feedback": "正确"
                },
                {
                    "step_name": "求解",
                    "student_work": "x = 5",
                    "location": [100, 0, 200, 100],
                    "score": 3,
                    "feedback": "正确"
                }
            ]
            
            evidence = agent._build_evidence_chain(steps, "计算题评分标准")
            assert len(evidence) == 2
            assert evidence[0]["scoring_point"] == "列方程"
            assert evidence[0]["points_awarded"] == 2


# ==================== EssayAgent 测试 ====================

class TestEssayAgent:
    """EssayAgent 单元测试"""
    
    def test_agent_type(self):
        """测试智能体类型标识"""
        with patch.object(EssayAgent, '__init__', lambda x, **kwargs: None):
            agent = EssayAgent.__new__(EssayAgent)
            agent._api_key = "test"
            assert agent.agent_type == "essay"
    
    def test_supported_question_types(self):
        """测试支持的题型"""
        with patch.object(EssayAgent, '__init__', lambda x, **kwargs: None):
            agent = EssayAgent.__new__(EssayAgent)
            agent._api_key = "test"
            assert QuestionType.ESSAY in agent.supported_question_types
    
    def test_build_evidence_chain(self):
        """测试证据链构建"""
        with patch.object(EssayAgent, '__init__', lambda x, **kwargs: None):
            agent = EssayAgent.__new__(EssayAgent)
            agent._api_key = "test"
            
            dimension_scores = [
                {
                    "dimension": "内容",
                    "evidence": "观点明确，论据充分",
                    "score": 8,
                    "feedback": "内容丰富"
                },
                {
                    "dimension": "结构",
                    "evidence": "层次清晰",
                    "score": 6,
                    "feedback": "结构合理"
                }
            ]
            
            evidence = agent._build_evidence_chain(dimension_scores, "作文评分标准")
            assert len(evidence) == 2
            assert evidence[0]["scoring_point"] == "内容"
            assert evidence[0]["points_awarded"] == 8
    
    def test_generate_feedback_with_highlights(self):
        """测试带亮点的反馈生成"""
        with patch.object(EssayAgent, '__init__', lambda x, **kwargs: None):
            agent = EssayAgent.__new__(EssayAgent)
            agent._api_key = "test"
            
            scoring_result = {
                "grade_level": "B",
                "overall_comment": "整体不错",
                "highlights": [{"reason": "论点清晰"}],
                "issues": [{"suggestion": "可以增加更多例子"}]
            }
            
            feedback = agent._generate_feedback(scoring_result)
            assert "B" in feedback
            assert "亮点" in feedback
            assert "改进" in feedback


# ==================== LabDesignAgent 测试 ====================

class TestLabDesignAgent:
    """LabDesignAgent 单元测试"""
    
    def test_agent_type(self):
        """测试智能体类型标识"""
        with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: None):
            agent = LabDesignAgent.__new__(LabDesignAgent)
            agent._api_key = "test"
            assert agent.agent_type == "lab_design"
    
    def test_supported_question_types(self):
        """测试支持的题型"""
        with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: None):
            agent = LabDesignAgent.__new__(LabDesignAgent)
            agent._api_key = "test"
            assert QuestionType.LAB_DESIGN in agent.supported_question_types
    
    def test_build_evidence_chain(self):
        """测试证据链构建"""
        with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: None):
            agent = LabDesignAgent.__new__(LabDesignAgent)
            agent._api_key = "test"
            
            dimension_scores = [
                {
                    "dimension": "实验目的",
                    "evidence": "目的明确",
                    "score": 2,
                    "feedback": "表述清晰"
                },
                {
                    "dimension": "实验步骤",
                    "evidence": "步骤完整",
                    "score": 5,
                    "feedback": "可操作性强"
                }
            ]
            
            evidence = agent._build_evidence_chain(dimension_scores, "实验设计评分标准")
            assert len(evidence) == 2
            assert evidence[0]["scoring_point"] == "实验目的"
    
    def test_build_visual_annotations(self):
        """测试视觉标注构建"""
        with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: None):
            agent = LabDesignAgent.__new__(LabDesignAgent)
            agent._api_key = "test"
            
            vision_analysis = {
                "components": {
                    "purpose": {"is_present": True, "location": [0, 0, 100, 100]},
                    "principle": {"is_present": True, "location": [100, 0, 200, 100]},
                    "materials": {"is_present": False}
                }
            }
            
            annotations = agent._build_visual_annotations(vision_analysis, {})
            assert len(annotations) == 2  # 只有 is_present=True 的
    
    def test_generate_feedback_with_errors(self):
        """测试带科学性错误的反馈生成"""
        with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: None):
            agent = LabDesignAgent.__new__(LabDesignAgent)
            agent._api_key = "test"
            
            scoring_result = {
                "overall_comment": "方案基本完整",
                "strengths": ["目的明确"],
                "weaknesses": ["变量控制不够严格"],
                "improvement_suggestions": ["增加对照组"]
            }
            
            validation_result = {
                "scientific_errors": [
                    {"error": "缺少对照实验", "severity": "critical", "suggestion": "设置对照组"}
                ]
            }
            
            feedback = agent._generate_feedback(scoring_result, validation_result)
            assert "优点" in feedback
            assert "改进" in feedback
            assert "科学性问题" in feedback


# ==================== AgentPool 集成测试 ====================

class TestAgentPoolIntegration:
    """AgentPool 与专业智能体集成测试"""
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    def test_register_all_agents(self):
        """测试注册所有专业智能体"""
        pool = AgentPool()
        
        # 使用 mock 避免实际初始化 LLM
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
                with patch.object(EssayAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
                    with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
                        pool.register_agent(ObjectiveAgent())
                        pool.register_agent(StepwiseAgent())
                        pool.register_agent(EssayAgent())
                        pool.register_agent(LabDesignAgent())
        
        assert len(pool) == 4
        assert "objective" in pool.list_agents()
        assert "stepwise" in pool.list_agents()
        assert "essay" in pool.list_agents()
        assert "lab_design" in pool.list_agents()
    
    def test_get_agent_by_question_type(self):
        """测试按题型获取智能体"""
        pool = AgentPool()
        
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            pool.register_agent(ObjectiveAgent())
        
        agent = pool.get_agent(QuestionType.OBJECTIVE)
        assert agent.agent_type == "objective"
    
    def test_has_agent_for_all_types(self):
        """测试所有题型都有对应智能体"""
        pool = AgentPool()
        
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
                with patch.object(EssayAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
                    with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
                        pool.register_agent(ObjectiveAgent())
                        pool.register_agent(StepwiseAgent())
                        pool.register_agent(EssayAgent())
                        pool.register_agent(LabDesignAgent())
        
        assert pool.has_agent_for(QuestionType.OBJECTIVE)
        assert pool.has_agent_for(QuestionType.STEPWISE)
        assert pool.has_agent_for(QuestionType.ESSAY)
        assert pool.has_agent_for(QuestionType.LAB_DESIGN)
        assert not pool.has_agent_for(QuestionType.UNKNOWN)
