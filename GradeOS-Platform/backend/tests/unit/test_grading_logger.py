"""单元测试：批改日志服务

测试 GradingLogger 的核心功能
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.grading_log import GradingLog
from src.services.grading_logger import GradingLogger


def test_grading_logger_initialization():
    """测试 GradingLogger 初始化"""
    logger = GradingLogger(max_pending_size=100)
    
    assert logger.get_pending_count() == 0
    assert logger._pending_logs.maxlen == 100


def test_pending_logs_management():
    """测试暂存日志管理"""
    logger = GradingLogger(max_pending_size=10)
    
    # 添加日志到暂存队列
    for i in range(5):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id=f"q{i}",
            extracted_answer=f"answer_{i}",
            extraction_confidence=0.9,
            score=8.0,
            confidence=0.85,
            reasoning_trace=["step1"],
            created_at=datetime.now()
        )
        logger._pending_logs.append(log)
    
    assert logger.get_pending_count() == 5


def test_pending_queue_overflow():
    """测试暂存队列溢出处理"""
    logger = GradingLogger(max_pending_size=5)
    
    # 添加超过容量的日志
    for i in range(10):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id=f"q{i}",
            extracted_answer=f"answer_{i}",
            extraction_confidence=0.9,
            score=8.0,
            confidence=0.85,
            reasoning_trace=["step1"],
            created_at=datetime.now()
        )
        logger._pending_logs.append(log)
    
    # 验证队列大小不超过限制
    assert logger.get_pending_count() == 5


def test_grading_log_model_validation():
    """测试批改日志模型验证"""
    # 创建有效的日志
    log = GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id="q1",
        extracted_answer="test answer",
        extraction_confidence=0.95,
        score=8.5,
        max_score=10.0,
        confidence=0.92,
        reasoning_trace=["step1", "step2"],
        created_at=datetime.now()
    )
    
    assert log.extracted_answer == "test answer"
    assert log.extraction_confidence == 0.95
    assert log.score == 8.5
    assert log.confidence == 0.92
    assert len(log.reasoning_trace) == 2


def test_override_log_model():
    """测试改判日志模型"""
    log = GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id="q1",
        extracted_answer="test answer",
        extraction_confidence=0.95,
        score=8.0,
        confidence=0.92,
        reasoning_trace=["step1"],
        was_overridden=True,
        override_score=9.0,
        override_reason="Teacher correction",
        override_teacher_id=str(uuid4()),
        override_at=datetime.now(),
        created_at=datetime.now()
    )
    
    assert log.was_overridden is True
    assert log.override_score == 9.0
    assert log.override_reason == "Teacher correction"
    assert log.override_teacher_id is not None
    assert log.override_at is not None


def test_get_override_samples_query_structure():
    """测试改判样本查询的结构"""
    logger = GradingLogger()
    
    # 这个测试验证查询方法的存在和参数
    # 实际的数据库查询需要集成测试
    assert hasattr(logger, 'get_override_samples')
    
    # 验证方法签名
    import inspect
    sig = inspect.signature(logger.get_override_samples)
    params = sig.parameters
    
    assert 'min_count' in params
    assert 'days' in params


def test_log_grading_method_exists():
    """测试 log_grading 方法存在"""
    logger = GradingLogger()
    
    assert hasattr(logger, 'log_grading')
    assert callable(logger.log_grading)


def test_log_override_method_exists():
    """测试 log_override 方法存在"""
    logger = GradingLogger()
    
    assert hasattr(logger, 'log_override')
    assert callable(logger.log_override)


def test_flush_pending_method_exists():
    """测试 flush_pending 方法存在"""
    logger = GradingLogger()
    
    assert hasattr(logger, 'flush_pending')
    assert callable(logger.flush_pending)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
