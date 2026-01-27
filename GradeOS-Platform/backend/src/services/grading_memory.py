"""批改记忆系统

实现批改经验的积累、存储、检索和共享，让自白节点能够：
1. 记住历史批改中的错误模式和经验教训
2. 跨学生/跨批次共享学习到的知识
3. 识别重复出现的问题模式
4. 提升自我校准能力

设计原则：
- 记忆分层：短期记忆（当前批次）+ 长期记忆（历史积累）
- 模式识别：从具体案例中抽象出通用模式
- 置信度校准：基于历史数据校准自我评估
- 遗忘机制：淘汰过时、低频、低价值的记忆
"""

import json
import logging
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import threading


logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """记忆类型"""
    ERROR_PATTERN = "error_pattern"        # 错误模式（如：某类题目容易误判）
    CALIBRATION = "calibration"            # 校准经验（如：某题型置信度偏高）
    EVIDENCE_QUALITY = "evidence_quality"  # 证据质量模式
    SCORING_INSIGHT = "scoring_insight"    # 评分洞察
    RISK_SIGNAL = "risk_signal"            # 风险信号
    CORRECTION_HISTORY = "correction_history"  # 修正历史


class MemoryImportance(str, Enum):
    """记忆重要性"""
    CRITICAL = "critical"    # 关键记忆（如：导致重大错误的模式）
    HIGH = "high"            # 高重要性
    MEDIUM = "medium"        # 中等重要性
    LOW = "low"              # 低重要性


@dataclass
class MemoryEntry:
    """单条记忆条目"""
    memory_id: str                          # 唯一标识
    memory_type: MemoryType                 # 记忆类型
    importance: MemoryImportance            # 重要性
    
    # 核心内容
    pattern: str                            # 模式描述
    context: Dict[str, Any]                 # 上下文信息
    lesson: str                             # 经验教训
    
    # 统计信息
    occurrence_count: int = 1               # 出现次数
    confirmation_count: int = 0             # 被验证正确的次数
    contradiction_count: int = 0            # 被证伪的次数
    
    # 时间信息
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 关联信息
    related_question_types: List[str] = field(default_factory=list)
    related_rubric_ids: List[str] = field(default_factory=list)
    source_batch_ids: List[str] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def confidence(self) -> float:
        """计算该记忆的可信度"""
        total = self.confirmation_count + self.contradiction_count
        if total == 0:
            return 0.5  # 未验证
        return self.confirmation_count / total
    
    @property
    def relevance_score(self) -> float:
        """计算相关性得分（用于检索排序）"""
        # 基于重要性、出现次数、可信度综合计算
        importance_weight = {
            MemoryImportance.CRITICAL: 1.0,
            MemoryImportance.HIGH: 0.8,
            MemoryImportance.MEDIUM: 0.5,
            MemoryImportance.LOW: 0.3,
        }
        base = importance_weight.get(self.importance, 0.5)
        frequency_factor = min(self.occurrence_count / 10, 1.0)  # 最多加成1.0
        confidence_factor = self.confidence
        return base * (1 + frequency_factor) * confidence_factor
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["memory_type"] = self.memory_type.value
        result["importance"] = self.importance.value
        result["confidence"] = self.confidence
        result["relevance_score"] = self.relevance_score
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        data = dict(data)
        if isinstance(data.get("memory_type"), str):
            data["memory_type"] = MemoryType(data["memory_type"])
        if isinstance(data.get("importance"), str):
            data["importance"] = MemoryImportance(data["importance"])
        # 移除计算属性
        data.pop("confidence", None)
        data.pop("relevance_score", None)
        return cls(**data)


