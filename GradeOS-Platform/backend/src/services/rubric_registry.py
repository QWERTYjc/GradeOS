"""
评分标准注册中心 (Rubric Registry)

提供评分标准的存储、查询、更新功能，支持内存缓存模式。
用于批改工作流中动态获取指定题目的评分标准。

Requirements: 1.1, 1.3, 1.4, 1.5, 11.3
"""

import logging
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from pathlib import Path

from src.models.grading_models import (
    QuestionRubric,
    ScoringPoint,
    AlternativeSolution,
)

logger = logging.getLogger(__name__)


@dataclass
class RubricQueryResult:
    """评分标准查询结果"""
    rubric: Optional[QuestionRubric]
    is_default: bool = False  # 是否为默认规则
    confidence: float = 1.0  # 置信度 (低置信度表示使用默认规则)
    message: str = ""


class RubricRegistry:
    """
    评分标准注册中心
    
    负责存储和管理所有题目的评分标准，支持动态查询。
    支持内存缓存模式，无需数据库依赖。
    
    Requirements:
    - 1.1: 返回题目的完整评分标准
    - 1.3: 同时返回所有有效的解法及其评分条件
    - 1.4: 不存在时返回默认评分规则并标记为低置信度
    - 1.5: 确保后续批改使用最新版本
    - 11.3: 支持内存缓存模式
    """
    
    def __init__(self, total_score: float = 100.0, version: str = "1.0"):
        """
        初始化评分标准注册中心
        
        Args:
            total_score: 试卷总分
            version: 版本号
        """
        self._rubrics: Dict[str, QuestionRubric] = {}
        self._total_score = total_score
        self._version = version
        self._lock = Lock()
        self._last_updated = datetime.utcnow().isoformat()
        
        # 默认评分规则配置
        self._default_max_score = 5.0
        self._default_confidence = 0.3

    @property
    def total_score(self) -> float:
        """获取试卷总分"""
        return self._total_score
    
    @property
    def version(self) -> str:
        """获取版本号"""
        return self._version
    
    @property
    def last_updated(self) -> str:
        """获取最后更新时间"""
        return self._last_updated
    
    def get_rubric_for_question(
        self, 
        question_id: str
    ) -> RubricQueryResult:
        """
        获取指定题目的评分标准
        
        Args:
            question_id: 题目编号（如 "1", "7a", "15"）
            
        Returns:
            RubricQueryResult: 包含评分标准、是否默认、置信度等信息
            
        Requirements:
        - 1.1: 返回完整评分标准（得分点、标准答案、另类解法）
        - 1.3: 同时返回所有有效的解法
        - 1.4: 不存在时返回默认规则并标记低置信度
        """
        normalized_id = self._normalize_question_id(question_id)
        
        with self._lock:
            # 精确匹配
            if normalized_id in self._rubrics:
                rubric = self._rubrics[normalized_id]
                return RubricQueryResult(
                    rubric=rubric,
                    is_default=False,
                    confidence=1.0,
                    message=f"找到题目 {question_id} 的评分标准"
                )
            
            # 尝试模糊匹配（处理子题情况，如 7a -> 7）
            parent_id = self._get_parent_question_id(normalized_id)
            if parent_id and parent_id in self._rubrics:
                rubric = self._rubrics[parent_id]
                return RubricQueryResult(
                    rubric=rubric,
                    is_default=False,
                    confidence=0.8,
                    message=f"使用父题目 {parent_id} 的评分标准"
                )
            
            # 返回默认评分规则 (Requirement 1.4)
            logger.warning(f"题目 {question_id} 的评分标准不存在，使用默认规则")
            default_rubric = self._create_default_rubric(question_id)
            return RubricQueryResult(
                rubric=default_rubric,
                is_default=True,
                confidence=self._default_confidence,
                message=f"题目 {question_id} 使用默认评分规则"
            )
    
    def get_all_rubrics(self) -> List[QuestionRubric]:
        """
        获取所有评分标准
        
        Returns:
            List[QuestionRubric]: 所有评分标准列表
        """
        with self._lock:
            return list(self._rubrics.values())
    
    def get_rubric_count(self) -> int:
        """获取评分标准数量"""
        with self._lock:
            return len(self._rubrics)
    
    def register_rubric(self, rubric: QuestionRubric) -> None:
        """
        注册单个评分标准
        
        Args:
            rubric: 评分标准对象
        """
        normalized_id = self._normalize_question_id(rubric.question_id)
        with self._lock:
            self._rubrics[normalized_id] = rubric
            self._update_timestamp()
            logger.info(f"注册评分标准: {rubric.question_id}")
    
    def register_rubrics(self, rubrics: List[QuestionRubric], log: bool = True) -> None:
        """
        批量注册评分标准
        
        Args:
            rubrics: 评分标准列表
        """
        with self._lock:
            for rubric in rubrics:
                normalized_id = self._normalize_question_id(rubric.question_id)
                self._rubrics[normalized_id] = rubric
            self._update_timestamp()
            if log:
                logger.info(f"批量注册 {len(rubrics)} 个评分标准")

    def update_rubric(
        self, 
        question_id: str, 
        rubric: QuestionRubric
    ) -> bool:
        """
        更新评分标准 (Requirement 1.5)
        
        Args:
            question_id: 题目编号
            rubric: 新的评分标准
            
        Returns:
            bool: 是否更新成功
        """
        normalized_id = self._normalize_question_id(question_id)
        with self._lock:
            if normalized_id in self._rubrics:
                self._rubrics[normalized_id] = rubric
                self._update_timestamp()
                self._version = self._increment_version()
                logger.info(f"更新评分标准: {question_id}, 新版本: {self._version}")
                return True
            else:
                logger.warning(f"更新失败: 题目 {question_id} 不存在")
                return False
    
    def remove_rubric(self, question_id: str) -> bool:
        """
        移除评分标准
        
        Args:
            question_id: 题目编号
            
        Returns:
            bool: 是否移除成功
        """
        normalized_id = self._normalize_question_id(question_id)
        with self._lock:
            if normalized_id in self._rubrics:
                del self._rubrics[normalized_id]
                self._update_timestamp()
                logger.info(f"移除评分标准: {question_id}")
                return True
            return False
    
    def clear(self) -> None:
        """清空所有评分标准"""
        with self._lock:
            self._rubrics.clear()
            self._update_timestamp()
            logger.info("清空所有评分标准")
    
    def has_rubric(self, question_id: str) -> bool:
        """
        检查是否存在指定题目的评分标准
        
        Args:
            question_id: 题目编号
            
        Returns:
            bool: 是否存在
        """
        normalized_id = self._normalize_question_id(question_id)
        with self._lock:
            return normalized_id in self._rubrics
    
    def get_question_ids(self) -> List[str]:
        """获取所有题目编号"""
        with self._lock:
            return list(self._rubrics.keys())
    
    def calculate_total_max_score(self) -> float:
        """计算所有题目的满分总和"""
        with self._lock:
            return sum(r.max_score for r in self._rubrics.values())
    
    # ==================== 序列化方法 ====================
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        with self._lock:
            return {
                "rubrics": {
                    qid: rubric.to_dict() 
                    for qid, rubric in self._rubrics.items()
                },
                "total_score": self._total_score,
                "version": self._version,
                "last_updated": self._last_updated
            }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RubricRegistry":
        """从字典反序列化"""
        registry = cls(
            total_score=data.get("total_score", 100.0),
            version=data.get("version", "1.0")
        )
        registry._last_updated = data.get("last_updated", datetime.utcnow().isoformat())
        
        rubrics_data = data.get("rubrics", {})
        for qid, rubric_dict in rubrics_data.items():
            rubric = QuestionRubric.from_dict(rubric_dict)
            registry._rubrics[qid] = rubric
        
        return registry
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "RubricRegistry":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))
    
    def save_to_file(self, filepath: str) -> None:
        """保存到文件"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info(f"评分标准已保存到: {filepath}")
    
    @classmethod
    def load_from_file(cls, filepath: str) -> "RubricRegistry":
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())

    # ==================== 从文本解析评分标准 ====================
    
    def parse_from_text(self, rubric_text: str) -> int:
        """
        从文本解析评分标准并注册
        
        支持常见的评分标准格式，如：
        - "第1题（5分）：..."
        - "1. (10分) ..."
        - "题目7a: 满分8分 ..."
        
        Args:
            rubric_text: 评分标准文本
            
        Returns:
            int: 成功解析的题目数量
        """
        rubrics = self._parse_rubric_text(rubric_text)
        self.register_rubrics(rubrics)
        return len(rubrics)
    
    def _parse_rubric_text(self, text: str) -> List[QuestionRubric]:
        """解析评分标准文本"""
        rubrics = []
        
        # 按题目分割
        # 匹配模式: 第N题、N.、题目N、N、等
        pattern = r'(?:第\s*)?(\d+[a-zA-Z]?)\s*[.、题：:]\s*[（(]?\s*(\d+)\s*分\s*[）)]?'
        
        sections = re.split(r'\n(?=(?:第\s*)?\d+[a-zA-Z]?\s*[.、题])', text)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            match = re.search(pattern, section)
            if match:
                question_id = match.group(1)
                max_score = float(match.group(2))
                
                # 提取得分点
                scoring_points = self._extract_scoring_points(section, max_score)
                
                rubric = QuestionRubric(
                    question_id=question_id,
                    max_score=max_score,
                    question_text=section,
                    standard_answer="",
                    scoring_points=scoring_points,
                    alternative_solutions=[],
                    grading_notes=""
                )
                rubrics.append(rubric)
        
        return rubrics
    
    def _extract_scoring_points(
        self, 
        text: str, 
        max_score: float
    ) -> List[ScoringPoint]:
        """从文本中提取得分点"""
        scoring_points = []
        
        # 匹配得分点模式: (N分)、N分、得N分等
        point_pattern = r'[（(]?\s*(\d+(?:\.\d+)?)\s*分\s*[）)]?'
        matches = re.findall(point_pattern, text)
        
        if matches:
            # 跳过第一个（通常是总分）
            for i, score_str in enumerate(matches[1:], 1):
                score = float(score_str)
                scoring_points.append(ScoringPoint(
                    description=f"得分点{i}",
                    score=score,
                    is_required=True
                ))
        
        # 如果没有找到得分点，创建一个默认的
        if not scoring_points:
            scoring_points.append(ScoringPoint(
                description="完整解答",
                score=max_score,
                is_required=True
            ))
        
        return scoring_points
    
    # ==================== 私有辅助方法 ====================
    
    def _normalize_question_id(self, question_id: str) -> str:
        """
        标准化题目编号
        
        - 去除空格
        - 统一大小写
        - 处理特殊字符
        """
        normalized = question_id.strip().lower()
        # 移除常见前缀
        normalized = re.sub(r'^(第|题目|question)\s*', '', normalized)
        # 移除常见后缀
        normalized = re.sub(r'\s*(题|分)$', '', normalized)
        return normalized
    
    def _get_parent_question_id(self, question_id: str) -> Optional[str]:
        """
        获取父题目编号（用于子题匹配）
        
        例如: "7a" -> "7", "15b" -> "15"
        """
        match = re.match(r'^(\d+)[a-zA-Z]$', question_id)
        if match:
            return match.group(1)
        return None
    
    def _create_default_rubric(self, question_id: str) -> QuestionRubric:
        """
        创建默认评分规则 (Requirement 1.4)
        
        当题目不存在时返回默认规则
        """
        return QuestionRubric(
            question_id=question_id,
            max_score=self._default_max_score,
            question_text="",
            standard_answer="",
            scoring_points=[
                ScoringPoint(
                    description="默认得分点",
                    score=self._default_max_score,
                    is_required=True
                )
            ],
            alternative_solutions=[],
            grading_notes="使用默认评分规则，建议人工复核"
        )
    
    def _update_timestamp(self) -> None:
        """更新最后修改时间"""
        self._last_updated = datetime.utcnow().isoformat()
    
    def _increment_version(self) -> str:
        """递增版本号"""
        try:
            parts = self._version.split('.')
            parts[-1] = str(int(parts[-1]) + 1)
            return '.'.join(parts)
        except (ValueError, IndexError):
            return "1.1"


# ==================== 全局单例支持 ====================

_global_registry: Optional[RubricRegistry] = None
_global_lock = Lock()


def get_global_registry() -> RubricRegistry:
    """
    获取全局评分标准注册中心实例
    
    支持无数据库模式的内存缓存 (Requirement 11.3)
    """
    global _global_registry
    with _global_lock:
        if _global_registry is None:
            _global_registry = RubricRegistry()
            logger.info("创建全局评分标准注册中心")
        return _global_registry


def reset_global_registry() -> None:
    """重置全局注册中心（主要用于测试）"""
    global _global_registry
    with _global_lock:
        _global_registry = None


# 导出
__all__ = [
    "RubricRegistry",
    "RubricQueryResult",
    "get_global_registry",
    "reset_global_registry",
]
