"""批改智能体基类定义

提供批改智能体的抽象接口，支持插件化扩展
"""

from abc import ABC, abstractmethod
from typing import List

from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState


class BaseGradingAgent(ABC):
    """批改智能体抽象基类
    
    所有专业批改智能体（ObjectiveAgent、StepwiseAgent 等）都必须继承此基类。
    通过标准接口注册到 AgentPool，支持热插拔和动态派生。
    
    Attributes:
        agent_type: 智能体类型标识（如 "objective", "stepwise"）
        supported_question_types: 该智能体支持的题型列表
    """
    
    @property
    @abstractmethod
    def agent_type(self) -> str:
        """智能体类型标识
        
        Returns:
            智能体类型字符串，如 "objective", "stepwise", "essay", "lab_design"
        """
        pass
    
    @property
    @abstractmethod
    def supported_question_types(self) -> List[QuestionType]:
        """支持的题型列表
        
        Returns:
            该智能体能够处理的 QuestionType 枚举值列表
        """
        pass
    
    @abstractmethod
    async def grade(self, context_pack: ContextPack) -> GradingState:
        """执行批改
        
        Args:
            context_pack: 包含题目图像、评分细则、术语等的上下文包
            
        Returns:
            GradingState: 包含分数、置信度、证据链等的批改结果
            
        Raises:
            GradingError: 批改过程中发生错误
        """
        pass
    
    def can_handle(self, question_type: QuestionType) -> bool:
        """检查是否能处理指定题型
        
        Args:
            question_type: 要检查的题型
            
        Returns:
            如果该智能体支持此题型则返回 True
        """
        return question_type in self.supported_question_types
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} agent_type={self.agent_type}>"
