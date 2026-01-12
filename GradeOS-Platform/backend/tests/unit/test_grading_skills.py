"""
GradingSkills 单元测试

验证 Agent Skills 的基本功能：
- Skill 注册和调用
- 日志记录
- 错误处理和重试
- 各个 Skill 方法的基本功能

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.skills.grading_skills import (
    GradingSkills,
    SkillResult,
    SkillError,
    SkillCallLog,
    SkillRegistry,
    get_skill_registry,
    skill,
    create_grading_skills,
)
from src.services.rubric_registry import RubricRegistry, RubricQueryResult
from src.services.question_merger import QuestionMerger
from src.models.grading_models import (
    QuestionRubric,
    ScoringPoint,
    QuestionResult,
    PageGradingResult,
    CrossPageQuestion,
    ScoringPointResult,
)


class TestSkillRegistry:
    """测试 Skill 注册中心"""
    
    def test_register_and_get_skill(self):
        """测试注册和获取 Skill"""
        registry = SkillRegistry()
        
        async def dummy_skill():
            return "test"
        
        registry.register("test_skill", dummy_skill)
        
        assert "test_skill" in registry.list_skills()
        assert registry.get("test_skill") == dummy_skill
    
    def test_list_skills(self):
        """测试列出所有 Skills"""
        registry = SkillRegistry()
        
        registry.register("skill1", lambda: None)
        registry.register("skill2", lambda: None)
        
        skills = registry.list_skills()
        assert "skill1" in skills
        assert "skill2" in skills
    
    def test_add_and_get_logs(self):
        """测试添加和获取日志"""
        registry = SkillRegistry()
        
        log = SkillCallLog(
            skill_name="test",
            timestamp="2024-01-01T00:00:00",
            args={"arg1": "value1"},
            success=True,
            execution_time_ms=100.0
        )
        
        registry.add_log(log)
        logs = registry.get_logs()
        
        assert len(logs) == 1
        assert logs[0].skill_name == "test"
    
    def test_log_limit(self):
        """测试日志数量限制"""
        registry = SkillRegistry()
        registry._max_logs = 5
        
        for i in range(10):
            log = SkillCallLog(
                skill_name=f"skill_{i}",
                timestamp="2024-01-01T00:00:00",
                args={},
                success=True,
                execution_time_ms=100.0
            )
            registry.add_log(log)
        
        logs = registry.get_logs()
        assert len(logs) == 5
        # 应该保留最后5个
        assert logs[0].skill_name == "skill_5"


class TestSkillDecorator:
    """测试 Skill 装饰器"""
    
    @pytest.mark.asyncio
    async def test_skill_decorator_success(self):
        """测试 Skill 装饰器成功执行"""
        @skill(name="test_success", max_retries=0)
        async def test_func(value: int) -> int:
            return value * 2
        
        result = await test_func(value=5)
        
        assert isinstance(result, SkillResult)
        assert result.success is True
        assert result.data == 10
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_skill_decorator_with_retry(self):
        """测试 Skill 装饰器重试机制"""
        call_count = 0
        
        @skill(name="test_retry", max_retries=2, retry_delay=0.01)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = await test_func()
        
        assert result.success is True
        assert result.data == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_skill_decorator_max_retries_exceeded(self):
        """测试 Skill 装饰器超过最大重试次数"""
        @skill(name="test_fail", max_retries=2, retry_delay=0.01)
        async def test_func() -> str:
            raise ValueError("Persistent error")
        
        result = await test_func()
        
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == "ValueError"
        assert "Persistent error" in result.error.message


class TestGradingSkills:
    """测试 GradingSkills 类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.rubric_registry = RubricRegistry(total_score=100.0)
        self.question_merger = QuestionMerger()
        self.skills = GradingSkills(
            rubric_registry=self.rubric_registry,
            question_merger=self.question_merger
        )
        
        # 注册一些测试用的评分标准
        rubric1 = QuestionRubric(
            question_id="1",
            max_score=10.0,
            question_text="测试题目1",
            standard_answer="标准答案1",
            scoring_points=[
                ScoringPoint(description="得分点1", score=5.0),
                ScoringPoint(description="得分点2", score=5.0),
            ]
        )
        rubric2 = QuestionRubric(
            question_id="2",
            max_score=15.0,
            question_text="测试题目2",
            standard_answer="标准答案2",
            scoring_points=[
                ScoringPoint(description="得分点1", score=10.0),
                ScoringPoint(description="得分点2", score=5.0),
            ]
        )
        self.rubric_registry.register_rubrics([rubric1, rubric2])
    
    @pytest.mark.asyncio
    async def test_get_rubric_for_question_exists(self):
        """测试获取存在的题目评分标准"""
        result = await self.skills.get_rubric_for_question(
            question_id="1",
            registry=self.rubric_registry
        )
        
        assert isinstance(result, SkillResult)
        assert result.success is True
        assert result.data is not None
        assert result.data.rubric.question_id == "1"
        assert result.data.rubric.max_score == 10.0
        assert result.data.is_default is False
    
    @pytest.mark.asyncio
    async def test_get_rubric_for_question_not_exists(self):
        """测试获取不存在的题目评分标准（返回默认规则）"""
        result = await self.skills.get_rubric_for_question(
            question_id="999",
            registry=self.rubric_registry
        )
        
        assert result.success is True
        assert result.data.is_default is True
        assert result.data.confidence < 1.0
    
    @pytest.mark.asyncio
    async def test_get_rubric_without_registry(self):
        """测试未设置 Registry 时获取评分标准"""
        skills = GradingSkills()  # 不设置 registry
        
        result = await skills.get_rubric_for_question(question_id="1")
        
        assert result.success is False
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_detect_cross_page_questions(self):
        """测试跨页题目检测"""
        # 创建测试数据：两个连续页面有相同题号
        page1 = PageGradingResult(
            page_index=0,
            question_results=[
                QuestionResult(
                    question_id="1",
                    score=5.0,
                    max_score=10.0,
                    confidence=0.9,
                    page_indices=[0]
                )
            ]
        )
        page2 = PageGradingResult(
            page_index=1,
            question_results=[
                QuestionResult(
                    question_id="1",
                    score=3.0,
                    max_score=10.0,
                    confidence=0.85,
                    page_indices=[1]
                )
            ]
        )
        
        result = await self.skills.detect_cross_page_questions(
            page_results=[page1, page2]
        )
        
        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0].question_id == "1"
        assert 0 in result.data[0].page_indices
        assert 1 in result.data[0].page_indices
    
    @pytest.mark.asyncio
    async def test_detect_cross_page_questions_no_cross_page(self):
        """测试无跨页题目的情况"""
        page1 = PageGradingResult(
            page_index=0,
            question_results=[
                QuestionResult(
                    question_id="1",
                    score=10.0,
                    max_score=10.0,
                    confidence=0.9,
                    page_indices=[0]
                )
            ]
        )
        page2 = PageGradingResult(
            page_index=1,
            question_results=[
                QuestionResult(
                    question_id="2",
                    score=15.0,
                    max_score=15.0,
                    confidence=0.9,
                    page_indices=[1]
                )
            ]
        )
        
        result = await self.skills.detect_cross_page_questions(
            page_results=[page1, page2]
        )
        
        assert result.success is True
        assert len(result.data) == 0
    
    @pytest.mark.asyncio
    async def test_merge_question_results(self):
        """测试合并题目结果"""
        results = [
            QuestionResult(
                question_id="1",
                score=5.0,
                max_score=10.0,
                confidence=0.9,
                feedback="第一部分",
                page_indices=[0],
                scoring_point_results=[
                    ScoringPointResult(
                        scoring_point=ScoringPoint(description="得分点1", score=5.0),
                        awarded=5.0,
                        evidence="正确"
                    )
                ]
            ),
            QuestionResult(
                question_id="1",
                score=3.0,
                max_score=10.0,
                confidence=0.85,
                feedback="第二部分",
                page_indices=[1],
                scoring_point_results=[
                    ScoringPointResult(
                        scoring_point=ScoringPoint(description="得分点2", score=5.0),
                        awarded=3.0,
                        evidence="部分正确"
                    )
                ]
            )
        ]
        
        cross_page_info = CrossPageQuestion(
            question_id="1",
            page_indices=[0, 1],
            confidence=0.9,
            merge_reason="测试合并"
        )
        
        result = await self.skills.merge_question_results(
            results=results,
            cross_page_info=cross_page_info
        )
        
        assert result.success is True
        merged = result.data
        assert merged.question_id == "1"
        assert merged.is_cross_page is True
        assert merged.max_score == 10.0  # 满分只计算一次
        assert merged.score == 8.0  # 5 + 3
        assert 0 in merged.page_indices
        assert 1 in merged.page_indices
    
    @pytest.mark.asyncio
    async def test_merge_question_results_empty(self):
        """测试合并空结果列表"""
        result = await self.skills.merge_question_results(results=[])
        
        assert result.success is False
        assert result.error is not None


