"""FastAPI 应用主入口"""

import os
import sys
import asyncio
from datetime import datetime, timezone

# Windows 事件循环修复 - 必须在所有其他导入之前
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
from contextlib import asynccontextmanager
from typing import Optional

# 加载环境变量（必须在其他导入之前）
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

# NOTE: Avoid importing heavy route modules at import time. Uvicorn must be able
# to bind quickly for Railway healthchecks. Routes are registered lazily during
# background bootstrap (see _register_api_routes).

from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.dependencies import init_orchestrator, close_orchestrator, get_orchestrator
from src.utils.database import init_db_pool, close_db_pool, db
from src.utils.pool_manager import UnifiedPoolManager, PoolConfig
from src.services.enhanced_api import EnhancedAPIService
from src.services.tracing import TracingService
from src.config.deployment_mode import get_deployment_mode, DeploymentMode


# 配置日志
# ????
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL_VALUE = getattr(logging, LOG_LEVEL, logging.INFO)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logging.basicConfig(
    level=LOG_LEVEL_VALUE,
    format=LOG_FORMAT,
    stream=sys.stdout,
    force=True,
)

# 禁用噪音日志
logging.getLogger("src.utils.redis_logger").setLevel(logging.WARNING)
logging.getLogger("src.utils.sql_logger").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def _configure_stdout_loggers() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "alembic",
        "alembic.runtime.migration",
    ):
        target = logging.getLogger(name)
        target.setLevel(LOG_LEVEL_VALUE)
        target.handlers = [handler]
        target.propagate = False


_configure_stdout_loggers()


def _configure_grading_loggers() -> None:
    log_path = os.getenv("GRADEOS_GRADING_LOG_PATH", "batch_grading.log")
    handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    for name in (
        "src.graphs.batch_grading",
        "src.api.routes.batch_langgraph",
        "src.services.enhanced_api",
        "src.orchestration.langgraph_orchestrator",
    ):
        target = logging.getLogger(name)
        target.setLevel(LOG_LEVEL_VALUE)
        target.handlers = [handler]
        target.propagate = False


_configure_grading_loggers()

logger = logging.getLogger(__name__)


# 全局服务实例
redis_client: Optional[redis.Redis] = None
pool_manager: Optional[UnifiedPoolManager] = None
enhanced_api_service: Optional[EnhancedAPIService] = None
tracing_service: Optional[TracingService] = None


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "y", "on")


def _is_grading_memory_enabled() -> bool:
    """默认关闭；通过环境变量显式开启。"""
    if _env_truthy("DISABLE_GRADING_MEMORY"):
        return False
    if os.getenv("ENABLE_GRADING_MEMORY") is not None:
        return _env_truthy("ENABLE_GRADING_MEMORY")
    if os.getenv("GRADING_MEMORY_ENABLED") is not None:
        return _env_truthy("GRADING_MEMORY_ENABLED")
    return False


