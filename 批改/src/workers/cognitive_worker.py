"""认知 Worker - 注册所有 Activities 并连接到 vision-compute-queue

此 Worker 负责运行认知计算任务（Activities），包括文档分割、题目批改、
通知发送和结果持久化。配置了并发限制以控制资源使用。

验证：需求 4.1
"""

import asyncio
import logging
import os
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from src.activities.segment import segment_document_activity
from src.activities.grade import grade_question_activity
from src.activities.notify import notify_teacher_activity
from src.activities.persist import persist_results_activity
from src.services.layout_analysis import LayoutAnalysisService
from src.services.cache import CacheService
from src.agents.grading_agent import GradingAgent
from src.repositories.grading_result import GradingResultRepository
from src.repositories.submission import SubmissionRepository
from src.utils.database import get_db_pool


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_cognitive_worker(
    temporal_host: Optional[str] = None,
    temporal_namespace: Optional[str] = None,
    task_queue: str = "vision-compute-queue",
    max_concurrent_activities: int = 10
) -> Worker:
    """
    创建认知 Worker
    
    Args:
        temporal_host: Temporal 服务器地址（默认从环境变量读取）
        temporal_namespace: Temporal 命名空间（默认从环境变量读取）
        task_queue: 任务队列名称
        max_concurrent_activities: 最大并发 Activity 数量
        
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
    
    logger.info(
        f"创建认知 Worker: task_queue={task_queue}, "
        f"max_concurrent_activities={max_concurrent_activities}"
    )
    
    # 初始化服务依赖
    # 注意：在实际应用中，这些服务应该从依赖注入容器获取
    logger.info("初始化服务依赖...")
    
    # 数据库连接池
    db_pool = await get_db_pool()
    
    # 服务实例
    layout_service = LayoutAnalysisService()
    cache_service = CacheService()
    grading_agent = GradingAgent()
    
    # 仓储实例
    grading_result_repo = GradingResultRepository(db_pool)
    submission_repo = SubmissionRepository(db_pool)
    
    logger.info("服务依赖初始化完成")
    
    # 创建 Activity 包装器，注入依赖
    async def segment_document_wrapper(
        submission_id: str,
        image_data: bytes,
        page_index: int = 0
    ):
        """文档分割 Activity 包装器"""
        return await segment_document_activity(
            submission_id=submission_id,
            image_data=image_data,
            page_index=page_index,
            layout_service=layout_service
        )
    
    async def grade_question_wrapper(
        submission_id: str,
        question_id: str,
        image_b64: str,
        rubric: str,
        max_score: float,
        standard_answer: Optional[str] = None
    ):
        """批改题目 Activity 包装器"""
        return await grade_question_activity(
            submission_id=submission_id,
            question_id=question_id,
            image_b64=image_b64,
            rubric=rubric,
            max_score=max_score,
            standard_answer=standard_answer,
            cache_service=cache_service,
            grading_agent=grading_agent
        )
    
    async def persist_results_wrapper(
        submission_id: str,
        grading_results: list
    ):
        """持久化结果 Activity 包装器"""
        return await persist_results_activity(
            submission_id=submission_id,
            grading_results=grading_results,
            grading_result_repo=grading_result_repo,
            submission_repo=submission_repo
        )
    
    # 创建 Worker，注册所有 Activities
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[],  # 认知 Worker 不运行工作流
        activities=[
            segment_document_wrapper,
            grade_question_wrapper,
            notify_teacher_activity,
            persist_results_wrapper
        ],
        max_concurrent_workflow_tasks=0,  # 不运行工作流
        max_concurrent_activities=max_concurrent_activities,  # 配置并发限制
        max_concurrent_activity_task_polls=5  # Activity 任务轮询器数量
    )
    
    logger.info(
        f"认知 Worker 已创建: "
        f"activities=[segment_document, grade_question, notify_teacher, persist_results], "
        f"task_queue={task_queue}, "
        f"max_concurrent_activities={max_concurrent_activities}"
    )
    
    return worker


async def run_cognitive_worker():
    """
    运行认知 Worker
    
    这是主入口函数，创建并启动 Worker。
    """
    logger.info("启动认知 Worker...")
    
    try:
        # 从环境变量读取并发限制配置
        max_concurrent = int(os.getenv("MAX_CONCURRENT_ACTIVITIES", "10"))
        
        # 创建 Worker
        worker = await create_cognitive_worker(
            max_concurrent_activities=max_concurrent
        )
        
        # 运行 Worker（阻塞直到收到停止信号）
        logger.info(
            f"认知 Worker 正在运行，等待 Activity 任务... "
            f"(max_concurrent={max_concurrent})"
        )
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭认知 Worker...")
    except Exception as e:
        logger.error(f"认知 Worker 运行失败: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("认知 Worker 已停止")


def main():
    """
    主函数入口
    
    使用方式：
        python -m src.workers.cognitive_worker
        
    环境变量：
        TEMPORAL_HOST: Temporal 服务器地址（默认: localhost:7233）
        TEMPORAL_NAMESPACE: Temporal 命名空间（默认: default）
        MAX_CONCURRENT_ACTIVITIES: 最大并发 Activity 数量（默认: 10）
    """
    asyncio.run(run_cognitive_worker())


if __name__ == "__main__":
    main()
