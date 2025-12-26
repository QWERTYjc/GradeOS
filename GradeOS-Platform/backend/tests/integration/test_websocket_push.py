"""
WebSocket 推送集成测试

测试 WebSocket 连接建立和状态推送功能。

验证：需求 7.1
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import WebSocket, WebSocketDisconnect

from src.services.enhanced_api import (
    EnhancedAPIService,
    EnhancedAPIConfig,
    QueryParams,
    PaginatedResponse,
    SortOrder,
    SlowQueryRecord,
)
from src.utils.pool_manager import UnifiedPoolManager


class MockWebSocket:
    """模拟 WebSocket 连接"""
    
    def __init__(self, should_disconnect: bool = False, disconnect_after: int = 0):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.sent_messages: List[Dict[str, Any]] = []
        self.sent_texts: List[str] = []
        self.should_disconnect = should_disconnect
        self.disconnect_after = disconnect_after
        self._receive_count = 0
        self._receive_queue: List[str] = []
    
    async def accept(self):
        self.accepted = True
    
    async def close(self, code: int = 1000, reason: str = None):
        self.closed = True
        self.close_code = code
        self.close_reason = reason
    
    async def send_json(self, data: Dict[str, Any]):
        if self.closed:
            raise WebSocketDisconnect()
        self.sent_messages.append(data)
    
    async def send_text(self, text: str):
        if self.closed:
            raise WebSocketDisconnect()
        self.sent_texts.append(text)
    
    async def receive_text(self) -> str:
        self._receive_count += 1
        
        if self.should_disconnect and self._receive_count > self.disconnect_after:
            raise WebSocketDisconnect()
        
        if self._receive_queue:
            return self._receive_queue.pop(0)
        
        # 模拟等待消息
        await asyncio.sleep(0.1)
        return "ping"
    
    def queue_message(self, message: str):
        """添加消息到接收队列"""
        self._receive_queue.append(message)


class MockRedisClient:
    """模拟 Redis 客户端"""
    
    def __init__(self):
        self._data = {}
    
    async def get(self, key: str):
        return self._data.get(key)
    
    async def setex(self, key: str, ttl: int, value: str):
        self._data[key] = value
    
    def pubsub(self):
        return MockPubSub()


class MockPubSub:
    """模拟 Redis PubSub"""
    
    def __init__(self):
        self._subscribed = []
    
    async def psubscribe(self, pattern: str):
        self._subscribed.append(pattern)
    
    async def punsubscribe(self, pattern: str):
        pass
    
    async def close(self):
        pass
    
    async def listen(self):
        # 模拟空消息流
        while True:
            await asyncio.sleep(1)
            yield {"type": "pmessage", "channel": b"test", "data": b"{}"}


class MockPoolManager:
    """模拟统一连接池管理器"""
    
    def __init__(self):
        self._redis_client = MockRedisClient()
        self._pg_data = {}
    
    def get_redis_client(self):
        return self._redis_client
    
    def pg_connection(self):
        return MockPgConnection(self._pg_data)


class MockPgConnection:
    """模拟 PostgreSQL 连接"""
    
    def __init__(self, data: dict):
        self._data = data
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def execute(self, query: str, params=None):
        return MockPgResult(self._data)


class MockPgResult:
    """模拟 PostgreSQL 查询结果"""
    
    def __init__(self, data: dict):
        self._data = data
    
    async def fetchone(self):
        return self._data.get("row")
    
    async def fetchall(self):
        return self._data.get("rows", [])


class TestWebSocketConnectionManagement:
    """
    测试 WebSocket 连接管理
    
    验证：需求 7.1
    """
    
    @pytest.mark.asyncio
    async def test_websocket_connection_acceptance(self):
        """测试 WebSocket 连接接受
        
        验证：需求 7.1
        """
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig(max_websocket_connections=100)
        )
        service._running = True
        
        websocket = MockWebSocket(should_disconnect=True, disconnect_after=1)
        
        await service.handle_websocket(websocket, "sub_001")
        
        # 验证连接已接受
        assert websocket.accepted is True
    
    @pytest.mark.asyncio
    async def test_websocket_initial_state_sent(self):
        """测试发送初始状态
        
        验证：需求 7.1
        """
        pool_manager = MockPoolManager()
        
        # 设置初始状态数据
        pool_manager._pg_data["row"] = {
            "submission_id": "sub_001",
            "exam_id": "exam_001",
            "student_id": "student_001",
            "status": "grading",
            "total_score": None,
            "max_total_score": 100.0,
            "created_at": datetime(2025, 12, 13, 10, 0, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 12, 13, 10, 5, 0, tzinfo=timezone.utc),
        }
        
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig(max_websocket_connections=100)
        )
        service._running = True
        
        websocket = MockWebSocket(should_disconnect=True, disconnect_after=1)
        
        await service.handle_websocket(websocket, "sub_001")
        
        # 验证发送了初始状态
        initial_messages = [m for m in websocket.sent_messages if m.get("type") == "initial_state"]
        assert len(initial_messages) >= 1
        
        initial_state = initial_messages[0]["data"]
        assert initial_state["submission_id"] == "sub_001"
        assert initial_state["status"] == "grading"
    
    @pytest.mark.asyncio
    async def test_websocket_heartbeat_response(self):
        """测试心跳响应
        
        验证：需求 7.1
        """
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig(
                max_websocket_connections=100,
                websocket_heartbeat_interval=0.1
            )
        )
        service._running = True
        
        websocket = MockWebSocket(should_disconnect=True, disconnect_after=2)
        websocket.queue_message("ping")
        
        await service.handle_websocket(websocket, "sub_001")
        
        # 验证发送了 pong 响应
        assert "pong" in websocket.sent_texts
    
    @pytest.mark.asyncio
    async def test_websocket_connection_limit(self):
        """测试连接数限制
        
        验证：需求 7.1
        """
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig(max_websocket_connections=2)
        )
        service._running = True
        
        # 模拟已有连接
        service._websocket_connections["sub_001"] = {MockWebSocket(), MockWebSocket()}
        
        # 尝试新连接
        websocket = MockWebSocket()
        await service.handle_websocket(websocket, "sub_002")
        
        # 验证连接被拒绝
        assert websocket.closed is True
        assert websocket.close_code == 1013


class TestStateBroadcast:
    """
    测试状态广播
    
    验证：需求 7.1
    """
    
    @pytest.mark.asyncio
    async def test_broadcast_state_change(self):
        """测试广播状态变更
        
        验证：需求 7.1
        """
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        # 注册连接
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        service._websocket_connections["sub_001"] = {ws1, ws2}
        
        state = {
            "status": "completed",
            "total_score": 85.0
        }
        
        sent_count = await service.broadcast_state_change("sub_001", state)
        
        # 验证发送给所有连接
        assert sent_count == 2
        
        # 验证消息内容
        for ws in [ws1, ws2]:
            assert len(ws.sent_messages) == 1
            msg = ws.sent_messages[0]
            assert msg["type"] == "state_change"
            assert msg["data"]["status"] == "completed"
            assert msg["data"]["total_score"] == 85.0
            assert "timestamp" in msg
    
    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_submission(self):
        """测试广播到不存在的提交"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        sent_count = await service.broadcast_state_change(
            "nonexistent_sub",
            {"status": "completed"}
        )
        
        # 验证没有发送
        assert sent_count == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        """测试广播时移除死连接"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        # 创建一个正常连接和一个已关闭的连接
        ws_alive = MockWebSocket()
        ws_dead = MockWebSocket()
        ws_dead.closed = True
        
        service._websocket_connections["sub_001"] = {ws_alive, ws_dead}
        
        sent_count = await service.broadcast_state_change(
            "sub_001",
            {"status": "completed"}
        )
        
        # 验证只发送给活跃连接
        assert sent_count == 1
        assert len(ws_alive.sent_messages) == 1


class TestConnectionStatistics:
    """测试连接统计"""
    
    def test_get_active_connections_count(self):
        """测试获取活跃连接数"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        # 添加一些连接
        service._websocket_connections["sub_001"] = {MockWebSocket(), MockWebSocket()}
        service._websocket_connections["sub_002"] = {MockWebSocket()}
        
        count = service.get_active_connections_count()
        
        assert count == 3
    
    def test_get_subscribed_submissions(self):
        """测试获取有订阅的提交列表"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        service._websocket_connections["sub_001"] = {MockWebSocket()}
        service._websocket_connections["sub_002"] = {MockWebSocket()}
        
        submissions = service.get_subscribed_submissions()
        
        assert "sub_001" in submissions
        assert "sub_002" in submissions
        assert len(submissions) == 2


class TestServiceLifecycle:
    """测试服务生命周期"""
    
    @pytest.mark.asyncio
    async def test_service_start(self):
        """测试服务启动"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        await service.start()
        
        assert service._running is True
        assert service._pubsub_task is not None
    
    @pytest.mark.asyncio
    async def test_service_stop(self):
        """测试服务停止"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        await service.start()
        
        # 添加一些连接
        ws = MockWebSocket()
        service._websocket_connections["sub_001"] = {ws}
        
        await service.stop()
        
        assert service._running is False
        assert len(service._websocket_connections) == 0
    
    @pytest.mark.asyncio
    async def test_service_stats(self):
        """测试服务统计信息"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig()
        )
        
        stats = service.stats
        
        assert "queries_executed" in stats
        assert "slow_queries" in stats
        assert "websocket_connections" in stats
        assert "messages_broadcast" in stats


