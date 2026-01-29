"""回归测试器服务

在评测集上运行回归测试，验证规则补丁的有效性。
验证：需求 9.3, 9.4
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from src.models.rule_patch import RulePatch, RegressionResult
from src.models.grading_log import GradingLog


logger = logging.getLogger(__name__)


class RegressionTester:
    """回归测试器

    功能：
    1. 在评测集上运行回归测试（run_regression）
    2. 判断补丁是否为改进（is_improvement）

    验证：需求 9.3, 9.4
    """

    def __init__(self, improvement_threshold: float = 0.05, max_degradation_rate: float = 0.02):
        """初始化回归测试器

        Args:
            improvement_threshold: 改进阈值（至少降低5%才算改进）
            max_degradation_rate: 最大允许退化率（不超过2%的样本可以退化）
        """
        self.improvement_threshold = improvement_threshold
        self.max_degradation_rate = max_degradation_rate

    async def run_regression(self, patch: RulePatch, eval_set_id: str) -> RegressionResult:
        """在评测集上运行回归测试

        对比应用补丁前后的批改结果，计算各项指标。
        验证：需求 9.3

        Args:
            patch: 待测试的规则补丁
            eval_set_id: 评测集ID

        Returns:
            回归测试结果
        """
        logger.info(f"开始回归测试：补丁 {patch.patch_id}，评测集 {eval_set_id}")

        # 加载评测集
        eval_samples = await self._load_eval_set(eval_set_id)

        if not eval_samples:
            logger.warning(f"评测集 {eval_set_id} 为空")
            return self._create_empty_result(patch.patch_id, eval_set_id)

        logger.info(f"评测集包含 {len(eval_samples)} 个样本")

        # 运行旧版本（不应用补丁）
        old_results = await self._run_grading_batch(eval_samples, apply_patch=False, patch=None)

        # 运行新版本（应用补丁）
        new_results = await self._run_grading_batch(eval_samples, apply_patch=True, patch=patch)

        # 计算指标
        old_metrics = self._calculate_metrics(eval_samples, old_results)
        new_metrics = self._calculate_metrics(eval_samples, new_results)

        # 对比样本级别的变化
        improved_count, degraded_count = self._compare_samples(
            eval_samples, old_results, new_results
        )

        # 判断是否通过
        passed = self.is_improvement(
            old_error_rate=old_metrics["error_rate"],
            new_error_rate=new_metrics["error_rate"],
            old_miss_rate=old_metrics["miss_rate"],
            new_miss_rate=new_metrics["miss_rate"],
            old_review_rate=old_metrics["review_rate"],
            new_review_rate=new_metrics["review_rate"],
            degraded_samples=degraded_count,
            total_samples=len(eval_samples),
        )

        result = RegressionResult(
            patch_id=patch.patch_id,
            passed=passed,
            old_error_rate=old_metrics["error_rate"],
            new_error_rate=new_metrics["error_rate"],
            old_miss_rate=old_metrics["miss_rate"],
            new_miss_rate=new_metrics["miss_rate"],
            old_review_rate=old_metrics["review_rate"],
            new_review_rate=new_metrics["review_rate"],
            total_samples=len(eval_samples),
            improved_samples=improved_count,
            degraded_samples=degraded_count,
            eval_set_id=eval_set_id,
            tested_at=datetime.utcnow(),
        )

        logger.info(
            f"回归测试完成：{'通过' if passed else '未通过'} | "
            f"误判率 {old_metrics['error_rate']:.2%} -> {new_metrics['error_rate']:.2%} | "
            f"漏判率 {old_metrics['miss_rate']:.2%} -> {new_metrics['miss_rate']:.2%} | "
            f"复核率 {old_metrics['review_rate']:.2%} -> {new_metrics['review_rate']:.2%}"
        )

        return result

    def is_improvement(
        self,
        old_error_rate: float,
        new_error_rate: float,
        old_miss_rate: float,
        new_miss_rate: float,
        old_review_rate: float,
        new_review_rate: float,
        degraded_samples: int = 0,
        total_samples: int = 100,
    ) -> bool:
        """判断是否为改进

        改进的定义：
        1. 误判率、漏判率、复核率都下降
        2. 至少有一项指标下降超过阈值
        3. 退化样本比例不超过最大允许值

        验证：需求 9.4

        Args:
            old_error_rate: 旧版本误判率
            new_error_rate: 新版本误判率
            old_miss_rate: 旧版本漏判率
            new_miss_rate: 新版本漏判率
            old_review_rate: 旧版本复核率
            new_review_rate: 新版本复核率
            degraded_samples: 退化的样本数
            total_samples: 总样本数

        Returns:
            是否为改进
        """
        # 检查是否所有指标都没有恶化（或保持不变）
        error_not_worse = new_error_rate <= old_error_rate
        miss_not_worse = new_miss_rate <= old_miss_rate
        review_not_worse = new_review_rate <= old_review_rate

        if not (error_not_worse and miss_not_worse and review_not_worse):
            logger.info("存在指标恶化，不算改进")
            return False

        # 检查是否至少有一项指标有显著改进（使用 > 而不是 >=，避免浮点数精度问题）
        error_improved = (old_error_rate - new_error_rate) > self.improvement_threshold - 1e-9
        miss_improved = (old_miss_rate - new_miss_rate) > self.improvement_threshold - 1e-9
        review_improved = (old_review_rate - new_review_rate) > self.improvement_threshold - 1e-9

        has_significant_improvement = error_improved or miss_improved or review_improved

        if not has_significant_improvement:
            logger.info(f"改进幅度不足（阈值 {self.improvement_threshold:.2%}）")
            return False

        # 检查退化样本比例
        if total_samples > 0:
            degradation_rate = degraded_samples / total_samples
            if degradation_rate > self.max_degradation_rate:
                logger.info(
                    f"退化样本比例过高：{degradation_rate:.2%} > {self.max_degradation_rate:.2%}"
                )
                return False

        logger.info("补丁通过改进检查")
        return True

    async def _load_eval_set(self, eval_set_id: str) -> List[Dict[str, Any]]:
        """加载评测集

        Args:
            eval_set_id: 评测集ID

        Returns:
            评测样本列表，每个样本包含：
            - sample_id: 样本ID
            - question_id: 题目ID
            - student_answer: 学生答案
            - ground_truth_score: 标准分数
            - ground_truth_feedback: 标准反馈
        """
        # TODO: 从数据库或文件系统加载评测集
        # 这里返回模拟数据用于测试
        logger.info(f"加载评测集 {eval_set_id}")

        # 实际实现应该从数据库加载
        # 这里返回空列表，实际使用时需要实现
        return []

    async def _run_grading_batch(
        self, samples: List[Dict[str, Any]], apply_patch: bool, patch: Optional[RulePatch]
    ) -> List[Dict[str, Any]]:
        """批量运行批改

        Args:
            samples: 评测样本列表
            apply_patch: 是否应用补丁
            patch: 补丁对象（如果 apply_patch=True）

        Returns:
            批改结果列表，每个结果包含：
            - sample_id: 样本ID
            - predicted_score: 预测分数
            - predicted_feedback: 预测反馈
            - confidence: 置信度
        """
        # TODO: 调用实际的批改服务
        # 这里返回模拟数据用于测试
        logger.info(
            f"运行批改：{'应用补丁' if apply_patch else '不应用补丁'}，" f"样本数 {len(samples)}"
        )

        results = []
        for sample in samples:
            # 实际实现应该调用批改服务
            # 这里返回模拟结果
            result = {
                "sample_id": sample.get("sample_id"),
                "predicted_score": sample.get("ground_truth_score", 0.0),
                "predicted_feedback": "模拟反馈",
                "confidence": 0.9,
            }
            results.append(result)

        return results

    def _calculate_metrics(
        self, samples: List[Dict[str, Any]], results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """计算评测指标

        Args:
            samples: 评测样本列表
            results: 批改结果列表

        Returns:
            指标字典，包含：
            - error_rate: 误判率（预测错误的比例）
            - miss_rate: 漏判率（应该扣分但没扣的比例）
            - review_rate: 复核率（低置信度需要人工复核的比例）
        """
        if not samples or not results:
            return {"error_rate": 0.0, "miss_rate": 0.0, "review_rate": 0.0}

        error_count = 0
        miss_count = 0
        review_count = 0
        total = len(samples)

        for sample, result in zip(samples, results):
            ground_truth = sample.get("ground_truth_score", 0.0)
            predicted = result.get("predicted_score", 0.0)
            confidence = result.get("confidence", 1.0)

            # 误判：预测分数与标准分数差异超过阈值
            score_diff = abs(predicted - ground_truth)
            if score_diff > 1.0:  # 差异超过1分算误判
                error_count += 1

            # 漏判：应该扣分（标准分数 < 满分）但预测给了满分
            max_score = sample.get("max_score", 10.0)
            if ground_truth < max_score and predicted >= max_score:
                miss_count += 1

            # 复核：置信度低于阈值（0.85）
            if confidence < 0.85:
                review_count += 1

        return {
            "error_rate": error_count / total if total > 0 else 0.0,
            "miss_rate": miss_count / total if total > 0 else 0.0,
            "review_rate": review_count / total if total > 0 else 0.0,
        }

    def _compare_samples(
        self,
        samples: List[Dict[str, Any]],
        old_results: List[Dict[str, Any]],
        new_results: List[Dict[str, Any]],
    ) -> Tuple[int, int]:
        """对比样本级别的变化

        Args:
            samples: 评测样本列表
            old_results: 旧版本批改结果
            new_results: 新版本批改结果

        Returns:
            (改进的样本数, 退化的样本数)
        """
        improved_count = 0
        degraded_count = 0

        for sample, old_result, new_result in zip(samples, old_results, new_results):
            ground_truth = sample.get("ground_truth_score", 0.0)
            old_score = old_result.get("predicted_score", 0.0)
            new_score = new_result.get("predicted_score", 0.0)

            old_error = abs(old_score - ground_truth)
            new_error = abs(new_score - ground_truth)

            # 改进：新版本误差更小
            if new_error < old_error - 0.5:  # 误差减少超过0.5分
                improved_count += 1
            # 退化：新版本误差更大
            elif new_error > old_error + 0.5:  # 误差增加超过0.5分
                degraded_count += 1

        return improved_count, degraded_count

    def _create_empty_result(self, patch_id: str, eval_set_id: str) -> RegressionResult:
        """创建空的测试结果（评测集为空时）"""
        return RegressionResult(
            patch_id=patch_id,
            passed=False,
            old_error_rate=0.0,
            new_error_rate=0.0,
            old_miss_rate=0.0,
            new_miss_rate=0.0,
            old_review_rate=0.0,
            new_review_rate=0.0,
            total_samples=0,
            improved_samples=0,
            degraded_samples=0,
            eval_set_id=eval_set_id,
            tested_at=datetime.utcnow(),
        )


# 全局单例
_regression_tester: Optional[RegressionTester] = None


def get_regression_tester() -> RegressionTester:
    """获取回归测试器单例"""
    global _regression_tester
    if _regression_tester is None:
        _regression_tester = RegressionTester()
    return _regression_tester
