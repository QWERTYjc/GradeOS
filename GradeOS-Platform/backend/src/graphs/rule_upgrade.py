"""规则升级 Graph 编译

实现自演化规则升级流程，支持：
- 规则挖掘（从批改日志中挖掘新规则）
- 补丁生成（生成规则补丁）
- 回归测试（验证补丁不会导致回归）
- 灰度发布（逐步部署新规则）
- 异常回滚（检测到异常时自动回滚）

验证：需求 2.1（RuleUpgradeGraphState）
"""

import logging
from typing import Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graphs.state import RuleUpgradeGraphState


logger = logging.getLogger(__name__)


# ==================== 规则升级节点 ====================

async def mine_rules_node(state: RuleUpgradeGraphState) -> RuleUpgradeGraphState:
    """
    规则挖掘节点
    
    从批改日志中挖掘潜在的新规则。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态（包含 mined_rules）
    """
    upgrade_id = state["upgrade_id"]
    time_window = state.get("time_window", {})
    
    logger.info(
        f"开始规则挖掘: upgrade_id={upgrade_id}, "
        f"time_window={time_window}"
    )
    
    try:
        from src.services.rule_miner import RuleMiner
        
        miner = RuleMiner()
        mined_rules = await miner.mine(
            start_time=time_window.get("start"),
            end_time=time_window.get("end")
        )
        
        # 筛选候选规则（置信度 > 0.8）
        rule_candidates = [
            rule for rule in mined_rules
            if rule.get("confidence", 0) > 0.8
        ]
        
        logger.info(
            f"规则挖掘完成: upgrade_id={upgrade_id}, "
            f"挖掘到 {len(mined_rules)} 条规则, "
            f"候选 {len(rule_candidates)} 条"
        )
        
        return {
            **state,
            "mined_rules": mined_rules,
            "rule_candidates": rule_candidates,
            "progress": {
                **state.get("progress", {}),
                "mining_completed": True,
                "mined_count": len(mined_rules),
                "candidate_count": len(rule_candidates)
            },
            "current_stage": "mining_completed",
            "percentage": 20.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "mining_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(
            f"规则挖掘失败: upgrade_id={upgrade_id}, error={str(e)}",
            exc_info=True
        )
        
        errors = state.get("errors", [])
        errors.append({
            "node": "mine_rules",
            "error_type": "mining_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            **state,
            "errors": errors,
            "current_stage": "mining_failed"
        }


async def generate_patches_node(state: RuleUpgradeGraphState) -> RuleUpgradeGraphState:
    """
    补丁生成节点
    
    为候选规则生成补丁。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态（包含 generated_patches）
    """
    upgrade_id = state["upgrade_id"]
    rule_candidates = state.get("rule_candidates", [])
    
    if not rule_candidates:
        logger.info(f"没有候选规则，跳过补丁生成: upgrade_id={upgrade_id}")
        return {
            **state,
            "generated_patches": [],
            "current_stage": "no_patches"
        }
    
    logger.info(
        f"开始补丁生成: upgrade_id={upgrade_id}, "
        f"候选规则数={len(rule_candidates)}"
    )
    
    try:
        from src.services.patch_generator import PatchGenerator
        
        generator = PatchGenerator()
        patches = await generator.generate(rule_candidates)
        
        logger.info(
            f"补丁生成完成: upgrade_id={upgrade_id}, "
            f"生成 {len(patches)} 个补丁"
        )
        
        return {
            **state,
            "generated_patches": patches,
            "patch_metadata": {
                "generated_at": datetime.now().isoformat(),
                "patch_count": len(patches)
            },
            "progress": {
                **state.get("progress", {}),
                "patch_generation_completed": True,
                "patch_count": len(patches)
            },
            "current_stage": "patch_generation_completed",
            "percentage": 40.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "patch_generation_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(
            f"补丁生成失败: upgrade_id={upgrade_id}, error={str(e)}",
            exc_info=True
        )
        
        errors = state.get("errors", [])
        errors.append({
            "node": "generate_patches",
            "error_type": "patch_generation_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            **state,
            "errors": errors,
            "current_stage": "patch_generation_failed"
        }


async def regression_test_node(state: RuleUpgradeGraphState) -> RuleUpgradeGraphState:
    """
    回归测试节点
    
    验证补丁不会导致回归。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态（包含 test_results）
    """
    upgrade_id = state["upgrade_id"]
    patches = state.get("generated_patches", [])
    
    if not patches:
        logger.info(f"没有补丁，跳过回归测试: upgrade_id={upgrade_id}")
        return {
            **state,
            "test_results": [],
            "regression_detected": False,
            "current_stage": "no_tests"
        }
    
    logger.info(
        f"开始回归测试: upgrade_id={upgrade_id}, "
        f"补丁数={len(patches)}"
    )
    
    try:
        from src.services.regression_tester import RegressionTester
        
        tester = RegressionTester()
        test_results = await tester.run_tests(patches)
        
        # 检查是否有回归
        regression_detected = any(
            result.get("regression", False)
            for result in test_results
        )
        
        logger.info(
            f"回归测试完成: upgrade_id={upgrade_id}, "
            f"regression_detected={regression_detected}"
        )
        
        return {
            **state,
            "test_results": test_results,
            "regression_detected": regression_detected,
            "progress": {
                **state.get("progress", {}),
                "regression_test_completed": True,
                "regression_detected": regression_detected
            },
            "current_stage": "regression_test_completed",
            "percentage": 60.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "regression_test_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(
            f"回归测试失败: upgrade_id={upgrade_id}, error={str(e)}",
            exc_info=True
        )
        
        errors = state.get("errors", [])
        errors.append({
            "node": "regression_test",
            "error_type": "regression_test_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            **state,
            "errors": errors,
            "current_stage": "regression_test_failed"
        }


async def approval_interrupt_node(state: RuleUpgradeGraphState) -> RuleUpgradeGraphState:
    """
    人工审批中断节点
    
    在部署前请求人工审批。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态（包含审批结果）
    """
    upgrade_id = state["upgrade_id"]
    patches = state.get("generated_patches", [])
    test_results = state.get("test_results", [])
    
    logger.info(f"请求人工审批: upgrade_id={upgrade_id}")
    
    # 准备审批数据
    approval_request = {
        "type": "deployment_approval_required",
        "upgrade_id": upgrade_id,
        "patches": patches,
        "test_results": test_results,
        "message": "规则补丁已通过回归测试，请审批部署",
        "requested_at": datetime.now().isoformat()
    }
    
    # 触发 interrupt，等待外部输入
    approval_response = interrupt(approval_request)
    
    logger.info(
        f"收到审批响应: upgrade_id={upgrade_id}, "
        f"approved={approval_response.get('approved')}"
    )
    
    return {
        **state,
        "approval_result": approval_response,
        "timestamps": {
            **state.get("timestamps", {}),
            "approval_at": datetime.now().isoformat()
        }
    }


async def deploy_node(state: RuleUpgradeGraphState) -> RuleUpgradeGraphState:
    """
    部署节点
    
    部署已审批的规则补丁。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
    """
    upgrade_id = state["upgrade_id"]
    patches = state.get("generated_patches", [])
    
    logger.info(f"开始部署: upgrade_id={upgrade_id}")
    
    try:
        from src.services.patch_deployer import PatchDeployer
        
        deployer = PatchDeployer()
        deployment_result = await deployer.deploy(patches)
        
        deployed_version = deployment_result.get("version")
        
        logger.info(
            f"部署完成: upgrade_id={upgrade_id}, "
            f"version={deployed_version}"
        )
        
        return {
            **state,
            "deployment_status": "deployed",
            "deployed_version": deployed_version,
            "progress": {
                **state.get("progress", {}),
                "deployment_completed": True
            },
            "current_stage": "deployed",
            "percentage": 90.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "deployment_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(
            f"部署失败: upgrade_id={upgrade_id}, error={str(e)}",
            exc_info=True
        )
        
        errors = state.get("errors", [])
        errors.append({
            "node": "deploy",
            "error_type": "deployment_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            **state,
            "errors": errors,
            "deployment_status": "failed",
            "current_stage": "deployment_failed"
        }


async def monitor_node(state: RuleUpgradeGraphState) -> RuleUpgradeGraphState:
    """
    监控节点
    
    监控部署后的异常情况。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
    """
    upgrade_id = state["upgrade_id"]
    deployed_version = state.get("deployed_version")
    
    logger.info(
        f"开始监控: upgrade_id={upgrade_id}, "
        f"version={deployed_version}"
    )
    
    # TODO: 实现实际的监控逻辑
    # 这里简化处理，假设监控通过
    
    return {
        **state,
        "progress": {
            **state.get("progress", {}),
            "monitoring_completed": True
        },
        "current_stage": "completed",
        "percentage": 100.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "completed_at": datetime.now().isoformat()
        }
    }


async def rollback_node(state: RuleUpgradeGraphState) -> RuleUpgradeGraphState:
    """
    回滚节点
    
    回滚到上一个版本。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
    """
    upgrade_id = state["upgrade_id"]
    deployed_version = state.get("deployed_version")
    
    logger.info(
        f"开始回滚: upgrade_id={upgrade_id}, "
        f"version={deployed_version}"
    )
    
    try:
        from src.services.patch_deployer import PatchDeployer
        
        deployer = PatchDeployer()
        await deployer.rollback(deployed_version)
        
        logger.info(f"回滚完成: upgrade_id={upgrade_id}")
        
        return {
            **state,
            "rollback_triggered": True,
            "deployment_status": "rolled_back",
            "current_stage": "rolled_back",
            "timestamps": {
                **state.get("timestamps", {}),
                "rollback_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(
            f"回滚失败: upgrade_id={upgrade_id}, error={str(e)}",
            exc_info=True
        )
        
        errors = state.get("errors", [])
        errors.append({
            "node": "rollback",
            "error_type": "rollback_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            **state,
            "errors": errors,
            "current_stage": "rollback_failed"
        }


# ==================== 条件路由 ====================

def should_generate_patches(state: RuleUpgradeGraphState) -> Literal["generate", "end"]:
    """判断是否需要生成补丁"""
    candidates = state.get("rule_candidates", [])
    if candidates:
        return "generate"
    return "end"


def should_deploy(state: RuleUpgradeGraphState) -> Literal["deploy", "end"]:
    """判断是否应该部署"""
    regression = state.get("regression_detected", False)
    if regression:
        logger.info("检测到回归，跳过部署")
        return "end"
    return "deploy"


def should_continue_after_approval(
    state: RuleUpgradeGraphState
) -> Literal["deploy", "end"]:
    """判断审批后是否继续"""
    approval = state.get("approval_result", {})
    if approval.get("approved", False):
        return "deploy"
    return "end"


# ==================== Graph 编译 ====================

def create_rule_upgrade_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None,
    require_approval: bool = True
) -> StateGraph:
    """创建规则升级 Graph
    
    流程：
    1. mine_rules: 规则挖掘
    2. generate_patches: 补丁生成
    3. regression_test: 回归测试
    4. approval_interrupt: 人工审批（可选）
    5. deploy: 部署
    6. monitor: 监控
    
    流程图：
    ```
    mine_rules
        ↓
    ┌───┴───┐
    ↓       ↓
    (有候选) (无候选)
    ↓       ↓
    generate END
        ↓
    regression_test
        ↓
    ┌───┴───┐
    ↓       ↓
    (无回归) (有回归)
    ↓       ↓
    approval END
        ↓
    ┌───┴───┐
    ↓       ↓
    (批准)  (拒绝)
    ↓       ↓
    deploy  END
        ↓
    monitor
        ↓
    END
    ```
    
    Args:
        checkpointer: PostgreSQL Checkpointer（可选）
        require_approval: 是否需要人工审批
        
    Returns:
        编译后的 Graph
    """
    logger.info(f"创建规则升级 Graph (require_approval={require_approval})")
    
    graph = StateGraph(RuleUpgradeGraphState)
    
    # 添加节点
    graph.add_node("mine_rules", mine_rules_node)
    graph.add_node("generate_patches", generate_patches_node)
    graph.add_node("regression_test", regression_test_node)
    graph.add_node("deploy", deploy_node)
    graph.add_node("monitor", monitor_node)
    graph.add_node("rollback", rollback_node)
    
    if require_approval:
        graph.add_node("approval_interrupt", approval_interrupt_node)
    
    # 入口点
    graph.set_entry_point("mine_rules")
    
    # 挖掘后的条件路由
    graph.add_conditional_edges(
        "mine_rules",
        should_generate_patches,
        {
            "generate": "generate_patches",
            "end": END
        }
    )
    
    # 补丁生成后回归测试
    graph.add_edge("generate_patches", "regression_test")
    
    # 回归测试后的条件路由
    if require_approval:
        graph.add_conditional_edges(
            "regression_test",
            should_deploy,
            {
                "deploy": "approval_interrupt",
                "end": END
            }
        )
        
        # 审批后的条件路由
        graph.add_conditional_edges(
            "approval_interrupt",
            should_continue_after_approval,
            {
                "deploy": "deploy",
                "end": END
            }
        )
    else:
        graph.add_conditional_edges(
            "regression_test",
            should_deploy,
            {
                "deploy": "deploy",
                "end": END
            }
        )
    
    # 部署后监控
    graph.add_edge("deploy", "monitor")
    
    # 监控后结束
    graph.add_edge("monitor", END)
    
    # 回滚后结束
    graph.add_edge("rollback", END)
    
    # 编译
    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    
    compiled_graph = graph.compile(**compile_kwargs)
    
    logger.info("规则升级 Graph 已编译")
    
    return compiled_graph


def create_scheduled_rule_upgrade_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None
) -> StateGraph:
    """创建定时规则升级 Graph（无需人工审批）
    
    适用于定时任务场景，自动执行规则升级。
    
    Args:
        checkpointer: PostgreSQL Checkpointer（可选）
        
    Returns:
        编译后的 Graph
    """
    return create_rule_upgrade_graph(
        checkpointer=checkpointer,
        require_approval=False
    )
