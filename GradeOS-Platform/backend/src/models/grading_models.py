"""
批改工作流优化 - 核心数据模型

本模块定义了批改工作流优化所需的核心数据结构，包括：
- QuestionRubric: 单题评分标准
- ScoringPoint: 得分点
- AlternativeSolution: 另类解法
- ScoringPointResult: 得分点评分结果
- QuestionResult: 单题评分结果
- PageGradingResult: 单页批改结果
- StudentResult: 学生批改结果
- CrossPageQuestion: 跨页题目信息
- BatchGradingResult: 批量批改结果
- StudentInfo: 学生信息
- ErrorLog: 错误日志

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


@dataclass
class ScoringPoint:
    """
    得分点
    
    表示评分标准中的单个得分点，包含描述、分值和是否必须。
    """
    description: str  # 得分点描述
    score: float  # 该得分点的分值
    is_required: bool = True  # 是否必须
    point_id: str = ""  # 得分点编号
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "description": self.description,
            "score": self.score,
            "is_required": self.is_required,
            "point_id": self.point_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringPoint":
        """从字典反序列化"""
        return cls(
            description=data["description"],
            score=data["score"],
            is_required=data.get("is_required", True),
            point_id=data.get("point_id", ""),
        )


@dataclass
class AlternativeSolution:
    """
    另类解法
    
    表示题目的另类解法，包含解法描述和评分条件。
    """
    description: str  # 解法描述
    scoring_conditions: str  # 评分条件
    max_score: float  # 该解法的最高分
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "description": self.description,
            "scoring_conditions": self.scoring_conditions,
            "max_score": self.max_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlternativeSolution":
        """从字典反序列化"""
        return cls(
            description=data["description"],
            scoring_conditions=data["scoring_conditions"],
            max_score=data["max_score"]
        )



@dataclass
class QuestionRubric:
    """
    单题评分标准
    
    包含题目的完整评分信息：题号、满分、题目内容、标准答案、得分点列表、另类解法等。
    
    Requirements: 1.1, 1.3
    """
    question_id: str  # 题号
    max_score: float  # 满分
    question_text: str = ""  # 题目内容
    question_type: Optional[str] = None  # objective/subjective/choice (optional)
    standard_answer: str = ""  # 标准答案
    scoring_points: List[ScoringPoint] = field(default_factory=list)  # 得分点列表
    alternative_solutions: List[AlternativeSolution] = field(default_factory=list)  # 另类解法
    grading_notes: str = ""  # 批改注意事项
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "question_id": self.question_id,
            "max_score": self.max_score,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "standard_answer": self.standard_answer,
            "scoring_points": [sp.to_dict() for sp in self.scoring_points],
            "alternative_solutions": [alt.to_dict() for alt in self.alternative_solutions],
            "grading_notes": self.grading_notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuestionRubric":
        """从字典反序列化"""
        return cls(
            question_id=data["question_id"],
            max_score=data["max_score"],
            question_text=data.get("question_text", ""),
            question_type=data.get("question_type") or data.get("questionType"),
            standard_answer=data.get("standard_answer", ""),
            scoring_points=[
                ScoringPoint.from_dict(sp) for sp in data.get("scoring_points", [])
            ],
            alternative_solutions=[
                AlternativeSolution.from_dict(alt) for alt in data.get("alternative_solutions", [])
            ],
            grading_notes=data.get("grading_notes", "")
        )
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "QuestionRubric":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))


class CitationQuality:
    """引用质量枚举"""
    EXACT = "exact"      # 精确引用
    PARTIAL = "partial"  # 部分引用
    NONE = "none"        # 无引用


@dataclass
class ScoringPointResult:
    """
    得分点评分结果
    
    记录单个得分点的评分情况，包含对应的得分点、获得的分数和证据。
    
    扩展字段（评分标准引用与置信度优化）：
    - rubric_reference: 评分标准引用（如 "1.2.a" 或原文摘要）
    - is_alternative_solution: 是否为另类解法
    - alternative_description: 另类解法描述
    - point_confidence: 该得分点的置信度
    - citation_quality: 引用质量（exact/partial/none）
    
    Requirements: 8.2
    """
    scoring_point: ScoringPoint  # 对应的得分点
    awarded: float  # 获得的分数
    evidence: str = ""  # 证据/依据
    
    # 新增字段：评分标准引用
    rubric_reference: Optional[str] = None  # 评分标准引用，如 "1.2.a" 或原文摘要
    is_alternative_solution: bool = False   # 是否为另类解法
    alternative_description: str = ""       # 另类解法描述
    point_confidence: float = 0.9           # 该得分点的置信度
    citation_quality: str = "exact"         # exact/partial/none
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "scoring_point": self.scoring_point.to_dict(),
            "awarded": self.awarded,
            "evidence": self.evidence,
            "rubric_reference": self.rubric_reference,
            "is_alternative_solution": self.is_alternative_solution,
            "alternative_description": self.alternative_description,
            "point_confidence": self.point_confidence,
            "citation_quality": self.citation_quality,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringPointResult":
        """从字典反序列化"""
        return cls(
            scoring_point=ScoringPoint.from_dict(data["scoring_point"]),
            awarded=data["awarded"],
            evidence=data.get("evidence", ""),
            rubric_reference=data.get("rubric_reference"),
            is_alternative_solution=data.get("is_alternative_solution", False),
            alternative_description=data.get("alternative_description", ""),
            point_confidence=data.get("point_confidence", 0.9),
            citation_quality=data.get("citation_quality", "exact"),
        )



@dataclass
class QuestionResult:
    """
    单题评分结果
    
    包含单道题目的完整评分信息，满足 Requirements 8.1-8.5：
    - 题目编号、得分、满分、置信度、反馈 (8.1)
    - 得分点明细列表 (8.2)
    - 页面索引列表 (8.3)
    - is_cross_page 标记 (8.4)
    - merge_source 字段 (8.5)
    - annotations 批注坐标列表 (8.6)
    """
    question_id: str  # 题号
    score: float  # 得分
    max_score: float  # 满分
    confidence: float  # 置信度 (0.0 - 1.0)
    feedback: str = ""  # 反馈
    scoring_point_results: List[ScoringPointResult] = field(default_factory=list)  # 得分点明细
    page_indices: List[int] = field(default_factory=list)  # 出现在哪些页面
    is_cross_page: bool = False  # 是否跨页题目
    merge_source: Optional[List[str]] = None  # 合并来源（如果是合并结果）
    student_answer: str = ""  # 学生答案
    question_type: Optional[str] = None  # objective/subjective/choice (optional)
    annotations: List[Dict[str, Any]] = field(default_factory=list)  # 批注坐标列表
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 (Requirements: 8.6)"""
        return {
            "question_id": self.question_id,
            "score": self.score,
            "max_score": self.max_score,
            "confidence": self.confidence,
            "feedback": self.feedback,
            "scoring_point_results": [spr.to_dict() for spr in self.scoring_point_results],
            "page_indices": self.page_indices,
            "is_cross_page": self.is_cross_page,
            "merge_source": self.merge_source,
            "student_answer": self.student_answer,
            "question_type": self.question_type,
            "annotations": self.annotations,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuestionResult":
        """从字典反序列化 (Requirements: 8.6)"""
        return cls(
            question_id=data["question_id"],
            score=data["score"],
            max_score=data["max_score"],
            confidence=data["confidence"],
            feedback=data.get("feedback", ""),
            scoring_point_results=[
                ScoringPointResult.from_dict(spr) 
                for spr in data.get("scoring_point_results", [])
            ],
            page_indices=data.get("page_indices", []),
            is_cross_page=data.get("is_cross_page", False),
            merge_source=data.get("merge_source"),
            student_answer=data.get("student_answer", ""),
            question_type=data.get("question_type") or data.get("questionType"),
            annotations=data.get("annotations", []),
        )
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "QuestionResult":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class StudentInfo:
    """
    学生信息
    
    从批改结果中识别到的学生信息。
    """
    student_id: Optional[str] = None  # 学号
    student_name: Optional[str] = None  # 姓名
    confidence: float = 0.0  # 识别置信度
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "student_id": self.student_id,
            "student_name": self.student_name,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudentInfo":
        """从字典反序列化"""
        return cls(
            student_id=data.get("student_id"),
            student_name=data.get("student_name"),
            confidence=data.get("confidence", 0.0)
        )



@dataclass
class PageGradingResult:
    """
    单页批改结果
    
    包含单个页面的批改结果，包括页码、题目结果列表、学生信息等。
    """
    page_index: int  # 页码
    question_results: List[QuestionResult] = field(default_factory=list)  # 该页的题目结果
    student_info: Optional[StudentInfo] = None  # 学生信息（如果识别到）
    is_blank_page: bool = False  # 是否空白页
    raw_response: str = ""  # LLM 原始响应
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 (Requirements: 8.6)"""
        return {
            "page_index": self.page_index,
            "question_results": [qr.to_dict() for qr in self.question_results],
            "student_info": self.student_info.to_dict() if self.student_info else None,
            "is_blank_page": self.is_blank_page,
            "raw_response": self.raw_response
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageGradingResult":
        """从字典反序列化 (Requirements: 8.6)"""
        student_info = None
        if data.get("student_info"):
            student_info = StudentInfo.from_dict(data["student_info"])
        
        return cls(
            page_index=data["page_index"],
            question_results=[
                QuestionResult.from_dict(qr) 
                for qr in data.get("question_results", [])
            ],
            student_info=student_info,
            is_blank_page=data.get("is_blank_page", False),
            raw_response=data.get("raw_response", "")
        )
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "PageGradingResult":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class StudentResult:
    """
    学生批改结果
    
    包含单个学生的完整批改结果，包括学生标识、分数、各题结果等。
    
    Requirements: 6.3, 6.5
    """
    student_key: str  # 学生标识
    student_id: Optional[str] = None  # 学号
    student_name: Optional[str] = None  # 姓名
    grading_mode: Optional[str] = None  # standard/assist_teacher/assist_student
    start_page: int = 0  # 起始页
    end_page: int = 0  # 结束页
    total_score: float = 0.0  # 总分
    max_total_score: float = 0.0  # 满分
    question_results: List[QuestionResult] = field(default_factory=list)  # 各题结果
    confidence: float = 0.0  # 置信度
    needs_confirmation: bool = False  # 是否需要人工确认
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 (Requirements: 8.6)"""
        return {
            "student_key": self.student_key,
            "student_id": self.student_id,
            "student_name": self.student_name,
            "grading_mode": self.grading_mode,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "total_score": self.total_score,
            "max_total_score": self.max_total_score,
            "question_results": [qr.to_dict() for qr in self.question_results],
            "confidence": self.confidence,
            "needs_confirmation": self.needs_confirmation
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudentResult":
        """从字典反序列化 (Requirements: 8.6)"""
        return cls(
            student_key=data["student_key"],
            student_id=data.get("student_id"),
            student_name=data.get("student_name"),
            grading_mode=data.get("grading_mode") or data.get("gradingMode"),
            start_page=data.get("start_page", 0),
            end_page=data.get("end_page", 0),
            total_score=data.get("total_score", 0.0),
            max_total_score=data.get("max_total_score", 0.0),
            question_results=[
                QuestionResult.from_dict(qr) 
                for qr in data.get("question_results", [])
            ],
            confidence=data.get("confidence", 0.0),
            needs_confirmation=data.get("needs_confirmation", False)
        )
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "StudentResult":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))