class TestSlowQueryMonitoring:
    """
    测试慢查询监控
    
    验证：需求 7.4
    """
    
    @pytest.mark.asyncio
    async def test_slow_query_recording(self):
        """测试慢查询记录
        
        验证：需求 7.4
        """
        pool_manager = MockPoolManager()
        
        alert_records = []
        
        async def alert_callback(record: SlowQueryRecord):
            alert_records.append(record)
        
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig(
                slow_query_threshold_ms=10,  # 低阈值便于测试
                enable_slow_query_logging=True
            ),
            alert_callback=alert_callback
        )
        
        # 模拟慢查询
        await service._record_slow_query(
            query_id="test_query",
            table="submissions",
            params={"page": 1},
            duration_ms=100,  # 超过阈值
            trace_id="trace_001"
        )
        
        # 验证记录了慢查询
        assert service.stats["slow_queries"] >= 1
        
        # 验证触发了告警
        assert len(alert_records) >= 1
        assert alert_records[0].duration_ms == 100
    
    @pytest.mark.asyncio
    async def test_get_slow_queries(self):
        """测试获取慢查询记录"""
        pool_manager = MockPoolManager()
        service = EnhancedAPIService(
            pool_manager=pool_manager,
            config=EnhancedAPIConfig(
                slow_query_threshold_ms=10,
                enable_slow_query_logging=True
            )
        )
        
        # 记录一些慢查询
        await service._record_slow_query(
            query_id="q1",
            table="submissions",
            params={},
            duration_ms=100,
            trace_id="t1"
        )
        await service._record_slow_query(
            query_id="q2",
            table="grading_results",
            params={},
            duration_ms=200,
            trace_id="t2"
        )
        
        records = await service.get_slow_queries(limit=10)
        
        assert len(records) == 2
        # 验证按时间倒序排序
        assert records[0]["duration_ms"] >= records[1]["duration_ms"] or \
               records[0]["timestamp"] >= records[1]["timestamp"]


