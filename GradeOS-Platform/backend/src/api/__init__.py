"""API 模块"""


# 延迟导入，避免循环依赖
def get_app():
    from .main import app

    return app


__all__ = ["get_app"]
