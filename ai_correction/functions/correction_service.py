"""
批改服务交互模块
处理与 AI 批改服务的交互逻辑，包括任务提交、状态轮询等
"""

import json
import time
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum
import requests


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class CorrectionPhase(Enum):
    """批改阶段枚举"""
    UPLOADING = "uploading"  # 上传中
    ANALYZING = "analyzing"  # 分析中
    CORRECTING = "correcting"  # 批改中
    GENERATING = "generating"  # 生成结果中
    COMPLETED = "completed"  # 已完成


class CorrectionTask:
    """批改任务类"""
    
    def __init__(self, task_id: str, files: List[str], mode: str = "auto", 
                 strictness: str = "中等", language: str = "zh"):
        self.task_id = task_id
        self.files = files
        self.mode = mode
        self.strictness = strictness
        self.language = language
        self.status = TaskStatus.PENDING
        self.phase = CorrectionPhase.UPLOADING
        self.progress = 0  # 0-100
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.phase_messages = []
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "files": self.files,
            "mode": self.mode,
            "strictness": self.strictness,
            "language": self.language,
            "status": self.status.value,
            "phase": self.phase.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "phase_messages": self.phase_messages
        }


class CorrectionService:
    """批改服务类"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000", use_simulator: bool = True):
        self.api_base_url = api_base_url
        self.use_simulator = use_simulator
        self.tasks: Dict[str, CorrectionTask] = {}
    
    def submit_task(self, task_id: str, files: List[str], mode: str = "auto",
                   strictness: str = "中等", language: str = "zh") -> CorrectionTask:
        """提交批改任务"""
        task = CorrectionTask(task_id, files, mode, strictness, language)
        self.tasks[task_id] = task
        
        if self.use_simulator:
            # 使用模拟器
            self._simulate_task_submission(task)
        else:
            # 调用真实 API
            self._call_api_submit(task)
        
        return task
    
    def get_task_status(self, task_id: str) -> Optional[CorrectionTask]:
        """获取任务状态"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        
        if self.use_simulator:
            self._simulate_task_progress(task)
        else:
            self._call_api_status(task)
        
        return task
    
    def _simulate_task_submission(self, task: CorrectionTask):
        """模拟任务提交"""
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now()
        task.phase_messages.append("✓ 任务已提交")
    
    def _simulate_task_progress(self, task: CorrectionTask):
        """模拟任务进度"""
        if task.status == TaskStatus.COMPLETED or task.status == TaskStatus.FAILED:
            return
        
        elapsed = (datetime.now() - task.started_at).total_seconds()
        
        # 模拟不同阶段的进度
        if elapsed < 2:
            task.phase = CorrectionPhase.UPLOADING
            task.progress = int(elapsed / 2 * 20)
            if "✓ 文件上传中" not in task.phase_messages:
                task.phase_messages.append("✓ 文件上传中")
        elif elapsed < 4:
            task.phase = CorrectionPhase.ANALYZING
            task.progress = 20 + int((elapsed - 2) / 2 * 20)
            if "✓ 分析题目中" not in task.phase_messages:
                task.phase_messages.append("✓ 分析题目中")
        elif elapsed < 6:
            task.phase = CorrectionPhase.CORRECTING
            task.progress = 40 + int((elapsed - 4) / 2 * 40)
            if "✓ 智能批改中" not in task.phase_messages:
                task.phase_messages.append("✓ 智能批改中")
        elif elapsed < 8:
            task.phase = CorrectionPhase.GENERATING
            task.progress = 80 + int((elapsed - 6) / 2 * 20)
            if "✓ 生成结果中" not in task.phase_messages:
                task.phase_messages.append("✓ 生成结果中")
        else:
            task.phase = CorrectionPhase.COMPLETED
            task.progress = 100
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = self._generate_mock_result(task)
            if "✓ 批改完成" not in task.phase_messages:
                task.phase_messages.append("✓ 批改完成")
    
    def _generate_mock_result(self, task: CorrectionTask) -> str:
        """生成模拟结果"""
        return f"""# 批改结果

## 基本信息
- 批改模式: {task.mode}
- 严格程度: {task.strictness}
- 文件数量: {len(task.files)}

## 批改结果
得分: 8/10
等级: B+

## 详细分析
### 优点
- 解题思路清晰
- 基础概念掌握扎实

### 问题
- 计算步骤有小错误
- 答案格式需要改进

### 建议
1. 仔细检查计算过程
2. 注意答案的规范性

---
批改时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    def _call_api_submit(self, task: CorrectionTask):
        """调用 API 提交任务"""
        try:
            response = requests.post(
                f"{self.api_base_url}/api/correction/submit",
                json=task.to_dict(),
                timeout=10
            )
            if response.status_code == 200:
                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now()
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
    
    def _call_api_status(self, task: CorrectionTask):
        """调用 API 获取状态"""
        try:
            response = requests.get(
                f"{self.api_base_url}/api/correction/status/{task.task_id}",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                task.status = TaskStatus(data.get("status"))
                task.phase = CorrectionPhase(data.get("phase"))
                task.progress = data.get("progress", 0)
                task.result = data.get("result")
        except Exception as e:
            task.error = str(e)


# 全局服务实例
_service_instance = None


def get_correction_service(use_simulator: bool = True) -> CorrectionService:
    """获取批改服务实例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = CorrectionService(use_simulator=use_simulator)
    return _service_instance

