"""
Agent Skills 模块

提供批改工作流中 Agent 可调用的技能模块，包括：
- 评分标准获取
- 题目编号识别
- 跨页题目检测
- 结果合并

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from .grading_skills import (
    GradingSkills,
    skill,
    SkillResult,
    SkillError,
    get_skill_registry,
)

__all__ = [
    "GradingSkills",
    "skill",
    "SkillResult",
    "SkillError",
    "get_skill_registry",
]
