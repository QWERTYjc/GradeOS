"""调试 LangGraph 执行"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def test_langgraph_execution():
    """测试 LangGraph 执行"""
    from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator
    from src.graphs.batch_grading import create_batch_grading_graph
    
    # 创建编排器（离线模式）
    orchestrator = LangGraphOrchestrator(offline_mode=True)
    
    # 创建并注册 Graph
    batch_graph = create_batch_grading_graph(checkpointer=None)
    orchestrator.register_graph("batch_grading", batch_graph)
    
    logger.info("Graph 已注册")
    
    # 准备测试数据
    payload = {
        "batch_id": "test-batch-001",
        "exam_id": "test-exam-001",
        "pdf_path": "学生作答.pdf",
        "rubric_images": [],  # 空列表用于测试
        "answer_images": [b"fake_image_1", b"fake_image_2"],  # 假图像数据
        "api_key": os.getenv("GEMINI_API_KEY"),
        "inputs": {
            "pdf_path": "学生作答.pdf",
            "rubric": "",
            "auto_identify": True
        }
    }
    
    logger.info("准备启动 Graph...")
    
    # 启动执行
    run_id = await orchestrator.start_run(
        graph_name="batch_grading",
        payload=payload,
        idempotency_key="test-001"
    )
    
    logger.info(f"Graph 已启动: run_id={run_id}")
    
    # 监听事件流
    event_count = 0
    async for event in orchestrator.stream_run(run_id):
        event_count += 1
        event_type = event.get("type")
        node_name = event.get("node")
        
        logger.info(f"事件 #{event_count}: type={event_type}, node={node_name}")
        
        if event_type == "node_start":
            logger.info(f"  → 节点开始: {node_name}")
        elif event_type == "node_end":
            logger.info(f"  → 节点结束: {node_name}")
            output = event.get("data", {}).get("output", {})
            if isinstance(output, dict):
                logger.info(f"  → 输出: {list(output.keys())}")
            else:
                logger.info(f"  → 输出类型: {type(output)}")
        elif event_type == "state_update":
            state = event.get("data", {}).get("state", {})
            logger.info(f"  → 状态更新: {list(state.keys())}")
        elif event_type == "error":
            error = event.get("data", {}).get("error")
            logger.error(f"  → 错误: {error}")
        elif event_type == "completed":
            logger.info(f"  → 完成!")
            break
        
        # 限制事件数量，防止无限循环
        if event_count > 100:
            logger.warning("事件数量超过限制，停止监听")
            break
    
    logger.info(f"事件流结束，共 {event_count} 个事件")
    
    # 查询最终状态
    status = await orchestrator.get_status(run_id)
    logger.info(f"最终状态: {status.status}")


if __name__ == "__main__":
    asyncio.run(test_langgraph_execution())