@dataclass
class CalibrationStats:
    """置信度校准统计"""
    question_type: str                      # 题型
    predicted_confidences: List[float] = field(default_factory=list)
    actual_accuracies: List[float] = field(default_factory=list)
    
    @property
    def calibration_error(self) -> float:
        """计算校准误差（预测置信度与实际准确率的差距）"""
        if not self.predicted_confidences or not self.actual_accuracies:
            return 0.0
        avg_predicted = sum(self.predicted_confidences) / len(self.predicted_confidences)
        avg_actual = sum(self.actual_accuracies) / len(self.actual_accuracies)
        return avg_predicted - avg_actual
    
    @property
    def recommended_adjustment(self) -> float:
        """推荐的置信度调整值"""
        error = self.calibration_error
        # 如果预测过高，建议降低；如果预测过低，建议提高
        return -error * 0.5  # 保守调整


@dataclass
class BatchMemory:
    """批次级短期记忆"""
    batch_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 当前批次的统计
    total_questions: int = 0
    total_students: int = 0
    
    # 错误模式统计
    error_patterns: Dict[str, int] = field(default_factory=dict)  # pattern -> count
    
    # 风险信号统计
    risk_signals: Dict[str, int] = field(default_factory=dict)  # signal -> count
    
    # 置信度分布
    confidence_distribution: Dict[str, List[float]] = field(default_factory=dict)  # question_type -> [confidences]
    
    # 高风险题目
    high_risk_questions: List[Dict[str, Any]] = field(default_factory=list)
    
    # 修正记录
    corrections: List[Dict[str, Any]] = field(default_factory=list)


