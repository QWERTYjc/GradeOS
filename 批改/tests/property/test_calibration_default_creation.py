"""
属性测试：校准配置默认创建

验证：需求 6.1
属性 13：校准配置默认创建

测试策略：
- 对于任意首次使用系统的教师，应自动创建包含默认值的校准配置
- 配置应包含默认的扣分规则、容差规则、评语模板和严格程度

注意：这些测试需要 PostgreSQL 数据库。如果数据库不可用，测试将被跳过。
可以通过设置环境变量 SKIP_DB_TESTS=true 来跳过这些测试。
"""

import pytest
import asyncio
import sys
import os
from hypothesis import given, strategies as st, settings, Phase
from uuid import uuid4

from src.services.calibration import CalibrationService
from src.utils.pool_manager import UnifiedPoolManager


# Windows 平台需要使用 SelectorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)
settings.load_profile("ci")


# 检查是否应该跳过数据库测试
SKIP_DB_TESTS = os.getenv("SKIP_DB_TESTS", "true").lower() == "true"
skip_if_no_db = pytest.mark.skipif(
    SKIP_DB_TESTS,
    reason="数据库测试已禁用 (SKIP_DB_TESTS=true)"
)


@pytest.fixture
async def clean_database():
    """清理测试数据"""
    pool_manager = UnifiedPoolManager.get_instance_sync()
    if not pool_manager.is_initialized:
        await pool_manager.initialize()
    async with pool_manager.pg_connection() as conn:
        await conn.execute("DELETE FROM calibration_profiles WHERE teacher_id LIKE 'test-%'")
    yield
    # 测试后再次清理
    async with pool_manager.pg_connection() as conn:
        await conn.execute("DELETE FROM calibration_profiles WHERE teacher_id LIKE 'test-%'")


@pytest.mark.asyncio
@skip_if_no_db
@given(
    teacher_suffix=st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
        min_size=1,
        max_size=20
    )
)
@settings(max_examples=50, deadline=5000)
async def test_calibration_default_creation(teacher_suffix: str, clean_database):
    """
    **Feature: self-evolving-grading, Property 13: 校准配置默认创建**
    **Validates: Requirements 6.1**
    
    属性：对于任意首次使用系统的教师，应自动创建包含默认值的校准配置
    
    验证点：
    1. 配置应被成功创建
    2. 配置应包含默认的扣分规则
    3. 配置应包含默认的容差规则
    4. 配置应包含默认的评语模板
    5. 严格程度应为默认值 0.5
    """
    # 生成唯一的教师ID
    teacher_id = f"test-{teacher_suffix}-{uuid4()}"
    
    # 创建服务
    pool_manager = UnifiedPoolManager.get_instance_sync()
    if not pool_manager.is_initialized:
        await pool_manager.initialize()
    service = CalibrationService(pool_manager=pool_manager)
    
    try:
        # 获取或创建配置（首次使用）
        profile = await service.get_or_create_profile(teacher_id=teacher_id)
        
        # 验证点 1：配置应被成功创建
        assert profile is not None, "配置应被成功创建"
        assert profile.teacher_id == teacher_id, "教师ID应匹配"
        
        # 验证点 2：配置应包含默认的扣分规则
        assert len(profile.deduction_rules) > 0, "应包含默认扣分规则"
        assert "spelling_error" in profile.deduction_rules, "应包含拼写错误扣分规则"
        assert "calculation_error" in profile.deduction_rules, "应包含计算错误扣分规则"
        assert "logic_error" in profile.deduction_rules, "应包含逻辑错误扣分规则"
        
        # 验证点 3：配置应包含默认的容差规则
        assert len(profile.tolerance_rules) > 0, "应包含默认容差规则"
        assert any(
            rule.rule_type == "numeric" for rule in profile.tolerance_rules
        ), "应包含数值容差规则"
        
        # 验证点 4：配置应包含默认的评语模板
        assert len(profile.feedback_templates) > 0, "应包含默认评语模板"
        assert "correct" in profile.feedback_templates, "应包含正确答案模板"
        assert "incorrect" in profile.feedback_templates, "应包含错误答案模板"
        
        # 验证点 5：严格程度应为默认值 0.5
        assert profile.strictness_level == 0.5, "严格程度应为默认值 0.5"
        
        # 验证幂等性：再次调用应返回相同配置
        profile2 = await service.get_or_create_profile(teacher_id=teacher_id)
        assert profile2.profile_id == profile.profile_id, "再次调用应返回相同配置"
        
    finally:
        # 清理测试数据
        async with pool_manager.pg_connection() as conn:
            await conn.execute(
                "DELETE FROM calibration_profiles WHERE teacher_id = $1",
                teacher_id
            )


@pytest.mark.asyncio
@skip_if_no_db
async def test_calibration_default_creation_with_school():
    """
    测试带学校ID的默认配置创建
    
    验证：需求 6.1
    """
    teacher_id = f"test-teacher-{uuid4()}"
    school_id = f"test-school-{uuid4()}"
    
    pool_manager = UnifiedPoolManager.get_instance_sync()
    if not pool_manager.is_initialized:
        await pool_manager.initialize()
    service = CalibrationService(pool_manager=pool_manager)
    
    try:
        # 创建配置
        profile = await service.get_or_create_profile(
            teacher_id=teacher_id,
            school_id=school_id
        )
        
        # 验证
        assert profile is not None
        assert profile.teacher_id == teacher_id
        assert profile.school_id == school_id
        assert len(profile.deduction_rules) > 0
        assert len(profile.tolerance_rules) > 0
        assert len(profile.feedback_templates) > 0
        
    finally:
        # 清理
        async with pool_manager.pg_connection() as conn:
            await conn.execute(
                "DELETE FROM calibration_profiles WHERE teacher_id = $1",
                teacher_id
            )


@pytest.mark.asyncio
@skip_if_no_db
async def test_calibration_default_values():
    """
    测试默认配置的具体值
    
    验证：需求 6.1
    """
    teacher_id = f"test-teacher-{uuid4()}"
    
    pool_manager = UnifiedPoolManager.get_instance_sync()
    if not pool_manager.is_initialized:
        await pool_manager.initialize()
    service = CalibrationService(pool_manager=pool_manager)
    
    try:
        # 创建配置
        profile = await service.get_or_create_profile(teacher_id=teacher_id)
        
        # 验证默认扣分规则的具体值
        assert profile.deduction_rules["spelling_error"] == 0.5
        assert profile.deduction_rules["calculation_error"] == 1.0
        assert profile.deduction_rules["logic_error"] == 2.0
        
        # 验证默认容差规则
        numeric_rule = next(
            (r for r in profile.tolerance_rules if r.rule_type == "numeric"),
            None
        )
        assert numeric_rule is not None
        assert numeric_rule.tolerance_value == 0.01
        
        # 验证默认评语模板
        assert "答案完全正确" in profile.feedback_templates["correct"]
        assert "{reason}" in profile.feedback_templates["partial_correct"]
        
    finally:
        # 清理
        async with pool_manager.pg_connection() as conn:
            await conn.execute(
                "DELETE FROM calibration_profiles WHERE teacher_id = $1",
                teacher_id
            )
