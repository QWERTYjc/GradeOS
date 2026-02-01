"""错误处理工具模块

实现完善的错误处理机制：
- 指数退避重试 (Requirement 9.1)
- 错误隔离 (Requirement 9.2)
- 部分结果保存 (Requirement 9.4)
- 详细错误日志 (Requirement 9.5)

验证：需求 9.1, 9.2, 9.4, 9.5
"""

import asyncio
import logging
import traceback
from typing import TypeVar, Callable, Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps


logger = logging.getLogger(__name__)


# ==================== 错误日志数据模型 ====================


@dataclass
class ErrorLog:
    """
    详细错误日志 (Requirement 9.5)

    记录错误类型、上下文、堆栈信息等详细信息。
    """

    timestamp: str  # ISO 格式时间戳
    error_type: str  # 错误类型
    error_message: str  # 错误消息
    context: Dict[str, Any]  # 上下文信息
    stack_trace: str  # 堆栈信息
    batch_id: Optional[str] = None  # 批次ID
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
            "resolved": self.resolved,
        }

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        context: Optional[Dict[str, Any]] = None,
        batch_id: Optional[str] = None,
        page_index: Optional[int] = None,
        question_id: Optional[str] = None,
        retry_count: int = 0,
    ) -> "ErrorLog":
        """从异常创建错误日志"""
        return cls(
            timestamp=datetime.now().isoformat(),
            error_type=type(exc).__name__,
            error_message=str(exc),
            context=context or {},
            stack_trace=traceback.format_exc(),
            batch_id=batch_id,
            page_index=page_index,
            question_id=question_id,
            retry_count=retry_count,
            resolved=False,
        )


# ==================== 指数退避重试 ====================


T = TypeVar("T")


class RetryConfig:
    """
    重试配置 (Requirement 9.1)

    配置指数退避重试策略。
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        初始化重试配置

        Args:
            max_retries: 最大重试次数
            initial_delay: 初始延迟（秒）
            max_delay: 最大延迟（秒）
            exponential_base: 指数基数
            jitter: 是否添加随机抖动
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, retry_count: int) -> float:
        """
        计算重试延迟 (Requirement 9.1)

        使用指数退避算法：delay = initial_delay * (exponential_base ^ retry_count)

        Args:
            retry_count: 当前重试次数（从0开始）

        Returns:
            float: 延迟时间（秒）
        """
        import random

        # 计算指数延迟
        delay = self.initial_delay * (self.exponential_base**retry_count)

        # 限制最大延迟
        delay = min(delay, self.max_delay)

        # 添加随机抖动（避免雷鸣群效应）
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)

        return delay


async def retry_with_exponential_backoff(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    error_log_context: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> T:
    """
    使用指数退避重试执行函数 (Requirement 9.1)

    API 调用失败时使用指数退避策略重试最多3次。

    Args:
        func: 要执行的异步函数
        *args: 函数参数
        config: 重试配置（可选）
        error_log_context: 错误日志上下文（可选）
        **kwargs: 函数关键字参数

    Returns:
        T: 函数返回值

    Raises:
        Exception: 所有重试失败后抛出最后一次的异常

    验证：需求 9.1
    """
    if config is None:
        config = RetryConfig()

    last_exception = None
    error_logs: List[ErrorLog] = []

    for retry_count in range(config.max_retries + 1):
        try:
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 成功执行，返回结果
            if retry_count > 0:
                logger.info(f"函数 {func.__name__} 在第 {retry_count} 次重试后成功执行")

            return result

        except Exception as e:
            last_exception = e

            # 记录错误日志 (Requirement 9.5)
            error_log = ErrorLog.from_exception(
                exc=e,
                context=error_log_context or {},
                retry_count=retry_count,
            )
            error_logs.append(error_log)

            # 如果还有重试机会
            if retry_count < config.max_retries:
                delay = config.calculate_delay(retry_count)

                logger.warning(
                    f"函数 {func.__name__} 执行失败（第 {retry_count + 1}/{config.max_retries + 1} 次）: {e}. "
                    f"将在 {delay:.2f} 秒后重试..."
                )

                # 等待后重试
                await asyncio.sleep(delay)
            else:
                # 所有重试都失败
                logger.error(
                    f"函数 {func.__name__} 在 {config.max_retries + 1} 次尝试后仍然失败: {e}",
                    exc_info=True,
                )

    # 所有重试都失败，抛出最后一次的异常
    raise last_exception


def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
):
    """
    重试装饰器 (Requirement 9.1)

    为异步函数添加指数退避重试功能。

    使用示例：
    ```python
    @with_retry(max_retries=3, initial_delay=1.0)
    async def call_api():
        # API 调用代码
        pass
    ```

    验证：需求 9.1
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
            )
            return await retry_with_exponential_backoff(func, *args, config=config, **kwargs)

        return wrapper

    return decorator


# ==================== 错误隔离 ====================


