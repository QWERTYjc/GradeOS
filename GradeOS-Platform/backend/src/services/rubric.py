"""
评分细则服务

提供评分细则的业务逻辑层，包括 CRUD 操作、缓存失效和缺失检测。
"""

import logging
from typing import Optional, List, Dict, Any

from src.repositories.rubric import RubricRepository
from src.services.cache import CacheService
from src.models.rubric import Rubric, RubricCreateRequest, RubricUpdateRequest, ScoringPoint


logger = logging.getLogger(__name__)


class RubricService:
    """
    评分细则服务

    提供评分细则的完整业务逻辑，包括：
    - CRUD 操作
    - 缓存失效管理
    - 缺失评分细则检测
    - 评分细则哈希预计算

    验证：需求 9.1, 9.2, 9.4, 9.5, 6.2
    """

    def __init__(
        self,
        rubric_repository: RubricRepository,
        cache_service: CacheService,
        warmup_service: Optional["CacheWarmupService"] = None,
    ):
        """
        初始化评分细则服务

        Args:
            rubric_repository: 评分细则仓储实例
            cache_service: 缓存服务实例
            warmup_service: 缓存预热服务实例（可选）
        """
        self.repository = rubric_repository
        self.cache_service = cache_service
        self.warmup_service = warmup_service

    async def create_rubric(self, request: RubricCreateRequest) -> Rubric:
        """
        创建评分细则

        将评分细则链接到 exam_id 和 question_id。
        创建时会预计算并缓存评分细则哈希。

        Args:
            request: 创建评分细则请求

        Returns:
            创建的评分细则对象

        Raises:
            ValueError: 如果评分细则已存在

        验证：需求 9.1, 6.2
        """
        # 检查是否已存在
        exists = await self.repository.exists(request.exam_id, request.question_id)

        if exists:
            raise ValueError(
                f"评分细则已存在: exam_id={request.exam_id}, " f"question_id={request.question_id}"
            )

        # 转换 ScoringPoint 为字典列表
        scoring_points_dict = [point.model_dump() for point in request.scoring_points]

        # 创建评分细则
        rubric_data = await self.repository.create(
            exam_id=request.exam_id,
            question_id=request.question_id,
            rubric_text=request.rubric_text,
            max_score=request.max_score,
            scoring_points=scoring_points_dict,
            standard_answer=request.standard_answer,
        )

        # 预计算并缓存评分细则哈希
        if self.warmup_service is not None:
            try:
                await self.warmup_service.precompute_rubric_hash(
                    rubric_id=rubric_data["rubric_id"],
                    rubric_text=request.rubric_text,
                    exam_id=request.exam_id,
                    question_id=request.question_id,
                )
            except Exception as e:
                # 哈希预计算失败不影响创建流程
                logger.warning(f"预计算评分细则哈希失败: {e}")

        logger.info(
            f"创建评分细则成功: rubric_id={rubric_data['rubric_id']}, "
            f"exam_id={request.exam_id}, question_id={request.question_id}"
        )

        return Rubric(**rubric_data)

    async def get_rubric(self, exam_id: str, question_id: str) -> Optional[Rubric]:
        """
        获取评分细则

        根据 exam_id 和 question_id 获取评分细则。

        Args:
            exam_id: 考试 ID
            question_id: 题目 ID

        Returns:
            评分细则对象，如果不存在返回 None

        验证：需求 9.2
        """
        rubric_data = await self.repository.get_by_exam_and_question(exam_id, question_id)

        if rubric_data is None:
            logger.debug(f"评分细则不存在: exam_id={exam_id}, question_id={question_id}")
            return None

        return Rubric(**rubric_data)

    async def get_rubric_by_id(self, rubric_id: str) -> Optional[Rubric]:
        """
        根据 ID 获取评分细则

        Args:
            rubric_id: 评分细则 ID

        Returns:
            评分细则对象，如果不存在返回 None
        """
        rubric_data = await self.repository.get_by_id(rubric_id)

        if rubric_data is None:
            logger.debug(f"评分细则不存在: rubric_id={rubric_id}")
            return None

        return Rubric(**rubric_data)

    async def get_exam_rubrics(self, exam_id: str) -> List[Rubric]:
        """
        获取考试的所有评分细则

        Args:
            exam_id: 考试 ID

        Returns:
            评分细则列表
        """
        rubrics_data = await self.repository.get_by_exam(exam_id)
        return [Rubric(**data) for data in rubrics_data]

    async def update_rubric(self, rubric_id: str, request: RubricUpdateRequest) -> Rubric:
        """
        更新评分细则

        更新后会自动使相关缓存失效，并重新预计算哈希。

        Args:
            rubric_id: 评分细则 ID
            request: 更新请求

        Returns:
            更新后的评分细则对象

        Raises:
            ValueError: 如果评分细则不存在

        验证：需求 9.2, 9.4, 6.2
        """
        # 获取原评分细则（用于缓存失效）
        old_rubric_data = await self.repository.get_by_id(rubric_id)

        if old_rubric_data is None:
            raise ValueError(f"评分细则不存在: rubric_id={rubric_id}")

        # 准备更新参数
        update_params = {}

        if request.rubric_text is not None:
            update_params["rubric_text"] = request.rubric_text

        if request.max_score is not None:
            update_params["max_score"] = request.max_score

        if request.scoring_points is not None:
            update_params["scoring_points"] = [
                point.model_dump() for point in request.scoring_points
            ]

        if request.standard_answer is not None:
            update_params["standard_answer"] = request.standard_answer

        # 执行更新
        success = await self.repository.update(rubric_id, **update_params)

        if not success:
            raise ValueError(f"更新评分细则失败: rubric_id={rubric_id}")

        # 使旧评分细则的缓存失效
        old_rubric_text = old_rubric_data["rubric_text"]
        deleted_count = await self.cache_service.invalidate_by_rubric(old_rubric_text)

        # 使评分细则哈希缓存失效
        if self.warmup_service is not None:
            try:
                await self.warmup_service.invalidate_rubric_hash_cache(
                    exam_id=old_rubric_data["exam_id"], question_id=old_rubric_data["question_id"]
                )
            except Exception as e:
                logger.warning(f"使评分细则哈希缓存失效失败: {e}")

        logger.info(f"更新评分细则成功: rubric_id={rubric_id}, " f"使 {deleted_count} 条缓存失效")

        # 如果评分细则文本也更新了，还需要使新文本的缓存失效并重新预计算哈希
        if request.rubric_text is not None and request.rubric_text != old_rubric_text:
            new_deleted_count = await self.cache_service.invalidate_by_rubric(request.rubric_text)
            logger.info(f"新评分细则文本缓存失效: {new_deleted_count} 条")

            # 重新预计算哈希
            if self.warmup_service is not None:
                try:
                    await self.warmup_service.precompute_rubric_hash(
                        rubric_id=rubric_id,
                        rubric_text=request.rubric_text,
                        exam_id=old_rubric_data["exam_id"],
                        question_id=old_rubric_data["question_id"],
                    )
                except Exception as e:
                    logger.warning(f"重新预计算评分细则哈希失败: {e}")

        # 获取更新后的评分细则
        updated_rubric_data = await self.repository.get_by_id(rubric_id)
        return Rubric(**updated_rubric_data)

    async def delete_rubric(self, rubric_id: str) -> bool:
        """
        删除评分细则

        删除前会使相关缓存失效，包括哈希缓存。

        Args:
            rubric_id: 评分细则 ID

        Returns:
            如果删除成功返回 True，否则返回 False

        验证：需求 9.2, 6.2
        """
        # 获取评分细则（用于缓存失效）
        rubric_data = await self.repository.get_by_id(rubric_id)

        if rubric_data is None:
            logger.warning(f"评分细则不存在，无法删除: rubric_id={rubric_id}")
            return False

        # 使缓存失效
        rubric_text = rubric_data["rubric_text"]
        deleted_count = await self.cache_service.invalidate_by_rubric(rubric_text)

        # 使评分细则哈希缓存失效
        if self.warmup_service is not None:
            try:
                await self.warmup_service.invalidate_rubric_hash_cache(
                    exam_id=rubric_data["exam_id"], question_id=rubric_data["question_id"]
                )
            except Exception as e:
                logger.warning(f"使评分细则哈希缓存失效失败: {e}")

        # 删除评分细则
        success = await self.repository.delete(rubric_id)

        if success:
            logger.info(
                f"删除评分细则成功: rubric_id={rubric_id}, " f"使 {deleted_count} 条缓存失效"
            )

        return success

    async def check_rubric_exists(self, exam_id: str, question_id: str) -> bool:
        """
        检查评分细则是否存在

        Args:
            exam_id: 考试 ID
            question_id: 题目 ID

        Returns:
            如果存在返回 True，否则返回 False

        验证：需求 9.5
        """
        return await self.repository.exists(exam_id, question_id)

    async def validate_rubric_for_grading(
        self, exam_id: str, question_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        验证题目是否有评分细则可用于批改

        如果题目没有评分细则，将其标记为需要手动配置。

        Args:
            exam_id: 考试 ID
            question_id: 题目 ID

        Returns:
            (是否有效, 错误消息)
            如果有效返回 (True, None)
            如果无效返回 (False, 错误消息)

        验证：需求 9.5
        """
        exists = await self.repository.exists(exam_id, question_id)

        if not exists:
            error_msg = (
                f"题目缺失评分细则，需要手动配置: " f"exam_id={exam_id}, question_id={question_id}"
            )
            logger.warning(error_msg)
            return False, error_msg

        return True, None
