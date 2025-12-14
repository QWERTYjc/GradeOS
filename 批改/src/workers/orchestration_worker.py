"""编排 Worker - 注册工作流并连接到 default-queue

此 Worker 负责运行编排工作流（ExamPaperWorkflow 和 QuestionGradingChildWorkflow），
处理试卷批改的整体流程编排。

验证：需求 4.1
"""

import asyncio
import logging
import os
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from src.workflows.exam_paper import ExamPaperWorkflow
from src.workflows.question_grading import QuestionGradingChildWorkflow


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_orchestration_worker(
    temporal_host: Optional[str] = None,
    temporal_namespace: Optional[str] = None,
    task_queue: str = "default-queue"
) -> Worker:
    """
    创建编排 Worker
    
    Args:
        temporal_host: Temporal 服务器地址（默认从环境变量读取）
        temporal_namespace: Temporal 命名空间（默认从环境变量读取）
        task_queue: 任务队列名称
        
    Returns:
        Worker: 配置好的 Temporal Worker 实例
    """
    # 从环境变量读取配置
    if temporal_host is None:
        temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    
    if temporal_namespace is None:
        temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    
    logger.info(
        f"连接到 Temporal 服务器: host={temporal_host}, "
        f"namespace={temporal_namespace}"
    )
    
    # 创建 Temporal 客户端
    client = await Client.connect(
        temporal_host,
        namespace=temporal_namespace
    )
    
    logger.info(f"创建编排 Worker: task_queue={task_queue}")
    
    # 创建 Worker，注册工作流
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[
            ExamPaperWorkflow,
            QuestionGradingChildWorkflow
        ],
        activities=[],  # 编排 Worker 不运行 Activities
        max_concurrent_workflow_tasks=100,  # 最大并发工作流任务数
        max_concurrent_activities=0  # 不运行 Activities
    )
    
    logger.info(
        f"编排 Worker 已创建: "
        f"workflows=[ExamPaperWorkflow, QuestionGradingChildWorkflow], "
        f"task_queue={task_queue}"
    )
    
    return worker


async def run_orchestration_worker():
    """
    运行编排 Worker
    
    这是主入口函数，创建并启动 Worker。
    """
    logger.info("启动编排 Worker...")
    
    try:
        # 创建 Worker
        worker = await create_orchestration_worker()
        
        # 运行 Worker（阻塞直到收到停止信号）
        logger.info("编排 Worker 正在运行，等待工作流任务...")
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭编排 Worker...")
    except Exception as e:
        logger.error(f"编排 Worker 运行失败: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("编排 Worker 已停止")


def main():
    """
    主函数入口
    
    使用方式：
        python -m src.workers.orchestration_worker
    """
    asyncio.run(run_orchestration_worker())


if __name__ == "__main__":
    main()