@dataclass
class IsolatedResult:
    """
    隔离执行结果 (Requirement 9.2)

    包含成功结果或错误信息，用于错误隔离。
    """

    success: bool
    result: Optional[Any] = None
    error: Optional[Exception] = None
    error_log: Optional[ErrorLog] = None
    index: Optional[int] = None  # 任务索引（用于批量处理）

    def is_success(self) -> bool:
        """是否成功"""
        return self.success

    def is_failure(self) -> bool:
        """是否失败"""
        return not self.success

    def get_result(self) -> Any:
        """获取结果（如果成功）"""
        if self.success:
            return self.result
        raise ValueError("任务失败，无法获取结果")

    def get_error(self) -> Exception:
        """获取错误（如果失败）"""
        if not self.success:
            return self.error
        raise ValueError("任务成功，无错误")


async def execute_with_isolation(
    func: Callable[..., T],
    *args,
    index: Optional[int] = None,
    error_log_context: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> IsolatedResult:
    """
    隔离执行函数 (Requirement 9.2)

    单个任务失败不影响其他任务，记录错误并继续处理。

    Args:
        func: 要执行的异步函数
        *args: 函数参数
        index: 任务索引（可选）
        error_log_context: 错误日志上下文（可选）
        **kwargs: 函数关键字参数

    Returns:
        IsolatedResult: 隔离执行结果

    验证：需求 9.2
    """
    try:
        # 执行函数
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)

        return IsolatedResult(
            success=True,
            result=result,
            index=index,
        )

    except Exception as e:
        # 记录错误日志 (Requirement 9.5)
        context = error_log_context or {}
        error_log = ErrorLog.from_exception(
            exc=e,
            context=context,
            batch_id=context.get("batch_id"),
            page_index=context.get("page_index"),
            question_id=context.get("question_id"),
        )

        # 记录到全局错误管理器
        error_manager = get_error_manager()
        error_manager.error_logs.append(error_log)

        logger.error(
            f"任务 {index if index is not None else 'N/A'} 执行失败: {e}. "
            f"错误已隔离，继续处理其他任务。",
            exc_info=True,
        )

        return IsolatedResult(
            success=False,
            error=e,
            error_log=error_log,
            index=index,
        )


