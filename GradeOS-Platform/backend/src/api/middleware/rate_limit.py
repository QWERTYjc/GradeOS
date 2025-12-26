"""限流中间件"""

import logging
from typing import Callable
from datetime import datetime, timezone

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from src.services.rate_limiter import RateLimiter


logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    API 限流中间件
    
    对所有 API 端点应用限流策略，防止滥用和保护系统稳定性。
    当请求超出限制时返回 429 状态码和 retry-after 头。
    
    验证：需求 8.3
    """
    
    def __init__(
        self,
        app,
        redis_client: redis.Redis,
        max_requests: int = 100,
        window_seconds: int = 60,
        key_prefix: str = "api_rate_limit"
    ):
        """
        初始化限流中间件
        
        Args:
            app: FastAPI 应用实例
            redis_client: Redis 异步客户端
            max_requests: 时间窗口内允许的最大请求数（默认 100）
            window_seconds: 时间窗口大小（秒，默认 60）
            key_prefix: Redis 键前缀
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter(redis_client, key_prefix)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def _get_client_identifier(self, request: Request) -> str:
        """
        获取客户端标识符
        
        优先使用认证用户 ID，否则使用 IP 地址。
        
        Args:
            request: FastAPI 请求对象
            
        Returns:
            客户端唯一标识符
        """
        # 尝试从请求中获取用户 ID（假设通过认证中间件设置）
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        
        # 使用客户端 IP 地址
        # 优先从 X-Forwarded-For 头获取真实 IP（考虑代理/负载均衡）
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For 可能包含多个 IP，取第一个
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _should_skip_rate_limit(self, request: Request) -> bool:
        """
        判断是否跳过限流检查
        
        某些端点（如健康检查）可以跳过限流。
        
        Args:
            request: FastAPI 请求对象
            
        Returns:
            如果应该跳过限流返回 True
        """
        # 跳过健康检查端点
        skip_paths = ["/health", "/healthz", "/ready", "/metrics"]
        return request.url.path in skip_paths
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求并应用限流
        
        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器
            
        Returns:
            响应对象
            
        验证：需求 8.3
        """
        # 跳过不需要限流的端点
        if self._should_skip_rate_limit(request):
            return await call_next(request)
        
        # 获取客户端标识符
        client_id = self._get_client_identifier(request)
        
        try:
            # 尝试获取限流令牌
            allowed = await self.rate_limiter.acquire(
                key=client_id,
                max_requests=self.max_requests,
                window_seconds=self.window_seconds
            )
            
            if not allowed:
                # 超出限流，返回 429
                # 获取限流详细信息
                rate_info = await self.rate_limiter.get_rate_limit_info(
                    key=client_id,
                    max_requests=self.max_requests,
                    window_seconds=self.window_seconds
                )
                
                # 计算 retry-after（距离窗口重置的秒数）
                retry_after = rate_info.get("ttl_seconds", self.window_seconds)
                
                logger.warning(
                    f"限流拒绝请求: client={client_id}, "
                    f"path={request.url.path}, "
                    f"used={rate_info.get('used')}/{self.max_requests}"
                )
                
                # 返回 429 Too Many Requests
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"请求过于频繁，请在 {retry_after} 秒后重试",
                        "limit": self.max_requests,
                        "window_seconds": self.window_seconds,
                        "retry_after": retry_after
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": rate_info.get("reset_at", "")
                    }
                )
            
            # 获取剩余配额
            remaining = await self.rate_limiter.get_remaining(
                key=client_id,
                max_requests=self.max_requests,
                window_seconds=self.window_seconds
            )
            
            # 处理请求
            response = await call_next(request)
            
            # 添加限流信息到响应头
            response.headers["X-RateLimit-Limit"] = str(self.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = str(self.window_seconds)
            
            return response
            
        except HTTPException:
            # 重新抛出 HTTPException（包括 429）
            raise
            
        except Exception as e:
            # 限流器错误：记录日志，允许请求通过（fail-open）
            logger.error(
                f"限流中间件发生错误（允许请求）: {str(e)}, "
                f"client={client_id}, path={request.url.path}",
                exc_info=True
            )
            return await call_next(request)


def create_rate_limit_middleware(
    redis_client: redis.Redis,
    max_requests: int = 100,
    window_seconds: int = 60
) -> RateLimitMiddleware:
    """
    创建限流中间件实例的工厂函数
    
    Args:
        redis_client: Redis 异步客户端
        max_requests: 时间窗口内允许的最大请求数
        window_seconds: 时间窗口大小（秒）
        
    Returns:
        配置好的限流中间件实例
    """
    def middleware_factory(app):
        return RateLimitMiddleware(
            app=app,
            redis_client=redis_client,
            max_requests=max_requests,
            window_seconds=window_seconds
        )
    
    return middleware_factory