def _is_redis_task_queue_enabled() -> bool:
    """默认关闭；通过环境变量显式开启。"""
    if _env_truthy("DISABLE_REDIS_TASK_QUEUE"):
        return False
    if os.getenv("ENABLE_REDIS_TASK_QUEUE") is not None:
        return _env_truthy("ENABLE_REDIS_TASK_QUEUE")
    if os.getenv("REDIS_TASK_QUEUE_ENABLED") is not None:
        return _env_truthy("REDIS_TASK_QUEUE_ENABLED")
    return False


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _bootstrap_init(app: FastAPI) -> None:
    """Initialize expensive dependencies in the background.

    This keeps startup fast so Railway healthchecks can pass, while still
    bringing the DB/Redis/LangGraph stack online for real traffic.
    """

    global redis_client, pool_manager, enhanced_api_service, tracing_service

    st = getattr(app.state, "bootstrap", None)
    if st is None:
        st = {}
        app.state.bootstrap = st

    st.update(
        {
            "status": "starting",
            "started_at": st.get("started_at") or _now_iso_utc(),
            "finished_at": None,
            "errors": [],
            "components": {},
        }
    )

    def _set_component(name: str, status: str, detail: Optional[str] = None) -> None:
        comp = st.setdefault("components", {})
        comp[name] = {"status": status, "detail": detail, "at": _now_iso_utc()}

    async def _step(name: str, coro, timeout_s: float) -> bool:
        _set_component(name, "starting")
        try:
            await asyncio.wait_for(coro, timeout=timeout_s)
            _set_component(name, "ok")
            return True
        except Exception as exc:
            msg = f"{name} failed: {exc}"
            st.setdefault("errors", []).append(msg)
            _set_component(name, "error", str(exc))
            logger.warning(msg)
            return False

    try:
        logger.info("Bootstrap: initializing dependencies in background...")

        deployment_config = get_deployment_mode()
        st["deployment_mode"] = deployment_config.mode.value
        st["features"] = deployment_config.get_feature_availability()

        if deployment_config.is_database_mode:
            try:
                _set_component("pool_manager", "starting")
                pool_manager = await UnifiedPoolManager.get_instance()
                await asyncio.wait_for(pool_manager.initialize(), timeout=25)
                _set_component("pool_manager", "ok")

                try:
                    redis_client = pool_manager.get_redis_client()
                    _set_component("redis_client", "ok")
                except Exception as exc:
                    redis_client = None
                    _set_component("redis_client", "error", str(exc))
            except Exception as exc:
                pool_manager = None
                redis_client = None
                _set_component("pool_manager", "error", str(exc))
                st.setdefault("errors", []).append(f"pool_manager failed: {exc}")

            await _step("db_pool", init_db_pool(use_unified_pool=True), timeout_s=25)
        else:
            logger.info("Bootstrap: OFFLINE/NO-DB mode detected.")
            redis_client = None
            pool_manager = None
            os.environ["OFFLINE_MODE"] = "true"
            _set_component("offline_mode", "ok")

        if pool_manager and not db.is_degraded:
            try:
                tracing_service = TracingService(pool_manager=pool_manager)
                _set_component("tracing_service", "ok")
            except Exception as exc:
                tracing_service = None
                _set_component("tracing_service", "error", str(exc))

            try:
                enhanced_api_service = EnhancedAPIService(
                    pool_manager=pool_manager, tracing_service=tracing_service
                )
                await asyncio.wait_for(enhanced_api_service.start(), timeout=25)
                _set_component("enhanced_api_service", "ok")
            except Exception as exc:
                enhanced_api_service = None
                _set_component("enhanced_api_service", "error", str(exc))
                st.setdefault("errors", []).append(f"enhanced_api_service failed: {exc}")

        if _is_grading_memory_enabled():
            try:
                from src.services.grading_memory import init_memory_service_with_db

                await asyncio.wait_for(
                    init_memory_service_with_db(
                        pool_manager=pool_manager, redis_client=redis_client
                    ),
                    timeout=25,
                )
                _set_component("grading_memory", "ok")
            except Exception as exc:
                _set_component("grading_memory", "error", str(exc))
                logger.warning("grading_memory init failed (will fall back): %s", exc)
        else:
            _set_component("grading_memory", "disabled", "ENABLE_GRADING_MEMORY=false")
            logger.info("grading_memory disabled by configuration.")

        await _step("orchestrator", init_orchestrator(), timeout_s=40)

        try:
            _register_api_routes(app)
            _set_component("routes", "ok")
        except Exception as exc:
            _set_component("routes", "error", str(exc))

        try:
            orch = await get_orchestrator()
            if orch is not None:
                try:
                    from src.api.routes import batch_langgraph

                    await batch_langgraph.resume_orphaned_streams(orch)
                    _set_component("orchestrator_resume", "ok")
                except Exception as exc:
                    _set_component("orchestrator_resume", "error", str(exc))
        except Exception as exc:
            _set_component("orchestrator_resume", "error", str(exc))

        if _is_redis_task_queue_enabled():
            try:
                from src.services.redis_task_queue import init_task_queue

                await asyncio.wait_for(init_task_queue(), timeout=20)
                _set_component("task_queue", "ok")
            except Exception as exc:
                _set_component("task_queue", "error", str(exc))
                logger.warning("task_queue init failed (will fall back): %s", exc)
        else:
            _set_component("task_queue", "disabled", "ENABLE_REDIS_TASK_QUEUE=false")
            logger.info("redis_task_queue disabled by configuration.")

        st["status"] = "ready" if not st.get("errors") else "degraded"
        logger.info("Bootstrap: %s", st["status"])

    except asyncio.CancelledError:
        st["status"] = "cancelled"
        raise
    except Exception as exc:
        st["status"] = "degraded"
        st.setdefault("errors", []).append(f"bootstrap crashed: {exc}")
        logger.error("Bootstrap crashed: %s", exc, exc_info=True)
    finally:
        st["finished_at"] = _now_iso_utc()