class TestRateLimitResponse:
    """
    测试限流响应
    
    验证：需求 7.5
    """
    
    def test_create_rate_limit_response(self):
        """测试创建限流响应
        
        验证：需求 7.5
        """
        response = EnhancedAPIService.create_rate_limit_response(
            retry_after=30,
            limit=100,
            window_seconds=60
        )
        
        assert response["error"] == "rate_limit_exceeded"
        assert response["retry_after"] == 30
        assert response["limit"] == 100
        assert response["window_seconds"] == 60
        assert "message" in response
    
    def test_get_rate_limit_headers(self):
        """测试获取限流响应头
        
        验证：需求 7.5
        """
        headers = EnhancedAPIService.get_rate_limit_headers(
            retry_after=30,
            limit=100,
            remaining=0,
            reset_at="2025-12-13T10:01:00Z"
        )
        
        assert headers["Retry-After"] == "30"
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "0"
        assert headers["X-RateLimit-Reset"] == "2025-12-13T10:01:00Z"


class TestQueryParams:
    """测试查询参数"""
    
    def test_query_params_defaults(self):
        """测试查询参数默认值"""
        params = QueryParams()
        
        assert params.page == 1
        assert params.page_size == 20
        assert params.sort_by is None
        assert params.sort_order == SortOrder.DESC
        assert params.filters is None
    
    def test_query_params_custom_values(self):
        """测试自定义查询参数"""
        params = QueryParams(
            page=3,
            page_size=50,
            sort_by="created_at",
            sort_order=SortOrder.ASC,
            filters={"status": "completed"}
        )
        
        assert params.page == 3
        assert params.page_size == 50
        assert params.sort_by == "created_at"
        assert params.sort_order == SortOrder.ASC
        assert params.filters["status"] == "completed"


class TestPaginatedResponse:
    """测试分页响应"""
    
    def test_paginated_response_creation(self):
        """测试分页响应创建"""
        response = PaginatedResponse(
            items=[{"id": 1}, {"id": 2}],
            total=100,
            page=1,
            page_size=20,
            total_pages=5,
            has_next=True,
            has_prev=False
        )
        
        assert len(response.items) == 2
        assert response.total == 100
        assert response.page == 1
        assert response.page_size == 20
        assert response.total_pages == 5
        assert response.has_next is True
        assert response.has_prev is False