@dataclass
class CrossPageQuestion:
    """
    跨页题目信息
    
    ⚠️ 已废弃 (DEPRECATED)
    ======================
    当前架构使用一次 LLM 调用批改整个学生的所有页面（grade_student），
    LLM 自己能看到跨页的完整答案，不再需要后续的跨页合并逻辑。
    
    此类保留仅用于向后兼容（如反序列化旧数据）。
    
    ---
    原设计：记录跨越多个页面的题目信息，用于合并处理。
    
    Requirements: 2.1, 2.2, 2.3 (已由 grade_student 内部实现)
    """
    question_id: str  # 题目编号
    page_indices: List[int] = field(default_factory=list)  # 涉及的页面索引
    confidence: float = 0.0  # 合并置信度
    merge_reason: str = ""  # 合并原因
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "question_id": self.question_id,
            "page_indices": self.page_indices,
            "confidence": self.confidence,
            "merge_reason": self.merge_reason
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrossPageQuestion":
        """从字典反序列化"""
        return cls(
            question_id=data["question_id"],
            page_indices=data.get("page_indices", []),
            confidence=data.get("confidence", 0.0),
            merge_reason=data.get("merge_reason", "")
        )


@dataclass
class BatchGradingResult:
    """
    批量批改结果
    
    包含整个批量批改任务的结果，包括学生结果列表、跨页题目信息、错误列表等。
    """
    batch_id: str  # 批次ID
    student_results: List[StudentResult] = field(default_factory=list)  # 学生结果列表
    total_pages: int = 0  # 总页数
    processed_pages: int = 0  # 已处理页数
    cross_page_questions: List[CrossPageQuestion] = field(default_factory=list)  # 跨页题目信息
    errors: List[Dict[str, Any]] = field(default_factory=list)  # 错误列表
    timestamps: Dict[str, str] = field(default_factory=dict)  # 时间戳
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 (Requirements: 8.6)"""
        return {
            "batch_id": self.batch_id,
            "student_results": [sr.to_dict() for sr in self.student_results],
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
            "cross_page_questions": [cpq.to_dict() for cpq in self.cross_page_questions],
            "errors": self.errors,
            "timestamps": self.timestamps
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchGradingResult":
        """从字典反序列化 (Requirements: 8.6)"""
        return cls(
            batch_id=data["batch_id"],
            student_results=[
                StudentResult.from_dict(sr) 
                for sr in data.get("student_results", [])
            ],
            total_pages=data.get("total_pages", 0),
            processed_pages=data.get("processed_pages", 0),
            cross_page_questions=[
                CrossPageQuestion.from_dict(cpq) 
                for cpq in data.get("cross_page_questions", [])
            ],
            errors=data.get("errors", []),
            timestamps=data.get("timestamps", {})
        )
    
    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "BatchGradingResult":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))



@dataclass
class ErrorLog:
    """
    错误日志
    
    记录批改过程中的错误信息，用于调试和审计。
    
    Requirements: 9.5
    """
    timestamp: str  # ISO 格式时间戳
    error_type: str  # 错误类型
    error_message: str  # 错误消息
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文信息
    stack_trace: str = ""  # 堆栈信息
    batch_id: str = ""  # 批次ID
    page_index: Optional[int] = None  # 页码（如果适用）
    question_id: Optional[str] = None  # 题号（如果适用）
    retry_count: int = 0  # 重试次数
    resolved: bool = False  # 是否已解决
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "timestamp": self.timestamp,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "context": self.context,
            "stack_trace": self.stack_trace,
            "batch_id": self.batch_id,
            "page_index": self.page_index,
            "question_id": self.question_id,
            "retry_count": self.retry_count,
            "resolved": self.resolved
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorLog":
        """从字典反序列化"""
        return cls(
            timestamp=data["timestamp"],
            error_type=data["error_type"],
            error_message=data["error_message"],
            context=data.get("context", {}),
            stack_trace=data.get("stack_trace", ""),
            batch_id=data.get("batch_id", ""),
            page_index=data.get("page_index"),
            question_id=data.get("question_id"),
            retry_count=data.get("retry_count", 0),
            resolved=data.get("resolved", False)
        )
    
    @classmethod
    def create_now(
        cls,
        error_type: str,
        error_message: str,
        **kwargs
    ) -> "ErrorLog":
        """创建当前时间的错误日志"""
        return cls(
            timestamp=datetime.utcnow().isoformat(),
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )


# 导出所有模型
__all__ = [
    "ScoringPoint",
    "AlternativeSolution",
    "QuestionRubric",
    "ScoringPointResult",
    "CitationQuality",
    "QuestionResult",
    "StudentInfo",
    "PageGradingResult",
    "StudentResult",
    "CrossPageQuestion",
    "BatchGradingResult",
    "ErrorLog",
]
