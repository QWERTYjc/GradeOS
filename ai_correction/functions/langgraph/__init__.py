# LangGraph AI 批改系统
# 正确集成到 ai_correction 中

# 延迟导入，避免在没有 langgraph 时报错
try:
    from .workflow import create_grading_workflow
    from .state import GradingState
    __all__ = [
        'create_grading_workflow',
        'GradingState',
    ]
except ImportError:
    # 如果 langgraph 未安装，只导出 agents
    __all__ = []
