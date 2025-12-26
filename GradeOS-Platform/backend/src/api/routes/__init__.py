# API Routes Package
# 统一的 API 路由入口

from fastapi import APIRouter

# 创建主路由
api_router = APIRouter()

# 导入各模块路由
# from .auth import router as auth_router
# from .classes import router as classes_router
# from .homework import router as homework_router
# from .grading import router as grading_router
# from .analysis import router as analysis_router
# from .scan import router as scan_router

# 注册路由
# api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
# api_router.include_router(classes_router, prefix="/class", tags=["班级管理"])
# api_router.include_router(homework_router, prefix="/homework", tags=["作业管理"])
# api_router.include_router(grading_router, prefix="/grading", tags=["AI批改"])
# api_router.include_router(analysis_router, prefix="/analysis", tags=["错题分析"])
# api_router.include_router(scan_router, prefix="/scan", tags=["移动扫描"])
