"""智能体池管理

管理批改智能体的注册、查询和选择
"""

import logging
from typing import Dict, List, Optional

from src.models.enums import QuestionType
from src.agents.base import BaseGradingAgent


logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """找不到合适的智能体"""
    pass


class AgentPool:
    """智能体池管理器
    
    管理所有已注册的批改智能体，支持按题型查询和动态注册。
    采用单例模式确保全局唯一的智能体池。
    
    Example:
        >>> pool = AgentPool()
        >>> pool.register_agent(ObjectiveAgent())
        >>> agent = pool.get_agent(QuestionType.OBJECTIVE)
    """
    
    _instance: Optional["AgentPool"] = None
    
    def __new__(cls) -> "AgentPool":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, BaseGradingAgent] = {}
            cls._instance._type_mapping: Dict[QuestionType, str] = {}
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None
    
    def register_agent(self, agent: BaseGradingAgent) -> None:
        """注册批改智能体
        
        将智能体添加到池中，并建立题型到智能体的映射。
        如果已存在相同类型的智能体，将被覆盖。
        
        Args:
            agent: 要注册的批改智能体实例
            
        Raises:
            TypeError: 如果 agent 不是 BaseGradingAgent 的子类实例
        """
        if not isinstance(agent, BaseGradingAgent):
            raise TypeError(
                f"agent 必须是 BaseGradingAgent 的子类实例，"
                f"实际类型: {type(agent).__name__}"
            )
        
        agent_type = agent.agent_type
        self._agents[agent_type] = agent
        
        # 建立题型到智能体的映射
        for question_type in agent.supported_question_types:
            self._type_mapping[question_type] = agent_type
            logger.info(
                f"注册智能体映射: {question_type.value} -> {agent_type}"
            )
        
        logger.info(f"注册智能体: {agent}")
    
    def get_agent(self, question_type: QuestionType) -> BaseGradingAgent:
        """获取指定题型的智能体
        
        Args:
            question_type: 题目类型
            
        Returns:
            能够处理该题型的批改智能体
            
        Raises:
            AgentNotFoundError: 如果没有找到能处理该题型的智能体
        """
        agent_type = self._type_mapping.get(question_type)
        
        if agent_type is None:
            raise AgentNotFoundError(
                f"没有找到能处理题型 '{question_type.value}' 的智能体。"
                f"已注册的智能体: {self.list_agents()}"
            )
        
        agent = self._agents.get(agent_type)
        if agent is None:
            raise AgentNotFoundError(
                f"智能体 '{agent_type}' 已注册但实例不存在"
            )
        
        return agent
    
    def get_agent_by_type(self, agent_type: str) -> Optional[BaseGradingAgent]:
        """按智能体类型获取智能体
        
        Args:
            agent_type: 智能体类型标识
            
        Returns:
            对应的智能体实例，如果不存在则返回 None
        """
        return self._agents.get(agent_type)
    
    def list_agents(self) -> List[str]:
        """列出所有已注册的智能体类型
        
        Returns:
            智能体类型标识列表
        """
        return list(self._agents.keys())
    
    def list_supported_types(self) -> List[QuestionType]:
        """列出所有支持的题型
        
        Returns:
            支持的 QuestionType 列表
        """
        return list(self._type_mapping.keys())
    
    def has_agent_for(self, question_type: QuestionType) -> bool:
        """检查是否有智能体能处理指定题型
        
        Args:
            question_type: 题目类型
            
        Returns:
            如果有智能体能处理该题型则返回 True
        """
        return question_type in self._type_mapping
    
    def clear(self) -> None:
        """清空所有注册的智能体（仅用于测试）"""
        self._agents.clear()
        self._type_mapping.clear()
        logger.info("已清空智能体池")
    
    def __len__(self) -> int:
        """返回已注册的智能体数量"""
        return len(self._agents)
    
    def __repr__(self) -> str:
        return f"<AgentPool agents={self.list_agents()}>"