class GradingMemoryService:
    """
    批改记忆服务
    
    管理批改经验的积累、存储、检索和共享。
    支持多种存储后端（内存、文件、数据库）。
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_memory_entries: int = 10000,
        memory_ttl_days: int = 90,
    ):
        """
        初始化记忆服务
        
        Args:
            storage_path: 持久化存储路径（None 则仅内存存储）
            max_memory_entries: 最大记忆条目数
            memory_ttl_days: 记忆过期时间（天）
        """
        self.storage_path = storage_path
        self.max_memory_entries = max_memory_entries
        self.memory_ttl_days = memory_ttl_days
        
        # 长期记忆存储
        self._long_term_memory: Dict[str, MemoryEntry] = {}
        
        # 短期记忆存储（按批次）
        self._batch_memories: Dict[str, BatchMemory] = {}
        
        # 置信度校准统计
        self._calibration_stats: Dict[str, CalibrationStats] = {}
        
        # 索引（用于快速检索）
        self._type_index: Dict[MemoryType, List[str]] = defaultdict(list)
        self._question_type_index: Dict[str, List[str]] = defaultdict(list)
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 加载持久化的记忆
        if storage_path:
            self._load_from_storage()
    
    def _generate_memory_id(self, pattern: str, context: Dict[str, Any]) -> str:
        """生成记忆唯一标识"""
        content = f"{pattern}:{json.dumps(context, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    # ==================== 记忆存储 ====================
    
    def store_memory(
        self,
        memory_type: MemoryType,
        pattern: str,
        lesson: str,
        context: Optional[Dict[str, Any]] = None,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        question_types: Optional[List[str]] = None,
        rubric_ids: Optional[List[str]] = None,
        batch_id: Optional[str] = None,
    ) -> str:
        """
        存储一条新记忆
        
        Args:
            memory_type: 记忆类型
            pattern: 模式描述
            lesson: 经验教训
            context: 上下文信息
            importance: 重要性
            question_types: 相关题型
            rubric_ids: 相关评分标准ID
            batch_id: 来源批次ID
            
        Returns:
            str: 记忆ID
        """
        context = context or {}
        memory_id = self._generate_memory_id(pattern, context)
        
        with self._lock:
            # 检查是否已存在相同模式
            if memory_id in self._long_term_memory:
                # 更新已有记忆
                existing = self._long_term_memory[memory_id]
                existing.occurrence_count += 1
                existing.last_updated_at = datetime.now().isoformat()
                if batch_id and batch_id not in existing.source_batch_ids:
                    existing.source_batch_ids.append(batch_id)
                logger.debug(f"[Memory] 更新已有记忆: {memory_id}, 出现次数: {existing.occurrence_count}")
                return memory_id
            
            # 创建新记忆
            entry = MemoryEntry(
                memory_id=memory_id,
                memory_type=memory_type,
                importance=importance,
                pattern=pattern,
                context=context,
                lesson=lesson,
                related_question_types=question_types or [],
                related_rubric_ids=rubric_ids or [],
                source_batch_ids=[batch_id] if batch_id else [],
            )
            
            self._long_term_memory[memory_id] = entry
            
            # 更新索引
            self._type_index[memory_type].append(memory_id)
            for qt in entry.related_question_types:
                self._question_type_index[qt].append(memory_id)
            
            # 检查容量限制
            self._enforce_capacity_limit()
            
            logger.info(f"[Memory] 存储新记忆: {memory_id}, 类型: {memory_type.value}")
            return memory_id
    
    def confirm_memory(self, memory_id: str) -> bool:
        """确认记忆正确（被验证）"""
        with self._lock:
            if memory_id in self._long_term_memory:
                self._long_term_memory[memory_id].confirmation_count += 1
                self._long_term_memory[memory_id].last_accessed_at = datetime.now().isoformat()
                return True
            return False
    
    def contradict_memory(self, memory_id: str) -> bool:
        """记忆被证伪"""
        with self._lock:
            if memory_id in self._long_term_memory:
                self._long_term_memory[memory_id].contradiction_count += 1
                self._long_term_memory[memory_id].last_accessed_at = datetime.now().isoformat()
                return True
            return False
    
    # ==================== 记忆检索 ====================
    
    def retrieve_relevant_memories(
        self,
        question_types: Optional[List[str]] = None,
        memory_types: Optional[List[MemoryType]] = None,
        min_confidence: float = 0.3,
        max_results: int = 10,
    ) -> List[MemoryEntry]:
        """
        检索相关记忆
        
        Args:
            question_types: 相关题型
            memory_types: 记忆类型过滤
            min_confidence: 最小可信度
            max_results: 最大返回数量
            
        Returns:
            List[MemoryEntry]: 相关记忆列表（按相关性排序）
        """
        with self._lock:
            candidates = []
            
            # 收集候选记忆
            if memory_types:
                memory_ids = set()
                for mt in memory_types:
                    memory_ids.update(self._type_index.get(mt, []))
            else:
                memory_ids = set(self._long_term_memory.keys())
            
            # 如果指定了题型，进一步过滤
            if question_types:
                type_memory_ids = set()
                for qt in question_types:
                    type_memory_ids.update(self._question_type_index.get(qt, []))
                # 交集或取相关的
                if type_memory_ids:
                    # 优先取交集，但也保留部分通用记忆
                    relevant_ids = memory_ids & type_memory_ids
                    # 加入一些高重要性的通用记忆
                    for mid in memory_ids - type_memory_ids:
                        entry = self._long_term_memory.get(mid)
                        if entry and entry.importance in [MemoryImportance.CRITICAL, MemoryImportance.HIGH]:
                            relevant_ids.add(mid)
                    memory_ids = relevant_ids if relevant_ids else memory_ids
            
            # 过滤和排序
            for memory_id in memory_ids:
                entry = self._long_term_memory.get(memory_id)
                if entry and entry.confidence >= min_confidence:
                    candidates.append(entry)
                    # 更新访问时间
                    entry.last_accessed_at = datetime.now().isoformat()
            
            # 按相关性排序
            candidates.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return candidates[:max_results]
    
    def get_error_patterns_for_question_type(
        self,
        question_type: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """获取特定题型的常见错误模式"""
        memories = self.retrieve_relevant_memories(
            question_types=[question_type],
            memory_types=[MemoryType.ERROR_PATTERN],
            max_results=max_results,
        )
        return [m.to_dict() for m in memories]
    
    def get_calibration_recommendation(
        self,
        question_type: str,
        predicted_confidence: float,
    ) -> Dict[str, Any]:
        """
        获取置信度校准建议
        
        基于历史数据，判断预测的置信度是否需要调整。
        
        Args:
            question_type: 题型
            predicted_confidence: 预测的置信度
            
        Returns:
            校准建议
        """
        with self._lock:
            stats = self._calibration_stats.get(question_type)
            if not stats or len(stats.predicted_confidences) < 10:
                return {
                    "has_data": False,
                    "predicted": predicted_confidence,
                    "adjusted": predicted_confidence,
                    "adjustment": 0.0,
                    "reason": "历史数据不足，无法校准",
                }
            
            adjustment = stats.recommended_adjustment
            adjusted_confidence = max(0.0, min(1.0, predicted_confidence + adjustment))
            
            return {
                "has_data": True,
                "predicted": predicted_confidence,
                "adjusted": adjusted_confidence,
                "adjustment": adjustment,
                "calibration_error": stats.calibration_error,
                "sample_size": len(stats.predicted_confidences),
                "reason": (
                    f"历史数据显示该题型预测置信度{'偏高' if adjustment < 0 else '偏低'}"
                    f"约 {abs(stats.calibration_error):.2f}"
                ),
            }
    
    # ==================== 批次记忆 ====================
    
    def create_batch_memory(self, batch_id: str) -> BatchMemory:
        """创建批次级短期记忆"""
        with self._lock:
            if batch_id not in self._batch_memories:
                self._batch_memories[batch_id] = BatchMemory(batch_id=batch_id)
            return self._batch_memories[batch_id]
    
    def get_batch_memory(self, batch_id: str) -> Optional[BatchMemory]:
        """获取批次记忆"""
        return self._batch_memories.get(batch_id)
    
    def record_batch_error_pattern(
        self,
        batch_id: str,
        pattern: str,
        question_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录批次内的错误模式"""
        with self._lock:
            batch_mem = self.create_batch_memory(batch_id)
            batch_mem.error_patterns[pattern] = batch_mem.error_patterns.get(pattern, 0) + 1
    
    def record_batch_risk_signal(
        self,
        batch_id: str,
        signal: str,
        question_id: str,
        severity: str = "medium",
    ) -> None:
        """记录批次内的风险信号"""
        with self._lock:
            batch_mem = self.create_batch_memory(batch_id)
            batch_mem.risk_signals[signal] = batch_mem.risk_signals.get(signal, 0) + 1
            
            if severity in ["high", "critical"]:
                batch_mem.high_risk_questions.append({
                    "question_id": question_id,
                    "signal": signal,
                    "severity": severity,
                    "timestamp": datetime.now().isoformat(),
                })
    
    def record_batch_confidence(
        self,
        batch_id: str,
        question_type: str,
        confidence: float,
    ) -> None:
        """记录批次内的置信度"""
        with self._lock:
            batch_mem = self.create_batch_memory(batch_id)
            if question_type not in batch_mem.confidence_distribution:
                batch_mem.confidence_distribution[question_type] = []
            batch_mem.confidence_distribution[question_type].append(confidence)
    
    def record_correction(
        self,
        batch_id: str,
        question_id: str,
        original_score: float,
        corrected_score: float,
        reason: str,
        source: str = "logic_review",
    ) -> None:
        """记录评分修正"""
        with self._lock:
            batch_mem = self.create_batch_memory(batch_id)
            batch_mem.corrections.append({
                "question_id": question_id,
                "original_score": original_score,
                "corrected_score": corrected_score,
                "difference": corrected_score - original_score,
                "reason": reason,
                "source": source,
                "timestamp": datetime.now().isoformat(),
            })
    
    def consolidate_batch_memory(self, batch_id: str) -> int:
        """
        将批次短期记忆整合到长期记忆
        
        在批次完成后调用，提取有价值的模式存入长期记忆。
        
        Returns:
            int: 新增的长期记忆数量
        """
        with self._lock:
            batch_mem = self._batch_memories.get(batch_id)
            if not batch_mem:
                return 0
            
            new_memories = 0
            
            # 整合频繁出现的错误模式
            for pattern, count in batch_mem.error_patterns.items():
                if count >= 3:  # 至少出现3次
                    self.store_memory(
                        memory_type=MemoryType.ERROR_PATTERN,
                        pattern=pattern,
                        lesson=f"该错误模式在批次 {batch_id} 中出现 {count} 次，需要特别关注",
                        context={"occurrence_count": count, "batch_id": batch_id},
                        importance=MemoryImportance.HIGH if count >= 5 else MemoryImportance.MEDIUM,
                        batch_id=batch_id,
                    )
                    new_memories += 1
            
            # 整合高风险信号
            for signal, count in batch_mem.risk_signals.items():
                if count >= 2:
                    self.store_memory(
                        memory_type=MemoryType.RISK_SIGNAL,
                        pattern=signal,
                        lesson=f"该风险信号在批次 {batch_id} 中出现 {count} 次",
                        context={"occurrence_count": count, "batch_id": batch_id},
                        importance=MemoryImportance.MEDIUM,
                        batch_id=batch_id,
                    )
                    new_memories += 1
            
            # 更新置信度校准数据
            for question_type, confidences in batch_mem.confidence_distribution.items():
                if question_type not in self._calibration_stats:
                    self._calibration_stats[question_type] = CalibrationStats(
                        question_type=question_type
                    )
                self._calibration_stats[question_type].predicted_confidences.extend(confidences)
            
            # 从修正记录中学习
            for correction in batch_mem.corrections:
                diff = abs(correction["difference"])
                if diff >= 2:  # 分数差距大于2分
                    importance = MemoryImportance.CRITICAL if diff >= 5 else MemoryImportance.HIGH
                    self.store_memory(
                        memory_type=MemoryType.CORRECTION_HISTORY,
                        pattern=f"评分修正: {correction['reason']}",
                        lesson=f"原分数与修正后分数相差 {diff} 分，原因: {correction['reason']}",
                        context=correction,
                        importance=importance,
                        batch_id=batch_id,
                    )
                    new_memories += 1
            
            logger.info(f"[Memory] 批次 {batch_id} 整合完成，新增 {new_memories} 条长期记忆")
            return new_memories
    
    # ==================== 自白辅助 ====================
    
    def generate_confession_context(
        self,
        question_details: List[Dict[str, Any]],
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        为自白节点生成记忆上下文
        
        基于历史记忆，为当前批改提供参考信息。
        
        Args:
            question_details: 当前批改的题目详情
            batch_id: 批次ID
            
        Returns:
            记忆上下文，包含相关经验、风险提示、校准建议
        """
        # 提取题型
        question_types = set()
        for q in question_details:
            qt = q.get("question_type") or q.get("questionType")
            if qt:
                question_types.add(qt)
        
        # 检索相关错误模式
        error_patterns = self.retrieve_relevant_memories(
            question_types=list(question_types) if question_types else None,
            memory_types=[MemoryType.ERROR_PATTERN],
            max_results=5,
        )
        
        # 检索相关风险信号
        risk_signals = self.retrieve_relevant_memories(
            question_types=list(question_types) if question_types else None,
            memory_types=[MemoryType.RISK_SIGNAL],
            max_results=5,
        )
        
        # 检索修正历史
        correction_history = self.retrieve_relevant_memories(
            question_types=list(question_types) if question_types else None,
            memory_types=[MemoryType.CORRECTION_HISTORY],
            max_results=5,
        )
        
        # 获取置信度校准建议
        calibration_suggestions = {}
        for qt in question_types:
            # 计算该题型的平均预测置信度
            avg_confidence = 0.7  # 默认值
            qt_questions = [q for q in question_details if q.get("question_type") == qt]
            if qt_questions:
                confidences = [q.get("confidence", 0.7) for q in qt_questions]
                avg_confidence = sum(confidences) / len(confidences)
            
            suggestion = self.get_calibration_recommendation(qt, avg_confidence)
            if suggestion.get("has_data"):
                calibration_suggestions[qt] = suggestion
        
        # 获取批次内已发现的模式
        batch_patterns = {}
        if batch_id:
            batch_mem = self.get_batch_memory(batch_id)
            if batch_mem:
                batch_patterns = {
                    "error_patterns": batch_mem.error_patterns,
                    "risk_signals": batch_mem.risk_signals,
                    "high_risk_questions": batch_mem.high_risk_questions[-10:],
                }
        
        return {
            "historical_error_patterns": [
                {
                    "pattern": m.pattern,
                    "lesson": m.lesson,
                    "confidence": m.confidence,
                    "occurrence_count": m.occurrence_count,
                }
                for m in error_patterns
            ],
            "historical_risk_signals": [
                {
                    "signal": m.pattern,
                    "lesson": m.lesson,
                    "importance": m.importance.value,
                }
                for m in risk_signals
            ],
            "correction_history": [
                {
                    "pattern": m.pattern,
                    "lesson": m.lesson,
                    "context": m.context,
                }
                for m in correction_history
            ],
            "calibration_suggestions": calibration_suggestions,
            "batch_patterns": batch_patterns,
            "memory_stats": {
                "total_memories": len(self._long_term_memory),
                "error_pattern_count": len(self._type_index.get(MemoryType.ERROR_PATTERN, [])),
                "correction_count": len(self._type_index.get(MemoryType.CORRECTION_HISTORY, [])),
            },
        }
    
    def format_confession_memory_prompt(
        self,
        memory_context: Dict[str, Any],
    ) -> str:
        """
        将记忆上下文格式化为提示词文本
        
        Args:
            memory_context: generate_confession_context 返回的上下文
            
        Returns:
            str: 格式化的提示词片段
        """
        lines = []
        
        # 历史错误模式
        error_patterns = memory_context.get("historical_error_patterns", [])
        if error_patterns:
            lines.append("## 历史经验：常见错误模式")
            lines.append("基于历史批改数据，以下错误模式需要特别关注：")
            for i, pattern in enumerate(error_patterns[:5], 1):
                lines.append(
                    f"{i}. **{pattern['pattern']}** (出现 {pattern['occurrence_count']} 次, "
                    f"可信度 {pattern['confidence']:.0%})"
                )
                lines.append(f"   教训: {pattern['lesson']}")
            lines.append("")
        
        # 修正历史
        corrections = memory_context.get("correction_history", [])
        if corrections:
            lines.append("## 历史教训：重大修正记录")
            lines.append("以下是历史上被大幅修正的评分案例：")
            for i, corr in enumerate(corrections[:3], 1):
                lines.append(f"{i}. {corr['pattern']}")
                if corr.get("context"):
                    ctx = corr["context"]
                    if ctx.get("difference"):
                        lines.append(f"   分数差距: {abs(ctx['difference'])} 分")
            lines.append("")
        
        # 置信度校准
        calibrations = memory_context.get("calibration_suggestions", {})
        if calibrations:
            lines.append("## 置信度校准建议")
            for qt, suggestion in calibrations.items():
                if suggestion.get("has_data"):
                    adj = suggestion["adjustment"]
                    lines.append(
                        f"- **{qt}**: 历史数据显示置信度{'偏高' if adj < 0 else '偏低'} "
                        f"{abs(adj):.2f}，建议{'下调' if adj < 0 else '上调'}"
                    )
            lines.append("")
        
        # 当前批次模式
        batch_patterns = memory_context.get("batch_patterns", {})
        if batch_patterns.get("error_patterns"):
            lines.append("## 当前批次已发现的模式")
            for pattern, count in list(batch_patterns["error_patterns"].items())[:5]:
                lines.append(f"- {pattern}: 出现 {count} 次")
            lines.append("")
        
        if not lines:
            return ""
        
        return "\n".join(lines)
    
    # ==================== 持久化 ====================
    
    def _enforce_capacity_limit(self) -> None:
        """强制执行容量限制"""
        if len(self._long_term_memory) <= self.max_memory_entries:
            return
        
        # 按相关性得分排序，删除得分最低的
        entries = list(self._long_term_memory.values())
        entries.sort(key=lambda x: x.relevance_score)
        
        # 删除底部20%
        to_remove = entries[:len(entries) // 5]
        for entry in to_remove:
            del self._long_term_memory[entry.memory_id]
            # 更新索引
            if entry.memory_id in self._type_index.get(entry.memory_type, []):
                self._type_index[entry.memory_type].remove(entry.memory_id)
            for qt in entry.related_question_types:
                if entry.memory_id in self._question_type_index.get(qt, []):
                    self._question_type_index[qt].remove(entry.memory_id)
        
        logger.info(f"[Memory] 容量限制：删除 {len(to_remove)} 条低价值记忆")
    
    def _load_from_storage(self) -> None:
        """从存储加载记忆"""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 加载长期记忆
            for entry_data in data.get("long_term_memory", []):
                try:
                    entry = MemoryEntry.from_dict(entry_data)
                    self._long_term_memory[entry.memory_id] = entry
                    self._type_index[entry.memory_type].append(entry.memory_id)
                    for qt in entry.related_question_types:
                        self._question_type_index[qt].append(entry.memory_id)
                except Exception as e:
                    logger.warning(f"加载记忆条目失败: {e}")
            
            # 加载校准统计
            for qt, stats_data in data.get("calibration_stats", {}).items():
                self._calibration_stats[qt] = CalibrationStats(
                    question_type=qt,
                    predicted_confidences=stats_data.get("predicted_confidences", []),
                    actual_accuracies=stats_data.get("actual_accuracies", []),
                )
            
            logger.info(f"[Memory] 从存储加载 {len(self._long_term_memory)} 条记忆")
        except Exception as e:
            logger.error(f"加载记忆存储失败: {e}")
    
    def save_to_storage(self) -> None:
        """保存记忆到存储"""
        if not self.storage_path:
            return
        
        try:
            with self._lock:
                data = {
                    "long_term_memory": [
                        entry.to_dict() for entry in self._long_term_memory.values()
                    ],
                    "calibration_stats": {
                        qt: {
                            "predicted_confidences": stats.predicted_confidences[-1000:],  # 保留最近1000条
                            "actual_accuracies": stats.actual_accuracies[-1000:],
                        }
                        for qt, stats in self._calibration_stats.items()
                    },
                    "saved_at": datetime.now().isoformat(),
                }
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[Memory] 保存 {len(self._long_term_memory)} 条记忆到存储")
        except Exception as e:
            logger.error(f"保存记忆存储失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息"""
        with self._lock:
            return {
                "total_memories": len(self._long_term_memory),
                "memory_by_type": {
                    mt.value: len(ids) for mt, ids in self._type_index.items()
                },
                "total_batch_memories": len(self._batch_memories),
                "calibration_question_types": list(self._calibration_stats.keys()),
                "storage_path": self.storage_path,
            }


# 全局单例
_memory_service: Optional[GradingMemoryService] = None
_memory_lock = threading.Lock()


def get_memory_service() -> GradingMemoryService:
    """获取全局记忆服务单例"""
    global _memory_service
    
    with _memory_lock:
        if _memory_service is None:
            storage_path = os.getenv("GRADING_MEMORY_STORAGE_PATH")
            if not storage_path:
                # 默认存储路径
                storage_path = os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "data",
                    "grading_memory.json",
                )
            
            _memory_service = GradingMemoryService(
                storage_path=storage_path,
                max_memory_entries=int(os.getenv("GRADING_MEMORY_MAX_ENTRIES", "10000")),
                memory_ttl_days=int(os.getenv("GRADING_MEMORY_TTL_DAYS", "90")),
            )
        
        return _memory_service


# 导出
__all__ = [
    "MemoryType",
    "MemoryImportance",
    "MemoryEntry",
    "CalibrationStats",
    "BatchMemory",
    "GradingMemoryService",
    "get_memory_service",
]