async def execute_batch_with_isolation(
    func: Callable[[Any], T],
    items: List[Any],
    error_log_context: Optional[Dict[str, Any]] = None,
) -> List[IsolatedResult]:
    """
    批量隔离执行 (Requirement 9.2)

    对列表中的每个项目执行函数，单个失败不影响其他项目。

    Args:
        func: 要执行的异步函数（接受单个项目作为参数）
        items: 项目列表
        error_log_context: 错误日志上下文（可选）

    Returns:
        List[IsolatedResult]: 隔离执行结果列表

    验证：需求 9.2
    """
    tasks = []
    for i, item in enumerate(items):
        task = execute_with_isolation(
            func,
            item,
            index=i,
            error_log_context=error_log_context,
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    # 统计成功和失败数量
    success_count = sum(1 for r in results if r.is_success())
    failure_count = sum(1 for r in results if r.is_failure())

    logger.info(f"批量执行完成: 总数={len(items)}, " f"成功={success_count}, 失败={failure_count}")

    return results


# ==================== 部分结果保存 ====================


@dataclass
class PartialResults:
    """
    部分结果容器 (Requirement 9.4)

    用于保存已完成的部分结果，在不可恢复错误时使用。
    """

    batch_id: str
    completed_results: List[Any] = field(default_factory=list)
    failed_items: List[Dict[str, Any]] = field(default_factory=list)
    error_logs: List[ErrorLog] = field(default_factory=list)
    total_items: int = 0
    completed_count: int = 0
    failed_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_result(self, result: Any) -> None:
        """添加成功结果"""
        self.completed_results.append(result)
        self.completed_count += 1

    def add_failure(
        self,
        item_index: int,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加失败项"""
        error_log = ErrorLog.from_exception(
            exc=error,
            context=context or {},
            batch_id=self.batch_id,
        )

        self.failed_items.append(
            {
                "index": item_index,
                "error": str(error),
                "error_type": type(error).__name__,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.error_logs.append(error_log)
        self.failed_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "batch_id": self.batch_id,
            "total_items": self.total_items,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "completion_rate": (
                self.completed_count / self.total_items if self.total_items > 0 else 0
            ),
            "completed_results": self.completed_results,
            "failed_items": self.failed_items,
            "error_logs": [log.to_dict() for log in self.error_logs],
            "timestamp": self.timestamp,
        }

    def save_to_file(self, filepath: str) -> None:
        """
        保存部分结果到文件 (Requirement 9.4)

        在不可恢复错误时保存已完成的部分结果。

        Args:
            filepath: 保存路径

        验证：需求 9.4
        """
        import json

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

            logger.info(
                f"部分结果已保存到 {filepath}: "
                f"完成={self.completed_count}/{self.total_items}, "
                f"失败={self.failed_count}"
            )
        except Exception as e:
            logger.error(f"保存部分结果失败: {e}", exc_info=True)


async def execute_with_partial_save(
    func: Callable[[Any], T],
    items: List[Any],
    batch_id: str,
    save_path: Optional[str] = None,
    error_log_context: Optional[Dict[str, Any]] = None,
) -> PartialResults:
    """
    执行任务并支持部分结果保存 (Requirement 9.4)

    处理过程中如果发生不可恢复错误，保存已完成的部分结果。

    Args:
        func: 要执行的异步函数
        items: 项目列表
        batch_id: 批次ID
        save_path: 保存路径（可选，默认为 f"partial_results_{batch_id}.json"）
        error_log_context: 错误日志上下文（可选）

    Returns:
        PartialResults: 部分结果容器

    验证：需求 9.4
    """
    partial_results = PartialResults(
        batch_id=batch_id,
        total_items=len(items),
    )

    if save_path is None:
        save_path = f"partial_results_{batch_id}.json"

    try:
        # 使用隔离执行批量处理
        isolated_results = await execute_batch_with_isolation(func, items, error_log_context)

        # 收集结果
        for i, isolated_result in enumerate(isolated_results):
            if isolated_result.is_success():
                partial_results.add_result(isolated_result.get_result())
            else:
                partial_results.add_failure(
                    item_index=i,
                    error=isolated_result.get_error(),
                    context=error_log_context,
                )

        # 如果有失败项，保存部分结果
        if partial_results.failed_count > 0:
            logger.warning(
                f"批次 {batch_id} 有 {partial_results.failed_count} 个失败项，" f"保存部分结果..."
            )
            partial_results.save_to_file(save_path)

        return partial_results

    except Exception as e:
        # 不可恢复错误，保存已完成的部分结果 (Requirement 9.4)
        logger.error(
            f"批次 {batch_id} 发生不可恢复错误: {e}. "
            f"保存已完成的 {partial_results.completed_count} 个结果...",
            exc_info=True,
        )

        partial_results.save_to_file(save_path)

        # 重新抛出异常
        raise


# ==================== 错误日志管理器 ====================


class ErrorLogManager:
    """
    错误日志管理器 (Requirement 9.5)

    集中管理所有错误日志，提供查询和导出功能。
    """

    def __init__(self):
        self.error_logs: List[ErrorLog] = []

    def add_error(
        self,
        exc: Exception,
        context: Optional[Dict[str, Any]] = None,
        batch_id: Optional[str] = None,
        page_index: Optional[int] = None,
        question_id: Optional[str] = None,
        retry_count: int = 0,
    ) -> ErrorLog:
        """
        添加错误日志 (Requirement 9.5)

        记录详细的错误日志，包括错误类型、上下文、堆栈信息。

        Args:
            exc: 异常对象
            context: 上下文信息
            batch_id: 批次ID
            page_index: 页码
            question_id: 题号
            retry_count: 重试次数

        Returns:
            ErrorLog: 创建的错误日志

        验证：需求 9.5
        """
        error_log = ErrorLog.from_exception(
            exc=exc,
            context=context,
            batch_id=batch_id,
            page_index=page_index,
            question_id=question_id,
            retry_count=retry_count,
        )

        self.error_logs.append(error_log)

        # 记录到日志系统
        logger.error(
            f"错误日志已记录: {error_log.error_type} - {error_log.error_message}",
            extra={
                "batch_id": batch_id,
                "page_index": page_index,
                "question_id": question_id,
                "retry_count": retry_count,
            },
        )

        return error_log

    def get_errors_by_batch(self, batch_id: str) -> List[ErrorLog]:
        """获取指定批次的所有错误"""
        return [log for log in self.error_logs if log.batch_id == batch_id]

    def get_errors_by_page(self, page_index: int) -> List[ErrorLog]:
        """获取指定页面的所有错误"""
        return [log for log in self.error_logs if log.page_index == page_index]

    def get_unresolved_errors(self) -> List[ErrorLog]:
        """获取所有未解决的错误"""
        return [log for log in self.error_logs if not log.resolved]

    def mark_resolved(self, error_log: ErrorLog) -> None:
        """标记错误已解决"""
        error_log.resolved = True
        logger.info(f"错误已标记为已解决: {error_log.error_type}")

    def export_to_dict(self) -> Dict[str, Any]:
        """导出所有错误日志为字典"""
        return {
            "total_errors": len(self.error_logs),
            "unresolved_errors": len(self.get_unresolved_errors()),
            "error_logs": [log.to_dict() for log in self.error_logs],
            "export_timestamp": datetime.now().isoformat(),
        }

    def export_to_file(self, filepath: str) -> None:
        """导出错误日志到文件"""
        import json

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.export_to_dict(), f, ensure_ascii=False, indent=2)

            logger.info(f"错误日志已导出到 {filepath}")
        except Exception as e:
            logger.error(f"导出错误日志失败: {e}", exc_info=True)

    def clear(self) -> None:
        """清空所有错误日志"""
        self.error_logs.clear()
        logger.info("错误日志已清空")


# 全局错误日志管理器实例
_global_error_manager: Optional[ErrorLogManager] = None


def get_error_manager() -> ErrorLogManager:
    """获取全局错误日志管理器"""
    global _global_error_manager
    if _global_error_manager is None:
        _global_error_manager = ErrorLogManager()
    return _global_error_manager
