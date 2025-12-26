"""Orchestrator 抽象接口

定义编排器的统一接口，隔离业务层对具体编排引擎（Temporal/LangGraph）的依赖。

验证：需求 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class RunStatus(str, Enum):
    """工作流执行状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 正在执行
    PAUSED = "paused"        # 暂停（等待人工介入）
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class RunInfo:
    """工作流执行信息
    
    Attributes:
        run_id: 执行 ID（唯一标识符）
        graph_name: Graph/Workflow 名称
        status: 当前执行状态
        progress: 进度信息（包含 stage、percentage、details 等）
        created_at: 创建时间
        updated_at: 更新时间
        error: 错误信息（如果失败）
        state: 完整状态数据（用于获取批改结果等）
    """
    run_id: str
    graph_name: str
    status: RunStatus
    progress: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None
    state: Optional[Dict[str, Any]] = None  # 新增：完整状态数据


class Orchestrator(ABC):
    """编排器抽象接口
    
    提供统一的工作流编排能力，支持启动、查询、取消、重试等操作。
    业务层通过此接口调用编排能力，无需关心底层是 Temporal 还是 LangGraph。
    
    验证：需求 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
    """
    
    @abstractmethod
    async def start_run(
        self,
        graph_name: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> str:
        """启动工作流执行
        
        Args:
            graph_name: Graph/Workflow 名称（如 "exam_paper", "batch_grading"）
            payload: 工作流输入数据
            idempotency_key: 幂等键（可选），用于防止重复执行
            
        Returns:
            run_id: 执行 ID，用于后续查询和操作
            
        Raises:
            Exception: 启动失败时抛出
            
        验证：需求 1.1
        """
        pass
    
    @abstractmethod
    async def get_status(self, run_id: str) -> RunInfo:
        """查询工作流执行状态
        
        Args:
            run_id: 执行 ID
            
        Returns:
            RunInfo: 执行信息，包含状态、进度等
            
        Raises:
            Exception: 查询失败或 run_id 不存在时抛出
            
        验证：需求 1.2
        """
        pass
    
    @abstractmethod
    async def cancel(self, run_id: str) -> bool:
        """取消工作流执行
        
        Args:
            run_id: 执行 ID
            
        Returns:
            bool: 是否成功取消
            
        Raises:
            Exception: 取消失败时抛出
            
        验证：需求 1.3
        """
        pass
    
    @abstractmethod
    async def retry(self, run_id: str) -> str:
        """重试失败的工作流
        
        Args:
            run_id: 原执行 ID
            
        Returns:
            str: 新的执行 ID
            
        Raises:
            Exception: 重试失败时抛出
            
        验证：需求 1.4
        """
        pass
    
    @abstractmethod
    async def list_runs(
        self,
        graph_name: Optional[str] = None,
        status: Optional[RunStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RunInfo]:
        """列出工作流执行
        
        Args:
            graph_name: 按 Graph 名称筛选（可选）
            status: 按状态筛选（可选）
            limit: 返回数量限制
            offset: 偏移量（用于分页）
            
        Returns:
            List[RunInfo]: 执行信息列表
            
        Raises:
            Exception: 查询失败时抛出
            
        验证：需求 1.5
        """
        pass
    
    @abstractmethod
    async def send_event(
        self,
        run_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> bool:
        """发送外部事件到工作流
        
        用于人工介入、外部回调等场景。
        
        Args:
            run_id: 执行 ID
            event_type: 事件类型（如 "review_signal", "external_callback"）
            event_data: 事件数据
            
        Returns:
            bool: 是否成功发送
            
        Raises:
            Exception: 发送失败时抛出
            
        验证：需求 1.6
        """
        pass