def _register_api_routes(app: FastAPI) -> None:
    """Register non-health routes lazily.

    Some route modules are large / import heavy deps. Importing them during
    module import can delay Uvicorn bind and fail Railway healthchecks.
    """

    if getattr(app.state, "routes_registered", False):
        return

    errors: list[str] = []

    def _warn(msg: str, exc: Exception) -> None:
        errors.append(f"{msg}: {exc}")
        logger.warning("%s: %s", msg, exc)

    try:
        from src.api.routes import unified_api

        app.include_router(unified_api.router, prefix="/api", tags=["GradeOS unified API"])
    except Exception as exc:  # pragma: no cover
        _warn("unified_api include failed", exc)

    try:
        from src.api.routes import batch_langgraph

        app.include_router(batch_langgraph.router, prefix="/api", tags=["batch grading"])
    except Exception as exc:  # pragma: no cover
        _warn("batch_langgraph include failed", exc)

    try:
        from src.api.routes import runs

        app.include_router(runs.router, prefix="/api", tags=["run observability"])
    except Exception as exc:  # pragma: no cover
        _warn("runs include failed", exc)

    # Optional modules.
    try:
        from src.api.routes import annotation_grading

        app.include_router(annotation_grading.router, prefix="/api", tags=["annotation grading"])
    except Exception as exc:  # pragma: no cover
        _warn("annotation_grading include failed", exc)

    try:
        from src.api.routes import assistant_grading

        app.include_router(assistant_grading.router, prefix="/api", tags=["assistant grading"])
    except Exception as exc:  # pragma: no cover
        _warn("assistant_grading include failed", exc)

    if _is_grading_memory_enabled():
        try:
            from src.api.routes import memory_api

            app.include_router(memory_api.router, prefix="/api", tags=["memory"])
        except Exception as exc:  # pragma: no cover
            _warn("memory_api include failed", exc)
    else:
        logger.info("memory_api disabled by configuration.")

    try:
        from src.api.routes import class_integration

        app.include_router(class_integration.router, tags=["class integration"])
    except Exception as exc:  # pragma: no cover
        _warn("class_integration include failed", exc)

    try:
        from src.api.routes import openboard

        app.include_router(openboard.router, prefix="/api", tags=["openboard"])
    except Exception as exc:  # pragma: no cover
        _warn("openboard include failed", exc)

    app.state.routes_registered = True
    app.state.routes_register_errors = errors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager. Non-blocking startup for Railway healthchecks."""
    global redis_client, pool_manager, enhanced_api_service, tracing_service

    app.state.bootstrap = {
        "status": "starting",
        "started_at": _now_iso_utc(),
        "finished_at": None,
        "errors": [],
        "components": {},
    }
    app.state.bootstrap_task = asyncio.create_task(_bootstrap_init(app))
    logger.info("Startup: bootstrap task scheduled (non-blocking).")

    try:
        yield
    finally:
        logger.info("Shutting down app...")

        # Stop bootstrap first to avoid racing initializers during shutdown.
        bootstrap_task = getattr(app.state, "bootstrap_task", None)
        if bootstrap_task is not None:
            bootstrap_task.cancel()
            try:
                await bootstrap_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning("Bootstrap task did not shut down cleanly.", exc_info=True)

        # Shutdown Redis task queue.
        try:
            from src.services.redis_task_queue import shutdown_task_queue

            await shutdown_task_queue()
            logger.info("Redis task queue shut down.")
        except Exception as e:
            logger.warning(f"Redis task queue shutdown failed: {e}")

        # Close orchestrator.
        try:
            await close_orchestrator()
            logger.info("Orchestrator closed.")
        except Exception as e:
            logger.warning(f"Orchestrator close failed: {e}")

        # Stop enhanced API service.
        try:
            if enhanced_api_service:
                await enhanced_api_service.stop()
                logger.info("Enhanced API service stopped.")
        except Exception as e:
            logger.warning(f"Enhanced API service stop failed: {e}")

        # Close pools.
        try:
            if pool_manager:
                await pool_manager.shutdown()
                logger.info("Unified pool manager shut down.")
            else:
                await close_db_pool()
                logger.info("DB pool closed.")

                if redis_client:
                    await redis_client.close()
                    logger.info("Redis client closed.")
        except Exception as e:
            logger.warning(f"Pool shutdown failed: {e}")
# 创建 FastAPI 应用
app = FastAPI(
    title="AI 批改系统 API",
    description="生产级纯视觉 AI 批改系统的 RESTful API",
    version="1.0.0",
    lifespan=lifespan,
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
            window_seconds=60,
        )
        logger.info("限流中间件已启用")


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"未处理的异常: {str(exc)}, " f"path={request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "服务器内部错误，请稍后重试"},
    )


# 注册路由
# Routes are registered lazily in background bootstrap: see _register_api_routes().

@app.get("/health", tags=["health"])
@app.get("/api/health", tags=["health"])
async def health_check():
    """
    健康检查

    返回系统状态和部署模式信息
    支持 /health 和 /api/health 两个路径
    """
    deployment_config = get_deployment_mode()
    features = deployment_config.get_feature_availability()

    return {
        "status": "healthy",
        "service": "ai-grading-api",
        "version": "1.0.0",
        "deployment_mode": deployment_config.mode.value,
        "database_available": db.is_available if hasattr(db, "is_available") else False,
        "degraded_mode": db.is_degraded if hasattr(db, "is_degraded") else False,
        "features": features,
        # Liveness endpoint: always 200. Readiness is exposed via /ready.
        "bootstrap": getattr(app.state, "bootstrap", {"status": "unknown"}),
    }


@app.get("/ready", tags=["health"])
@app.get("/api/ready", tags=["health"])
async def readiness_check():
    """Readiness endpoint: returns 200 only after background bootstrap finishes."""
    st = getattr(app.state, "bootstrap", None)
    if not st:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "starting"}
        )

    if st.get("status") in ("ready", "degraded"):
        return {"status": "ready", "bootstrap": st}

    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=st)



@app.get("/", tags=["root"])
async def root():
    """根路径"""
    return {"message": "AI 批改系统 API", "version": "1.0.0", "docs": "/docs", "redoc": "/redoc"}


@app.get("/api/v1/admin/slow-queries", tags=["admin"])
async def get_slow_queries(limit: int = 100, min_duration_ms: Optional[int] = None):
    """
    获取慢查询记录

    返回最近的慢查询记录，用于性能监控。

    验证：需求 7.4
    """
    if not enhanced_api_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="增强 API 服务不可用"
        )

    records = await enhanced_api_service.get_slow_queries(
        limit=limit, min_duration_ms=min_duration_ms
    )

    return {"slow_queries": records, "count": len(records)}


@app.get("/api/v1/admin/stats", tags=["admin"])
async def get_api_stats():
    """
    获取 API 统计信息

    返回 API 服务统计信息（例如查询数量和慢查询记录）。
    """
    if not enhanced_api_service:
        return {"error": "增强 API 服务不可用"}

    return enhanced_api_service.stats


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
