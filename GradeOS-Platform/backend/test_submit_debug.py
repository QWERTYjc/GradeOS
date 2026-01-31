"""
调试批改提交问题的测试脚本
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from src.api.dependencies import init_orchestrator, get_orchestrator
from src.utils.database import init_db_pool


async def test_orchestrator():
    """测试 orchestrator 是否正常初始化"""
    print("=" * 60)
    print("测试 1: 初始化 Orchestrator")
    print("=" * 60)
    
    try:
        # 初始化数据库
        await init_db_pool()
        print("✓ 数据库连接池初始化成功")
        
        # 初始化 orchestrator
        await init_orchestrator()
        print("✓ Orchestrator 初始化成功")
        
        # 获取 orchestrator 实例
        orchestrator = await get_orchestrator()
        
        if orchestrator is None:
            print("✗ Orchestrator 实例为 None!")
            return False
        
        print(f"✓ Orchestrator 实例: {type(orchestrator).__name__}")
        
        # 检查是否注册了 batch_grading graph
        if hasattr(orchestrator, '_graph_registry'):
            graphs = list(orchestrator._graph_registry.keys())
            print(f"✓ 已注册的 Graphs: {graphs}")
            
            if 'batch_grading' not in graphs:
                print("✗ batch_grading Graph 未注册!")
                return False
            else:
                print("✓ batch_grading Graph 已注册")
        
        return True
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_simple_run():
    """测试简单的批改流程"""
    print("\n" + "=" * 60)
    print("测试 2: 启动简单批改任务")
    print("=" * 60)
    
    try:
        orchestrator = await get_orchestrator()
        if not orchestrator:
            print("✗ Orchestrator 未初始化")
            return False
        
        # 创建测试 payload
        test_payload = {
            "batch_id": "test_debug_001",
            "exam_id": "test_exam",
            "rubric_images": [],
            "answer_images": [],
            "api_key": os.getenv("LLM_API_KEY"),
            "inputs": {
                "rubric": "test rubric",
                "auto_identify": True,
                "manual_boundaries": [],
                "expected_students": 1,
                "enable_review": False,
                "grading_mode": "auto",
            }
        }
        
        print(f"payload keys: {list(test_payload.keys())}")
        print(f"API Key 存在: {bool(test_payload['api_key'])}")
        
        # 尝试启动
        print("\n尝试启动 batch_grading...")
        run_id = await orchestrator.start_run(
            graph_name="batch_grading",
            payload=test_payload,
            idempotency_key="test_debug_001"
        )
        
        print(f"✓ 任务已启动! run_id: {run_id}")
        
        # 等待一会儿
        await asyncio.sleep(2)
        
        # 检查状态
        status = await orchestrator.get_status(run_id)
        print(f"✓ 任务状态: {status.status.value}")
        
        return True
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n🔍 GradeOS 批改提交诊断工具\n")
    
    # 测试 1: Orchestrator 初始化
    test1_ok = await test_orchestrator()
    
    if not test1_ok:
        print("\n❌ Orchestrator 初始化失败，无法继续测试")
        return
    
    # 测试 2: 简单批改任务
    test2_ok = await test_simple_run()
    
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    print(f"Orchestrator 初始化: {'✓ 通过' if test1_ok else '✗ 失败'}")
    print(f"批改任务启动: {'✓ 通过' if test2_ok else '✗ 失败'}")
    
    if test1_ok and test2_ok:
        print("\n✅ 所有测试通过！批改系统应该可以正常工作。")
        print("\n可能的问题：")
        print("1. 前端 WebSocket 连接问题")
        print("2. 前端提交时的参数问题")
        print("3. 后端日志中有具体错误信息")
    else:
        print("\n❌ 发现问题！请检查上面的错误信息。")


if __name__ == "__main__":
    asyncio.run(main())
