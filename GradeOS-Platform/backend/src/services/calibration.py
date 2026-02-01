"""
校准服务

管理教师/学校的个性化评分配置，包括扣分规则、容差设置和措辞模板。
验证：需求 6.1, 6.2, 6.3, 6.4, 6.5
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from src.models.calibration import (
    CalibrationProfile,
    ToleranceRule,
    CalibrationProfileCreateRequest,
    CalibrationProfileUpdateRequest,
)
from src.utils.pool_manager import UnifiedPoolManager


logger = logging.getLogger(__name__)


# 默认校准配置
DEFAULT_DEDUCTION_RULES = {
    "spelling_error": 0.5,
    "calculation_error": 1.0,
    "logic_error": 2.0,
    "incomplete_answer": 1.5,
    "format_error": 0.5,
}

DEFAULT_TOLERANCE_RULES = [
    ToleranceRule(rule_type="numeric", tolerance_value=0.01, description="数值误差容差 ±0.01"),
    ToleranceRule(rule_type="unit", tolerance_value=1.0, description="单位换算容差"),
]

DEFAULT_FEEDBACK_TEMPLATES = {
    "correct": "答案完全正确！",
    "partial_correct": "答案部分正确，{reason}",
    "incorrect": "答案错误，{reason}",
    "missing_steps": "解题步骤不完整，缺少{missing_parts}",
    "calculation_error": "计算错误，正确答案应为{correct_answer}",
}


class CalibrationService:
    """
    校准服务

    管理教师/学校的个性化评分配置。
    验证：需求 6.1, 6.2, 6.3, 6.4, 6.5
    """

    def __init__(self, pool_manager: Optional[UnifiedPoolManager] = None):
        """
        初始化校准服务

        Args:
            pool_manager: 数据库连接池管理器
        """
        self.pool_manager = pool_manager or UnifiedPoolManager()
        logger.info("CalibrationService 服务初始化完成")

    async def get_or_create_profile(
        self, teacher_id: str, school_id: Optional[str] = None
    ) -> CalibrationProfile:
        """
        获取或创建教师校准配置

        验证：需求 6.1
        属性 13：校准配置默认创建

        如果教师首次使用系统，自动创建包含默认值的校准配置。

        Args:
            teacher_id: 教师ID
            school_id: 学校ID（可选）

        Returns:
            校准配置
        """
        try:
            # 尝试获取现有配置
            profile = await self._get_profile_by_teacher_id(teacher_id)

            if profile:
                logger.info(f"获取到教师 {teacher_id} 的现有校准配置")
                return profile

            # 不存在则创建默认配置
            logger.info(f"教师 {teacher_id} 首次使用，创建默认校准配置")

            profile_id = str(uuid4())

            async with self.pool_manager.pg_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO calibration_profiles (
                        profile_id, teacher_id, school_id,
                        deduction_rules, tolerance_rules, feedback_templates,
                        strictness_level
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    profile_id,
                    teacher_id,
                    school_id,
                    json.dumps(DEFAULT_DEDUCTION_RULES),
                    json.dumps([rule.model_dump() for rule in DEFAULT_TOLERANCE_RULES]),
                    json.dumps(DEFAULT_FEEDBACK_TEMPLATES),
                    0.5,  # 默认严格程度
                )

            # 返回创建的配置
            profile = await self._get_profile_by_teacher_id(teacher_id)
            logger.info(f"成功创建教师 {teacher_id} 的默认校准配置")
            return profile

        except Exception as e:
            logger.error(f"获取或创建校准配置失败: {e}")
            raise

    async def _get_profile_by_teacher_id(self, teacher_id: str) -> Optional[CalibrationProfile]:
        """根据教师ID获取校准配置"""
        try:
            async with self.pool_manager.pg_connection() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT 
                        profile_id, teacher_id, school_id,
                        deduction_rules, tolerance_rules, feedback_templates,
                        strictness_level, created_at, updated_at
                    FROM calibration_profiles
                    WHERE teacher_id = $1
                    """,
                    teacher_id,
                )

                if not row:
                    return None

                # 解析 JSONB 字段
                tolerance_rules = [ToleranceRule(**rule) for rule in row["tolerance_rules"]]

                return CalibrationProfile(
                    profile_id=str(row["profile_id"]),
                    teacher_id=str(row["teacher_id"]),
                    school_id=str(row["school_id"]) if row["school_id"] else None,
                    deduction_rules=row["deduction_rules"],
                    tolerance_rules=tolerance_rules,
                    feedback_templates=row["feedback_templates"],
                    strictness_level=float(row["strictness_level"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

        except Exception as e:
            logger.error(f"获取校准配置失败: {e}")
            return None

    async def update_profile(self, teacher_id: str, updates: Dict[str, Any]) -> CalibrationProfile:
        """
        更新校准配置

        验证：需求 6.2
        属性 14：校准配置更新一致性

        Args:
            teacher_id: 教师ID
            updates: 更新字段字典

        Returns:
            更新后的校准配置

        Raises:
            ValueError: 如果配置不存在
        """
        try:
            # 确保配置存在
            profile = await self._get_profile_by_teacher_id(teacher_id)
            if not profile:
                raise ValueError(f"教师 {teacher_id} 的校准配置不存在")

            # 构建更新语句
            update_fields = []
            params = []
            param_index = 1

            if "deduction_rules" in updates:
                update_fields.append(f"deduction_rules = ${param_index}::jsonb")
                params.append(json.dumps(updates["deduction_rules"]))
                param_index += 1

            if "tolerance_rules" in updates:
                # 转换为字典列表
                tolerance_rules_data = [
                    rule.model_dump() if isinstance(rule, ToleranceRule) else rule
                    for rule in updates["tolerance_rules"]
                ]
                update_fields.append(f"tolerance_rules = ${param_index}::jsonb")
                params.append(json.dumps(tolerance_rules_data))
                param_index += 1

            if "feedback_templates" in updates:
                update_fields.append(f"feedback_templates = ${param_index}::jsonb")
                params.append(json.dumps(updates["feedback_templates"]))
                param_index += 1

            if "strictness_level" in updates:
                update_fields.append(f"strictness_level = ${param_index}")
                params.append(float(updates["strictness_level"]))
                param_index += 1

            if not update_fields:
                logger.warning("没有需要更新的字段")
                return profile

            # 添加 teacher_id 参数
            params.append(teacher_id)

            # 执行更新
            update_sql = f"""
                UPDATE calibration_profiles
                SET {', '.join(update_fields)}
                WHERE teacher_id = ${param_index}
            """

            async with self.pool_manager.pg_connection() as conn:
                await conn.execute(update_sql, *params)

            # 返回更新后的配置
            updated_profile = await self._get_profile_by_teacher_id(teacher_id)
            logger.info(f"成功更新教师 {teacher_id} 的校准配置")
            return updated_profile

        except ValueError as e:
            logger.error(f"更新校准配置失败: {e}")
            raise
        except Exception as e:
            logger.error(f"更新校准配置失败: {e}")
            raise

    def apply_tolerance(
        self, student_answer: str, standard_answer: str, profile: CalibrationProfile
    ) -> bool:
        """
        应用容差规则判断答案是否等价

        验证：需求 6.4

        Args:
            student_answer: 学生答案
            standard_answer: 标准答案
            profile: 校准配置

        Returns:
            是否等价
        """
        try:
            # 精确匹配
            if student_answer.strip() == standard_answer.strip():
                return True

            # 应用容差规则
            for rule in profile.tolerance_rules:
                if rule.rule_type == "numeric":
                    # 数值容差
                    if self._check_numeric_tolerance(
                        student_answer, standard_answer, rule.tolerance_value
                    ):
                        return True

                elif rule.rule_type == "unit":
                    # 单位换算容差
                    if self._check_unit_tolerance(student_answer, standard_answer):
                        return True

                elif rule.rule_type == "synonym":
                    # 同义词容差
                    if self._check_synonym_tolerance(student_answer, standard_answer):
                        return True

            return False

        except Exception as e:
            logger.warning(f"应用容差规则失败: {e}")
            return False

    def _check_numeric_tolerance(
        self, student_answer: str, standard_answer: str, tolerance: float
    ) -> bool:
        """检查数值容差"""
        try:
            student_val = float(student_answer.strip())
            standard_val = float(standard_answer.strip())
            return abs(student_val - standard_val) <= tolerance
        except (ValueError, TypeError):
            return False

    def _check_unit_tolerance(self, student_answer: str, standard_answer: str) -> bool:
        """检查单位换算容差（简化实现）"""
        # TODO: 实现完整的单位换算逻辑
        # 这里只做简单的单位识别
        common_units = {
            "m": ["米", "meter", "m"],
            "cm": ["厘米", "centimeter", "cm"],
            "kg": ["千克", "kilogram", "kg"],
            "g": ["克", "gram", "g"],
        }
        return False

    def _check_synonym_tolerance(self, student_answer: str, standard_answer: str) -> bool:
        """检查同义词容差（简化实现）"""
        # TODO: 实现完整的同义词匹配逻辑
        # 这里只做简单的相似度检查
        return False

    def generate_feedback(
        self, scenario: str, context: Dict[str, Any], profile: CalibrationProfile
    ) -> str:
        """
        使用模板生成评语

        验证：需求 6.5

        Args:
            scenario: 场景名称（如 'partial_correct', 'incorrect'）
            context: 上下文变量字典
            profile: 校准配置

        Returns:
            生成的评语
        """
        try:
            # 获取模板
            template = profile.feedback_templates.get(scenario)

            if not template:
                # 使用默认模板
                template = DEFAULT_FEEDBACK_TEMPLATES.get(scenario, "评分完成")

            # 填充模板
            feedback = template.format(**context)
            return feedback

        except Exception as e:
            logger.warning(f"生成评语失败: {e}")
            return "评分完成"

    async def get_profile_by_id(self, profile_id: str) -> Optional[CalibrationProfile]:
        """根据配置ID获取校准配置"""
        try:
            async with self.pool_manager.pg_connection() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT 
                        profile_id, teacher_id, school_id,
                        deduction_rules, tolerance_rules, feedback_templates,
                        strictness_level, created_at, updated_at
                    FROM calibration_profiles
                    WHERE profile_id = $1
                    """,
                    profile_id,
                )

                if not row:
                    return None

                tolerance_rules = [ToleranceRule(**rule) for rule in row["tolerance_rules"]]

                return CalibrationProfile(
                    profile_id=str(row["profile_id"]),
                    teacher_id=str(row["teacher_id"]),
                    school_id=str(row["school_id"]) if row["school_id"] else None,
                    deduction_rules=row["deduction_rules"],
                    tolerance_rules=tolerance_rules,
                    feedback_templates=row["feedback_templates"],
                    strictness_level=float(row["strictness_level"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

        except Exception as e:
            logger.error(f"获取校准配置失败: {e}")
            return None
