"""LangGraph 重试策略实现

本模块提供节点级重试和超时控制，用于处理 LLM API 限流等临时故障。
"""

from dataclasses import dataclass, field
from typing import Callable, Any, Optional, List, TypeVar, Awaitable
import asyncio
import logging
from datetime import datetime

from .state import GradingGraphState

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """重试策略配置

    定义节点执行失败时的重试行为。

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5

    Attributes:
        initial_interval: 初始重试间隔（秒）
        backoff_coefficient: 退避系数（每次重试间隔乘以此系数）
        maximum_interval: 最大重试间隔（秒）
        maximum_attempts: 最大重试次数
        non_retryable_errors: 不可重试的错误类型列表
        timeout: 单次执行超时时间（秒），None 表示无超时
    """

    initial_interval: float = 1.0
    backoff_coefficient: float = 2.0
    maximum_interval: float = 60.0
    maximum_attempts: int = 3
    non_retryable_errors: List[type] = field(default_factory=lambda: [ValueError, TypeError])
    timeout: Optional[float] = None

    def calculate_interval(self, attempt: int) -> float:
        """计算指定重试次数的等待间隔

        使用指数退避算法：interval = min(initial * coefficient^attempt, maximum)

        Args:
            attempt: 重试次数（从 0 开始）

        Returns:
            等待间隔（秒）
        """
        interval = self.initial_interval * (self.backoff_coefficient**attempt)
        return min(interval, self.maximum_interval)


async def with_retry(func: Callable[..., Awaitable[T]], config: RetryConfig, *args, **kwargs) -> T:
    """带重试的异步函数执行

    根据配置的重试策略执行函数，失败时自动重试。

    Requirements: 4.1, 4.4

    Args:
        func: 要执行的异步函数
        config: 重试配置
        *args: 函数位置参数
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果

    Raises:
        最后一次执行的异常（如果所有重试都失败）

    Example:
        >>> config = RetryConfig(maximum_attempts=3)
        >>> result = await with_retry(some_async_func, config, arg1, arg2)
    """
    last_error: Optional[Exception] = None

    for attempt in range(config.maximum_attempts):
        try:
            # 如果配置了超时，使用 asyncio.wait_for
            if config.timeout:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=config.timeout)
            else:
                return await func(*args, **kwargs)

        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning(
                f"执行超时（{config.timeout}s），"
                f"第 {attempt + 1}/{config.maximum_attempts} 次尝试"
            )

        except Exception as e:
            # 检查是否为不可重试错误
            if any(isinstance(e, err_type) for err_type in config.non_retryable_errors):
                logger.error(f"遇到不可重试错误: {type(e).__name__}: {e}")
                raise

            last_error = e

            if attempt < config.maximum_attempts - 1:
                # 计算等待间隔
                interval = config.calculate_interval(attempt)
                logger.warning(
                    f"执行失败: {type(e).__name__}: {e}，"
                    f"第 {attempt + 1}/{config.maximum_attempts} 次尝试，"
                    f"等待 {interval:.2f}s 后重试"
                )
                await asyncio.sleep(interval)
            else:
                logger.error(
                    f"重试次数耗尽（{config.maximum_attempts} 次），"
                    f"最后错误: {type(e).__name__}: {e}"
                )

    # 所有重试都失败，抛出最后一次的异常
    if last_error:
        raise last_error

    # 理论上不会到达这里
    raise RuntimeError("with_retry: 未知错误")


def create_retryable_node(
    node_func: Callable[[GradingGraphState], Awaitable[GradingGraphState]],
    retry_config: RetryConfig,
    fallback_func: Optional[
        Callable[[GradingGraphState, Exception], Awaitable[GradingGraphState]]
    ] = None,
    node_name: Optional[str] = None,
) -> Callable[[GradingGraphState], Awaitable[GradingGraphState]]:
    """创建带重试的节点函数

    包装节点函数，添加重试逻辑和可选的降级处理。

    Requirements: 4.1, 4.2, 4.3

    Args:
        node_func: 原始节点函数
        retry_config: 重试配置
        fallback_func: 降级函数（可选），当所有重试都失败时调用
        node_name: 节点名称（用于日志），默认使用函数名

    Returns:
        包装后的节点函数

    Example:
        >>> config = RetryConfig(maximum_attempts=3)
        >>> retryable_node = create_retryable_node(
        ...     my_node_func,
        ...     config,
        ...     fallback_func=my_fallback
        ... )
    """
    name = node_name or node_func.__name__

    async def wrapped_node(state: GradingGraphState) -> GradingGraphState:
        """包装后的节点函数"""
        try:
            # 使用重试逻辑执行节点
            return await with_retry(node_func, retry_config, state)

        except Exception as e:
            # 如果提供了降级函数，执行降级逻辑
            if fallback_func:
                logger.warning(f"节点 {name} 执行失败，执行降级逻辑: {type(e).__name__}: {e}")
                try:
                    return await fallback_func(state, e)
                except Exception as fallback_error:
                    logger.error(
                        f"降级逻辑也失败了: {type(fallback_error).__name__}: {fallback_error}"
                    )
                    # 降级也失败，记录错误到状态
                    return _record_error_to_state(state, name, fallback_error)
            else:
                # 没有降级函数，记录错误到状态
                logger.error(f"节点 {name} 执行失败，无降级逻辑: {type(e).__name__}: {e}")
                return _record_error_to_state(state, name, e)

    # 保留原函数的元数据
    wrapped_node.__name__ = f"retryable_{name}"
    wrapped_node.__doc__ = f"带重试的 {name} 节点"

    return wrapped_node


def _record_error_to_state(
    state: GradingGraphState, node_name: str, error: Exception
) -> GradingGraphState:
    """将错误记录到状态中

    Args:
        state: 当前状态
        node_name: 节点名称
        error: 异常对象

    Returns:
        更新后的状态
    """
    errors = state.get("errors", [])
    errors.append(
        {
            "node": node_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
        }
    )

    # 更新重试计数
    retry_count = state.get("retry_count", 0) + 1

    return {**state, "errors": errors, "retry_count": retry_count}


# 预定义的重试配置

# 默认配置：适用于大多数节点
DEFAULT_RETRY_CONFIG = RetryConfig(
    initial_interval=1.0,
    backoff_coefficient=2.0,
    maximum_interval=60.0,
    maximum_attempts=3,
    timeout=None,
)

# LLM API 配置：处理 API 限流
LLM_API_RETRY_CONFIG = RetryConfig(
    initial_interval=2.0,
    backoff_coefficient=2.0,
    maximum_interval=120.0,
    maximum_attempts=5,
    timeout=300.0,  # 5 分钟超时
    non_retryable_errors=[ValueError, TypeError, KeyError],
)

# 快速失败配置：不重试或只重试一次
FAST_FAIL_RETRY_CONFIG = RetryConfig(
    initial_interval=0.5,
    backoff_coefficient=1.0,
    maximum_interval=1.0,
    maximum_attempts=1,
    timeout=30.0,
)

# 持久化操作配置：数据库写入等
PERSISTENCE_RETRY_CONFIG = RetryConfig(
    initial_interval=0.5,
    backoff_coefficient=1.5,
    maximum_interval=10.0,
    maximum_attempts=5,
    timeout=60.0,
)
