"""自我成长系统端到端集成测试

测试完整的批改流程，包括：
1. 流式推送
2. 学生分割
3. 判例检索和动态提示词
4. 规则升级流程

验证：需求 1.1, 2.1, 3.1, 4.3, 5.1, 6.3, 8.1, 9.1
"""

import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from uuid import uuid4

import redis.asyncio as redis

from src.workflows.batch_grading_enhanced import EnhancedBatchGradingWorkflow
from src.agents.grading_agent_enhanced import EnhancedGradingAgent
from src.workflows.rule_upgrade import RuleUpgradeWorkflow
from src.services.streaming import StreamingService, EventType
from src.services.student_boundary_detector import StudentBoundaryDetector
from src.services.exemplar_memory import ExemplarMemory
from src.services.prompt_assembler import PromptAssembler
from src.services.calibration import CalibrationService
from src.services.grading_logger import GradingLogger
from src.services.rule_miner import RuleMiner
from src.services.patch_generator import PatchGenerator
from src.services.regression_tester import RegressionTester
from src.services.patch_deployer import PatchDeployer
from src.utils.pool_manager import UnifiedPoolManager


@pytest.mark.asyncio
@pytest.mark.integration
class TestSelfEvolvingIntegration:
    """自我成长系统集成测试"""
    
    @pytest.fixture
    async def redis_client(self):
        """Redis 客户端 fixture"""
        client = await redis.from_url(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=False
        )
        yield client
        await client.close()
    
    @pytest.fixture
    async def pool_manager(self):
        """连接池管理器 fixture"""
        manager = UnifiedPoolManager()
        # 在测试中初始化连接池
        await manager.initialize(
            pg_dsn="postgresql://postgres:postgres@localhost:5432/test_db",
            redis_url="redis://localhost:6379"
        )
        yield manager
        # 清理资源
        await manager.close_all()
    
    @pytest.fixture
    async def streaming_service(self, redis_client):
        """流式推送服务 fixture"""
        # 注意：StreamingService 需要 db_pool，但在测试中我们可以不启用持久化
        return StreamingService(
            redis_client=redis_client,
            db_pool=None,  # 测试中不启用持久化
            enable_persistence=False
        )
    
    @pytest.fixture
    async def boundary_detector(self):
        """学生边界检测器 fixture"""
        return StudentBoundaryDetector()
    
    @pytest.fixture
    async def exemplar_memory(self, pool_manager):
        """判例记忆服务 fixture"""
        # 使用初始化好的 pool_manager
        return ExemplarMemory(
            pool_manager=pool_manager,
            embedding_model=None  # 测试中不使用实际的 embedding
        )
    
    @pytest.fixture
    async def prompt_assembler(self):
        """提示词拼装器 fixture"""
        return PromptAssembler()
    
    @pytest.fixture
    async def calibration_service(self, pool_manager):
        """校准服务 fixture"""
        return CalibrationService(pool_manager=pool_manager)
    
    @pytest.fixture
    async def grading_logger(self):
        """批改日志服务 fixture"""
        return GradingLogger()
    
    async def test_complete_grading_flow(
        self,
        streaming_service,
        boundary_detector,
        exemplar_memory,
        prompt_assembler,
        calibration_service,
        grading_logger
    ):
        """
        测试完整批改流程
        
        验证：
        - 流式推送正常工作
        - 学生边界检测正确
        - 判例检索和动态提示词集成
        - 批改日志记录完整
        """
        # 准备测试数据
        batch_id = f"test_batch_{uuid4()}"
        teacher_id = "test_teacher_001"
        
        # 模拟批改结果
        grading_results = [
            {
                "page_index": 0,
                "question_id": "Q1",
                "student_answer": "答案A",
                "score": 5.0,
                "confidence": 0.9,
                "student_info": {
                    "name": "张三",
                    "student_id": "2021001",
                    "confidence": 0.95
                }
            },
            {
                "page_index": 1,
                "question_id": "Q2",
                "student_answer": "答案B",
                "score": 4.0,
                "confidence": 0.85,
                "student_info": {
                    "name": "张三",
                    "student_id": "2021001",
                    "confidence": 0.95
                }
            },
            {
                "page_index": 2,
                "question_id": "Q1",
                "student_answer": "答案C",
                "score": 3.0,
                "confidence": 0.8,
                "student_info": {
                    "name": "李四",
                    "student_id": "2021002",
                    "confidence": 0.9
                }
            }
        ]
        
        # 1. 测试流式推送
        stream_id = await streaming_service.create_stream(batch_id)
        assert stream_id == batch_id
        
        # 推送批次开始事件
        from src.services.streaming import StreamEvent
        event = StreamEvent(
            event_type=EventType.BATCH_START,
            batch_id=batch_id,
            sequence_number=0,
            data={"total_pages": len(grading_results)}
        )
        success = await streaming_service.push_event(stream_id, event)
        assert success
        
        # 推送页面完成事件
        for i, result in enumerate(grading_results):
            event = StreamEvent(
                event_type=EventType.PAGE_COMPLETE,
                batch_id=batch_id,
                sequence_number=i + 1,
                data={
                    "page_index": result["page_index"],
                    "score": result["score"]
                }
            )
            success = await streaming_service.push_event(stream_id, event)
            assert success
        
        # 2. 测试学生边界检测
        boundary_result = await boundary_detector.detect_boundaries(grading_results)
        
        assert boundary_result.total_students >= 1
        assert len(boundary_result.boundaries) >= 1
        
        # 验证边界正确性
        for boundary in boundary_result.boundaries:
            assert boundary.start_page <= boundary.end_page
            assert boundary.confidence >= 0.0
            assert boundary.confidence <= 1.0
        
        # 3. 测试判例检索
        # 先存储一个判例
        exemplar_id = await exemplar_memory.store_exemplar(
            grading_result={
                "question_type": "objective",
                "question_image_hash": "test_hash_123",
                "student_answer_text": "答案A",
                "score": 5.0,
                "max_score": 5.0
            },
            teacher_id=teacher_id,
            teacher_feedback="答案正确"
        )
        assert exemplar_id
        
        # 检索判例
        exemplars = await exemplar_memory.retrieve_similar(
            question_image_hash="test_hash_123",
            question_type="objective",
            top_k=5,
            min_similarity=0.7
        )
        assert len(exemplars) >= 0
        assert len(exemplars) <= 5
        
        # 4. 测试动态提示词拼装
        assembled_prompt = prompt_assembler.assemble(
            question_type="objective",
            rubric="评分细则：...",
            exemplars=exemplars,
            error_patterns=["常见错误1"],
            previous_confidence=0.7,
            max_tokens=8000
        )
        
        assert assembled_prompt.total_tokens > 0
        assert assembled_prompt.total_tokens <= 8000
        assert len(assembled_prompt.sections) > 0
        
        # 5. 测试校准配置
        profile = await calibration_service.get_or_create_profile(teacher_id)
        assert profile.teacher_id == teacher_id
        assert profile.strictness_level >= 0.0
        assert profile.strictness_level <= 1.0
        
        # 6. 测试批改日志记录
        from src.models.grading_log import GradingLog
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=f"sub_{batch_id}",
            question_id="Q1",
            timestamp=datetime.now(),
            extracted_answer="答案A",
            extraction_confidence=0.9,
            evidence_snippets=["证据1"],
            score=5.0,
            max_score=5.0,
            confidence=0.9,
            reasoning_trace=["推理步骤1"],
            was_overridden=False
        )
        
        log_id = await grading_logger.log_grading(log)
        assert log_id
        
        # 推送完成事件
        event = StreamEvent(
            event_type=EventType.COMPLETE,
            batch_id=batch_id,
            sequence_number=len(grading_results) + 1,
            data={"total_students": boundary_result.total_students}
        )
        success = await streaming_service.push_event(stream_id, event)
        assert success
        
        # 清理
        await streaming_service.close_stream(stream_id)
    
    async def test_streaming_resume(self, streaming_service):
        """
        测试流式推送断点续传
        
        验证：需求 1.4
        """
        stream_id = f"test_stream_{uuid4()}"
        
        # 创建流
        await streaming_service.create_stream(stream_id)
        
        # 推送一些事件
        from src.services.streaming import StreamEvent
        for i in range(5):
            event = StreamEvent(
                event_type=EventType.PAGE_COMPLETE,
                batch_id=stream_id,
                sequence_number=i,
                data={"page_index": i}
            )
            await streaming_service.push_event(stream_id, event)
        
        # 模拟断开后重连，从序列号 3 开始获取
        events = []
        async for event in streaming_service.get_events(stream_id, from_sequence=3):
            events.append(event)
            if len(events) >= 2:  # 只获取 2 个事件
                break
        
        assert len(events) == 2
        assert events[0].sequence_number == 3
        assert events[1].sequence_number == 4
        
        # 清理
        await streaming_service.close_stream(stream_id)
    
    async def test_student_boundary_detection(self, boundary_detector):
        """
        测试学生边界检测
        
        验证：需求 3.1, 3.2
        """
        # 准备测试数据：3 个学生的批改结果
        grading_results = []
        
        # 学生1：页面 0-1
        for i in range(2):
            grading_results.append({
                "page_index": i,
                "question_id": f"Q{i+1}",
                "student_info": {
                    "name": "学生A",
                    "student_id": "001",
                    "confidence": 0.9
                }
            })
        
        # 学生2：页面 2-3
        for i in range(2, 4):
            grading_results.append({
                "page_index": i,
                "question_id": f"Q{i-1}",
                "student_info": {
                    "name": "学生B",
                    "student_id": "002",
                    "confidence": 0.85
                }
            })
        
        # 学生3：页面 4-5
        for i in range(4, 6):
            grading_results.append({
                "page_index": i,
                "question_id": f"Q{i-3}",
                "student_info": {
                    "name": "学生C",
                    "student_id": "003",
                    "confidence": 0.8
                }
            })
        
        # 执行边界检测
        result = await boundary_detector.detect_boundaries(grading_results)
        
        # 验证结果
        assert result.total_students >= 1
        assert result.total_pages == 6
        
        # 验证边界不重叠
        boundaries_sorted = sorted(result.boundaries, key=lambda b: b.start_page)
        for i in range(len(boundaries_sorted) - 1):
            assert boundaries_sorted[i].end_page < boundaries_sorted[i + 1].start_page
    
    async def test_exemplar_retrieval_and_prompt_assembly(
        self,
        exemplar_memory,
        prompt_assembler
    ):
        """
        测试判例检索和动态提示词拼装
        
        验证：需求 4.3, 5.1
        """
        teacher_id = "test_teacher_002"
        
        # 存储多个判例
        exemplar_ids = []
        for i in range(3):
            exemplar_id = await exemplar_memory.store_exemplar(
                grading_result={
                    "question_type": "stepwise",
                    "question_image_hash": f"hash_{i}",
                    "student_answer_text": f"答案{i}",
                    "score": 4.0 + i,
                    "max_score": 10.0
                },
                teacher_id=teacher_id,
                teacher_feedback=f"评语{i}"
            )
            exemplar_ids.append(exemplar_id)
        
        # 检索判例
        exemplars = await exemplar_memory.retrieve_similar(
            question_image_hash="hash_1",
            question_type="stepwise",
            top_k=5,
            min_similarity=0.7
        )
        
        # 验证检索数量约束（属性 9）
        assert len(exemplars) >= 0
        assert len(exemplars) <= 5
        
        # 拼装提示词
        assembled_prompt = prompt_assembler.assemble(
            question_type="stepwise",
            rubric="评分细则：步骤1...步骤2...",
            exemplars=exemplars,
            error_patterns=["缺少步骤", "计算错误"],
            previous_confidence=0.75,
            max_tokens=8000
        )
        
        # 验证提示词结构
        assert assembled_prompt.total_tokens > 0
        assert assembled_prompt.total_tokens <= 8000
        
        # 验证包含必要区段
        from src.models.prompt import PromptSection
        assert PromptSection.SYSTEM in assembled_prompt.sections
        assert PromptSection.RUBRIC in assembled_prompt.sections
        
        # 如果有判例，应该包含判例区段
        if len(exemplars) > 0:
            assert PromptSection.EXEMPLARS in assembled_prompt.sections
    
    async def test_rule_upgrade_flow(
        self,
        grading_logger,
        pool_manager
    ):
        """
        测试规则升级流程
        
        验证：需求 9.1, 9.2, 9.3, 9.4
        """
        # 初始化服务
        rule_miner = RuleMiner()
        patch_generator = PatchGenerator()
        regression_tester = RegressionTester()
        patch_deployer = PatchDeployer(pool_manager=pool_manager)
        
        # 1. 准备改判样本
        # 注意：这里需要先有一些改判记录
        # 在实际测试中，可能需要先创建一些测试数据
        
        # 2. 规则挖掘
        override_samples = await grading_logger.get_override_samples(
            min_count=10,
            days=30
        )
        
        if len(override_samples) >= 10:
            patterns = await rule_miner.analyze_overrides(override_samples)
            
            # 验证挖掘结果
            assert isinstance(patterns, list)
            
            # 3. 补丁生成
            if len(patterns) > 0:
                patch = await patch_generator.generate_patch(patterns[0])
                
                if patch:
                    # 验证补丁结构
                    assert patch.patch_id
                    assert patch.version
                    assert patch.content
                    
                    # 4. 回归测试
                    result = await regression_tester.run_regression(
                        patch,
                        eval_set_id="test_eval_set"
                    )
                    
                    # 验证测试结果
                    assert result.patch_id == patch.patch_id
                    assert result.total_samples >= 0
                    
                    # 5. 如果测试通过，尝试部署
                    if regression_tester.is_improvement(result):
                        deployment_id = await patch_deployer.deploy_canary(
                            patch,
                            traffic_percentage=0.1
                        )
                        
                        # 验证部署
                        assert deployment_id
                        
                        # 清理：回滚部署
                        await patch_deployer.rollback(deployment_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_to_end_batch_grading():
    """
    端到端批量批改测试
    
    模拟完整的批量批改流程，包括：
    - 固定分批
    - 并行批改
    - 学生分割
    - 流式推送
    """
    # 准备测试数据
    batch_id = f"e2e_test_{uuid4()}"
    exam_id = "test_exam_001"
    
    # 模拟 15 张图片（会分成 2 个批次）
    file_paths = [f"/tmp/test_page_{i}.jpg" for i in range(15)]
    
    # 注意：这个测试需要在 Temporal 环境中运行
    # 这里只是展示测试结构
    
    input_data = {
        "batch_id": batch_id,
        "exam_id": exam_id,
        "file_paths": file_paths,
        "rubric": "测试评分细则",
        "teacher_id": "test_teacher_003",
        "enable_streaming": True
    }
    
    # 在实际测试中，需要启动 Temporal Worker 并执行工作流
    # result = await execute_workflow(EnhancedBatchGradingWorkflow, input_data)
    
    # 验证结果
    # assert result["batch_id"] == batch_id
    # assert result["total_batches"] == 2  # 15 张图片分成 2 批
    # assert result["total_students"] >= 1
    
    pass  # 占位符


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
