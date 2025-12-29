"""
批改相关的 Agent Skills

提供批改工作流中 Agent 可调用的技能模块，实现模块化的批改能力。
支持技能注册、调用日志记录、错误处理和重试机制。

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import asyncio
import functools
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

from src.models.grading_models import (
    QuestionRubric,
    QuestionResult,
    PageGradingResult,
    CrossPageQuestion,
)
from src.services.rubric_registry import RubricRegistry, RubricQueryResult
from src.services.question_merger import QuestionMerger

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ==================== 数据结构 ====================


@dataclass
class SkillError:
    """
    Skill 错误信息
    
    Requirements: 5.6 - 返回明确错误信息
    """
    error_type: str  # 错误类型
    message: str  # 错误消息
    details: Optional[Dict[str, Any]] = None  # 详细信息
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    retry_count: int = 0  # 已重试次数
    is_retryable: bool = True  # 是否可重试
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "is_retryable": self.is_retryable,
        }


@dataclass
class SkillResult(Generic[T]):
    """
    Skill 执行结果
    
    封装 Skill 的执行结果，包含成功/失败状态、数据和错误信息。
    """
    success: bool  # 是否成功
    data: Optional[T] = None  # 返回数据
    error: Optional[SkillError] = None  # 错误信息
    execution_time_ms: float = 0.0  # 执行时间（毫秒）
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "success": self.success,
            "data": self.data if not hasattr(self.data, "to_dict") else self.data.to_dict(),
            "error": self.error.to_dict() if self.error else None,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class SkillCallLog:
    """
    Skill 调用日志
    
    Requirements: 5.5 - 记录调用日志用于调试和审计
    """
    skill_name: str  # Skill 名称
    timestamp: str  # 调用时间
    args: Dict[str, Any]  # 调用参数（敏感信息已脱敏）
    success: bool  # 是否成功
    execution_time_ms: float  # 执行时间
    error_message: Optional[str] = None  # 错误消息
    retry_count: int = 0  # 重试次数
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "skill_name": self.skill_name,
            "timestamp": self.timestamp,
            "args": self.args,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


# ==================== Skill 装饰器和注册机制 ====================


class SkillRegistry:
    """
    Skill 注册中心
    
    管理所有注册的 Skills，提供查询和调用功能。
    """
    
    def __init__(self):
        self._skills: Dict[str, Callable] = {}
        self._call_logs: List[SkillCallLog] = []
        self._max_logs = 1000  # 最大日志数量
    
    def register(self, name: str, func: Callable) -> None:
        """注册 Skill"""
        self._skills[name] = func
        logger.info(f"注册 Skill: {name}")
    
    def get(self, name: str) -> Optional[Callable]:
        """获取 Skill"""
        return self._skills.get(name)
    
    def list_skills(self) -> List[str]:
        """列出所有 Skill 名称"""
        return list(self._skills.keys())
    
    def add_log(self, log: SkillCallLog) -> None:
        """添加调用日志"""
        self._call_logs.append(log)
        # 限制日志数量
        if len(self._call_logs) > self._max_logs:
            self._call_logs = self._call_logs[-self._max_logs:]
    
    def get_logs(self, limit: int = 100) -> List[SkillCallLog]:
        """获取最近的调用日志"""
        return self._call_logs[-limit:]
    
    def clear_logs(self) -> None:
        """清空日志"""
        self._call_logs.clear()


# 全局 Skill 注册中心
_skill_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """获取全局 Skill 注册中心"""
    return _skill_registry


def skill(
    name: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    log_args: bool = True,
):
    """
    Skill 装饰器
    
    将函数注册为 Skill，并添加日志记录、错误处理和重试机制。
    
    Args:
        name: Skill 名称，默认使用函数名
        max_retries: 最大重试次数 (Requirements: 5.6)
        retry_delay: 重试延迟（秒）
        log_args: 是否记录调用参数
        
    Requirements: 5.5, 5.6
    """
    def decorator(func: Callable) -> Callable:
        skill_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> SkillResult:
            start_time = datetime.utcnow()
            retry_count = 0
            last_error: Optional[SkillError] = None
            
            # 准备日志参数（脱敏处理）
            log_kwargs = {}
            if log_args:
                for k, v in kwargs.items():
                    if k in ("image", "images", "page_image"):
                        log_kwargs[k] = f"<bytes:{len(v) if isinstance(v, bytes) else 'list'}>"
                    elif isinstance(v, (RubricRegistry, QuestionMerger)):
                        log_kwargs[k] = f"<{type(v).__name__}>"
                    else:
                        log_kwargs[k] = str(v)[:100]  # 截断长字符串
            
            while retry_count <= max_retries:
                try:
                    # 执行 Skill
                    result = await func(*args, **kwargs)
                    
                    # 计算执行时间
                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                    
                    # 记录成功日志
                    log = SkillCallLog(
                        skill_name=skill_name,
                        timestamp=start_time.isoformat(),
                        args=log_kwargs,
                        success=True,
                        execution_time_ms=execution_time,
                        retry_count=retry_count,
                    )
                    _skill_registry.add_log(log)
                    
                    logger.debug(f"Skill {skill_name} 执行成功, 耗时 {execution_time:.2f}ms")
                    
                    return SkillResult(
                        success=True,
                        data=result,
                        execution_time_ms=execution_time,
                    )
                    
                except Exception as e:
                    retry_count += 1
                    last_error = SkillError(
                        error_type=type(e).__name__,
                        message=str(e),
                        details={"traceback": traceback.format_exc()},
                        retry_count=retry_count,
                        is_retryable=retry_count < max_retries,
                    )
                    
                    logger.warning(
                        f"Skill {skill_name} 执行失败 (重试 {retry_count}/{max_retries}): {e}"
                    )
                    
                    if retry_count <= max_retries:
                        # 指数退避重试
                        await asyncio.sleep(retry_delay * (2 ** (retry_count - 1)))
            
            # 所有重试都失败
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 记录失败日志
            log = SkillCallLog(
                skill_name=skill_name,
                timestamp=start_time.isoformat(),
                args=log_kwargs,
                success=False,
                execution_time_ms=execution_time,
                error_message=last_error.message if last_error else "Unknown error",
                retry_count=retry_count,
            )
            _skill_registry.add_log(log)
            
            logger.error(f"Skill {skill_name} 执行失败，已重试 {max_retries} 次")
            
            return SkillResult(
                success=False,
                error=last_error,
                execution_time_ms=execution_time,
            )
        
        # 注册 Skill
        _skill_registry.register(skill_name, wrapper)
        
        return wrapper
    
    return decorator


# ==================== GradingSkills 类 ====================


class GradingSkills:
    """
    批改相关的 Agent Skills
    
    提供批改工作流中 Agent 可调用的技能模块：
    - get_rubric_for_question: 获取指定题目的评分标准 (Req 5.1)
    - identify_question_numbers: 从页面图像中识别题目编号 (Req 5.2)
    - detect_cross_page_questions: 检测跨页题目 (Req 5.3)
    - merge_question_results: 合并同一题目的多个评分结果 (Req 5.4)
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
    """
    
    def __init__(
        self,
        rubric_registry: Optional[RubricRegistry] = None,
        question_merger: Optional[QuestionMerger] = None,
        llm_client: Optional[Any] = None,
    ):
        """
        初始化 GradingSkills
        
        Args:
            rubric_registry: 评分标准注册中心
            question_merger: 题目合并器
            llm_client: LLM 客户端（用于视觉识别）
        """
        self._rubric_registry = rubric_registry
        self._question_merger = question_merger or QuestionMerger()
        self._llm_client = llm_client
        self._page_index_contexts: Optional[Dict[int, Dict[str, Any]]] = None
    
    @property
    def rubric_registry(self) -> Optional[RubricRegistry]:
        """获取评分标准注册中心"""
        return self._rubric_registry
    
    @rubric_registry.setter
    def rubric_registry(self, registry: RubricRegistry) -> None:
        """设置评分标准注册中心"""
        self._rubric_registry = registry
    
    @property
    def question_merger(self) -> QuestionMerger:
        """获取题目合并器"""
        return self._question_merger
    
    @property
    def llm_client(self) -> Optional[Any]:
        """获取 LLM 客户端"""
        return self._llm_client
    
    @llm_client.setter
    def llm_client(self, client: Any) -> None:
        """设置 LLM 客户端"""
        self._llm_client = client

    @property
    def page_index_contexts(self) -> Optional[Dict[int, Dict[str, Any]]]:
        """获取页级索引上下文"""
        return self._page_index_contexts

    @page_index_contexts.setter
    def page_index_contexts(self, contexts: Dict[int, Dict[str, Any]]) -> None:
        """设置页级索引上下文"""
        self._page_index_contexts = contexts

    # ==================== Skill 方法 ====================
    
    @skill(name="get_rubric_for_question", max_retries=1)
    async def get_rubric_for_question(
        self,
        question_id: str,
        registry: Optional[RubricRegistry] = None,
    ) -> RubricQueryResult:
        """
        获取指定题目的评分标准
        
        从 RubricRegistry 获取指定题目的评分标准，包括得分点、标准答案、另类解法。
        
        Args:
            question_id: 题目编号（如 "1", "7a", "15"）
            registry: 评分标准注册中心，为 None 时使用实例的 registry
            
        Returns:
            RubricQueryResult: 包含评分标准、是否默认、置信度等信息
            
        Requirements: 5.1, 1.1
        """
        reg = registry or self._rubric_registry
        if reg is None:
            raise ValueError("未设置评分标准注册中心 (RubricRegistry)")
        
        result = reg.get_rubric_for_question(question_id)
        
        logger.info(
            f"获取题目 {question_id} 的评分标准: "
            f"is_default={result.is_default}, confidence={result.confidence}"
        )
        
        return result

    @skill(name="get_index_context_for_page", max_retries=1, log_args=False)
    async def get_index_context_for_page(
        self,
        page_index: int,
        page_index_contexts: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        获取指定页面的索引上下文

        用于在批改时注入题目边界/学生信息等上下文。
        """
        contexts = page_index_contexts or self._page_index_contexts or {}
        context = contexts.get(page_index)
        if not context:
            return {"page_index": page_index, "missing": True}

        allowed_keys = {
            "page_index",
            "question_numbers",
            "first_question",
            "continuation_of",
            "student_key",
            "student_info",
            "is_cover_page",
            "index_notes",
            "is_first_page",
        }
        return {k: context.get(k) for k in allowed_keys if k in context}
    
    @skill(name="identify_question_numbers", max_retries=3, retry_delay=2.0)
    async def identify_question_numbers(
        self,
        page_image: bytes,
        llm_client: Optional[Any] = None,
    ) -> List[str]:
        """
        从页面图像中识别题目编号
        
        调用 LLM 视觉能力分析页面图像，识别其中的题目编号。
        
        Args:
            page_image: 页面图像字节
            llm_client: LLM 客户端，为 None 时使用实例的 client
            
        Returns:
            List[str]: 识别出的题目编号列表
            
        Requirements: 5.2
        """
        import base64
        import json
        
        client = llm_client or self._llm_client
        if client is None:
            raise ValueError("未设置 LLM 客户端")
        
        # 构建识别提示词
        prompt = """请分析这张学生答题图像，识别其中出现的所有题目编号。

任务：
1. 找出页面中所有可见的题目编号
2. 包括大题号（如 1, 2, 3）和小题号（如 1a, 1b, 2.1, 2.2）
3. 按照在页面中出现的顺序排列

输出格式（JSON）：
```json
{
    "question_numbers": ["1", "2", "3a", "3b"],
    "confidence": 0.95
}
```

注意：
- 只返回题目编号，不要返回其他内容
- 如果页面是空白页或没有题目，返回空列表
- 题目编号应该是字符串格式"""

        # 转换图像为 base64
        if isinstance(page_image, bytes):
            img_b64 = base64.b64encode(page_image).decode("utf-8")
        else:
            img_b64 = page_image
        
        # 调用 LLM
        from langchain_core.messages import HumanMessage
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{img_b64}",
                },
            ]
        )
        
        response = await client.ainvoke([message])
        
        # 解析响应
        response_text = str(response.content)
        
        # 提取 JSON
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text
        
        try:
            result = json.loads(json_text)
            question_numbers = result.get("question_numbers", [])
        except json.JSONDecodeError:
            # 尝试直接提取数字
            import re
            question_numbers = re.findall(r'\d+[a-zA-Z]?', response_text)
        
        logger.info(f"识别到 {len(question_numbers)} 个题目编号: {question_numbers}")
        
        return question_numbers
    
    @skill(name="detect_cross_page_questions", max_retries=1)
    async def detect_cross_page_questions(
        self,
        page_results: List[PageGradingResult],
    ) -> List[CrossPageQuestion]:
        """
        检测跨页题目
        
        封装 QuestionMerger 的跨页检测功能，识别跨越多个页面的同一道题目。
        
        Args:
            page_results: 各页面的批改结果
            
        Returns:
            List[CrossPageQuestion]: 检测到的跨页题目列表
            
        Requirements: 5.3
        """
        cross_page_questions = self._question_merger.detect_cross_page_questions(
            page_results
        )
        
        logger.info(f"检测到 {len(cross_page_questions)} 个跨页题目")
        
        return cross_page_questions
    
    @skill(name="merge_question_results", max_retries=1)
    async def merge_question_results(
        self,
        results: List[QuestionResult],
        cross_page_info: Optional[CrossPageQuestion] = None,
    ) -> QuestionResult:
        """
        合并同一题目的多个评分结果
        
        封装 QuestionMerger 的合并功能，将跨页题目的多个评分结果合并为单一结果。
        
        Args:
            results: 待合并的评分结果列表
            cross_page_info: 跨页信息（如果是跨页题目）
            
        Returns:
            QuestionResult: 合并后的评分结果
            
        Requirements: 5.4
        """
        if not results:
            raise ValueError("没有可合并的结果")
        
        if len(results) == 1 and cross_page_info is None:
            return results[0]
        
        # 如果没有跨页信息，创建一个默认的
        if cross_page_info is None:
            page_indices = []
            for r in results:
                page_indices.extend(r.page_indices)
            page_indices = sorted(set(page_indices))
            
            cross_page_info = CrossPageQuestion(
                question_id=results[0].question_id,
                page_indices=page_indices,
                confidence=0.8,
                merge_reason="手动合并",
            )
        
        # 使用 QuestionMerger 的内部方法进行合并
        merged = self._question_merger._merge_question_results(results, cross_page_info)
        
        logger.info(
            f"合并题目 {merged.question_id} 的 {len(results)} 个结果, "
            f"得分: {merged.score}/{merged.max_score}"
        )
        
        return merged
    
    @skill(name="merge_all_cross_page_results", max_retries=1)
    async def merge_all_cross_page_results(
        self,
        page_results: List[PageGradingResult],
        cross_page_questions: List[CrossPageQuestion],
    ) -> List[QuestionResult]:
        """
        合并所有跨页题目的评分结果
        
        批量处理跨页题目合并，返回合并后的完整题目结果列表。
        
        Args:
            page_results: 各页面的批改结果
            cross_page_questions: 跨页题目信息列表
            
        Returns:
            List[QuestionResult]: 合并后的题目结果列表
        """
        merged_results = self._question_merger.merge_cross_page_results(
            page_results, cross_page_questions
        )
        
        logger.info(f"合并完成，共 {len(merged_results)} 道题目")
        
        return merged_results


# ==================== 便捷函数 ====================


def create_grading_skills(
    rubric_registry: Optional[RubricRegistry] = None,
    question_merger: Optional[QuestionMerger] = None,
    llm_client: Optional[Any] = None,
) -> GradingSkills:
    """
    创建 GradingSkills 实例的便捷函数
    
    Args:
        rubric_registry: 评分标准注册中心
        question_merger: 题目合并器
        llm_client: LLM 客户端
        
    Returns:
        GradingSkills: 配置好的 GradingSkills 实例
    """
    return GradingSkills(
        rubric_registry=rubric_registry,
        question_merger=question_merger,
        llm_client=llm_client,
    )


# 导出
__all__ = [
    "GradingSkills",
    "skill",
    "SkillResult",
    "SkillError",
    "SkillCallLog",
    "SkillRegistry",
    "get_skill_registry",
    "create_grading_skills",
]
