"""FastAPI 应用主入口"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

# 加载环境变量（必须在其他导入之前）
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, WebSocket, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from src.api.routes import submissions, rubrics, reviews, batch
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.utils.database import init_db_pool, close_db_pool
from src.utils.pool_manager import UnifiedPoolManager, PoolConfig
from src.services.enhanced_api import EnhancedAPIService, QueryParams
from src.services.tracing import TracingService


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# 全局服务实例
redis_client: Optional[redis.Redis] = None
pool_manager: Optional[UnifiedPoolManager] = None
enhanced_api_service: Optional[EnhancedAPIService] = None
tracing_service: Optional[TracingService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global redis_client, pool_manager, enhanced_api_service, tracing_service
    
    # 启动时初始化
    logger.info("初始化应用...")
    
    # 初始化统一连接池
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        await pool_manager.initialize()
        logger.info("统一连接池已初始化")
        
        # 获取 Redis 客户端
        redis_client = pool_manager.get_redis_client()
        
        # 初始化全局数据库实例
        await init_db_pool(use_unified_pool=True)
        logger.info("全局数据库实例已初始化")
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        # 如果初始化失败，回退到离线模式
        logger.warning("回退到离线模式")
        redis_client = None
        pool_manager = None
    
    # 初始化追踪服务
    if pool_manager:
        tracing_service = TracingService(
            pool_manager=pool_manager,
            alert_threshold_ms=500
        )
        logger.info("追踪服务已初始化")
    
    # 初始化增强 API 服务
    if pool_manager:
        enhanced_api_service = EnhancedAPIService(
            pool_manager=pool_manager,
            tracing_service=tracing_service
        )
        await enhanced_api_service.start()
        logger.info("增强 API 服务已启动")
    
    yield
    
    # 关闭时清理
    logger.info("关闭应用...")
    
    # 停止增强 API 服务
    if enhanced_api_service:
        await enhanced_api_service.stop()
        logger.info("增强 API 服务已停止")
    
    # 关闭统一连接池
    if pool_manager:
        await pool_manager.shutdown()
        logger.info("统一连接池已关闭")
    else:
        # 传统方式关闭
        await close_db_pool()
        logger.info("数据库连接池已关闭")
        
        if redis_client:
            await redis_client.close()
            logger.info("Redis 连接已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="AI 批改系统 API",
    description="生产级纯视觉 AI 批改系统的 RESTful API",
    version="1.0.0",
    lifespan=lifespan
)


# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该配置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 添加限流中间件
@app.on_event("startup")
async def add_rate_limit_middleware():
    """在启动后添加限流中间件"""
    if redis_client:
        app.add_middleware(
            RateLimitMiddleware,
            redis_client=redis_client,
            max_requests=100,  # 每分钟 100 个请求
            window_seconds=60
        )
        logger.info("限流中间件已启用")


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(
        f"未处理的异常: {str(exc)}, "
        f"path={request.url.path}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "服务器内部错误，请稍后重试"
        }
    )


# 注册路由
app.include_router(submissions.router)
app.include_router(rubrics.router)
app.include_router(reviews.router)
app.include_router(batch.router)


# 健康检查端点
@app.get("/health", tags=["health"])
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "ai-grading-api",
        "version": "1.0.0"
    }


@app.get("/", tags=["root"])
async def root():
    """根路径"""
    return {
        "message": "AI 批改系统 API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# ==================== WebSocket 端点 ====================

@app.websocket("/ws/submissions/{submission_id}")
async def websocket_endpoint(websocket: WebSocket, submission_id: str):
    """
    WebSocket 实时推送端点
    
    订阅指定提交的状态变更，实时推送更新。
    
    验证：需求 7.1
    """
    if enhanced_api_service:
        await enhanced_api_service.handle_websocket(websocket, submission_id)
    else:
        await websocket.accept()
        await websocket.send_json({
            "error": "WebSocket 服务不可用"
        })
        await websocket.close()


# ==================== 增强查询端点 ====================

@app.get("/api/v1/submissions", tags=["submissions"])
async def list_submissions(
    page: int = 1,
    page_size: int = 20,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    status: Optional[str] = None,
    exam_id: Optional[str] = None,
    student_id: Optional[str] = None
):
    """
    分页查询提交列表
    
    支持分页、排序和过滤功能。
    
    验证：需求 7.2
    """
    if not enhanced_api_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="增强 API 服务不可用"
        )
    
    # 构建查询参数
    filters = {}
    if status:
        filters["status"] = status
    if exam_id:
        filters["exam_id"] = exam_id
    if student_id:
        filters["student_id"] = student_id
    
    params = QueryParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        filters=filters if filters else None
    )
    
    # 执行查询
    result = await enhanced_api_service.query_with_pagination(
        table="submissions",
        params=params
    )
    
    return result


@app.get("/api/v1/submissions/{submission_id}/fields", tags=["submissions"])
async def get_submission_fields(
    submission_id: str,
    fields: str
):
    """
    字段选择查询
    
    仅返回指定的字段，减少数据传输。
    
    Args:
        submission_id: 提交 ID
        fields: 逗号分隔的字段列表，例如 "submission_id,status,total_score"
    
    验证：需求 7.3
    """
    if not enhanced_api_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="增强 API 服务不可用"
        )
    
    # 解析字段列表
    field_set = set(f.strip() for f in fields.split(",") if f.strip())
    
    if not field_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定至少一个字段"
        )
    
    # 执行查询
    result = await enhanced_api_service.query_with_field_selection(
        table="submissions",
        record_id=submission_id,
        fields=field_set,
        id_field="submission_id"
    )
    
    return result


@app.get("/api/v1/admin/slow-queries", tags=["admin"])
async def get_slow_queries(
    limit: int = 100,
    min_duration_ms: Optional[int] = None
):
    """
    获取慢查询记录
    
    返回最近的慢查询记录，用于性能监控。
    
    验证：需求 7.4
    """
    if not enhanced_api_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="增强 API 服务不可用"
        )
    
    records = await enhanced_api_service.get_slow_queries(
        limit=limit,
        min_duration_ms=min_duration_ms
    )
    
    return {
        "slow_queries": records,
        "count": len(records)
    }


@app.get("/api/v1/admin/stats", tags=["admin"])
async def get_api_stats():
    """
    获取 API 统计信息
    
    返回 API 服务的统计信息，包括查询数、慢查询数、WebSocket 连接数等。
    """
    if not enhanced_api_service:
        return {
            "error": "增强 API 服务不可用"
        }
    
    stats = enhanced_api_service.stats
    stats["active_websocket_connections"] = enhanced_api_service.get_active_connections_count()
    stats["subscribed_submissions"] = enhanced_api_service.get_subscribed_submissions()
    
    return stats


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