class TestSkillCallLog:
    """测试 Skill 调用日志"""
    
    def test_to_dict(self):
        """测试日志序列化"""
        log = SkillCallLog(
            skill_name="test",
            timestamp="2024-01-01T00:00:00",
            args={"arg1": "value1"},
            success=True,
            execution_time_ms=100.0,
            error_message=None,
            retry_count=0
        )
        
        data = log.to_dict()
        
        assert data["skill_name"] == "test"
        assert data["success"] is True
        assert data["execution_time_ms"] == 100.0


class TestSkillError:
    """测试 Skill 错误"""
    
    def test_to_dict(self):
        """测试错误序列化"""
        error = SkillError(
            error_type="ValueError",
            message="Test error",
            details={"key": "value"},
            retry_count=2,
            is_retryable=False
        )
        
        data = error.to_dict()
        
        assert data["error_type"] == "ValueError"
        assert data["message"] == "Test error"
        assert data["retry_count"] == 2
        assert data["is_retryable"] is False


class TestCreateGradingSkills:
    """测试便捷创建函数"""
    
    def test_create_with_defaults(self):
        """测试使用默认参数创建"""
        skills = create_grading_skills()
        
        assert skills is not None
        assert skills.rubric_registry is None
        assert skills.question_merger is not None
    
    def test_create_with_registry(self):
        """测试使用自定义 Registry 创建"""
        registry = RubricRegistry()
        skills = create_grading_skills(rubric_registry=registry)
        
        assert skills.rubric_registry is registry


class TestGlobalSkillRegistry:
    """测试全局 Skill 注册中心"""
    
    def test_get_skill_registry(self):
        """测试获取全局注册中心"""
        registry = get_skill_registry()
        
        assert registry is not None
        assert isinstance(registry, SkillRegistry)
    
    def test_skills_registered_on_import(self):
        """测试 Skills 在导入时自动注册"""
        registry = get_skill_registry()
        skills = registry.list_skills()
        
        # 验证核心 Skills 已注册
        assert "get_rubric_for_question" in skills
        assert "detect_cross_page_questions" in skills
        assert "merge_question_results" in skills
