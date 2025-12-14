"""追踪标识传递完整性属性测试

**功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
**验证: 需求 5.1, 5.2, 5.3**

属性 10 定义：对于任意 API 请求，生成的 trace_id 应当传递给 Temporal 工作流、
所有 Activity 调用和 LangGraph 节点，所有组件的日志应当包含相同的 trace_id。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any

from src.services.tracing import (
    TracingService,
    TracingConfig,
    TraceSpan,
    TraceContext,
    SpanKind,
    SpanStatus,
)
from src.utils.pool_manager import UnifiedPoolManager


def create_tracing_service(enable_persistence: bool = False) -> TracingService:
    """创建追踪服务实例（用于测试）"""
    mock_pool_manager = MagicMock(spec=UnifiedPoolManager)
    config = TracingConfig(
        enable_persistence=enable_persistence,
        enable_alerts=False,
    )
    return TracingService(pool_manager=mock_pool_manager, config=config)


# 生成有效 trace_id 的策略
trace_id_strategy = st.text(
    alphabet="0123456789abcdef-",
    min_size=36,
    max_size=36,
).filter(lambda x: x.count("-") == 4)

# 生成跨度名称的策略
span_name_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_.",
    min_size=1,
    max_size=50,
)

# 生成属性字典的策略
attributes_strategy = st.dictionaries(
    keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20),
    values=st.one_of(
        st.text(min_size=0, max_size=50),
        st.integers(min_value=-1000, max_value=1000),
        st.booleans(),
    ),
    min_size=0,
    max_size=5,
)

# 生成跨度类型的策略
span_kind_strategy = st.sampled_from(list(SpanKind))


class TestTraceIdPropagation:
    """追踪标识传递完整性属性测试
    
    **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
    **验证: 需求 5.1, 5.2, 5.3**
    """
    
    @given(
        num_spans=st.integers(min_value=1, max_value=20),
        span_kinds=st.lists(span_kind_strategy, min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_trace_id_consistent_across_all_spans(self, num_spans, span_kinds):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        对于任意追踪，所有跨度应当共享相同的 trace_id。
        """
        service = create_tracing_service()
        
        # 生成唯一的 trace_id
        trace_id = service.generate_trace_id()
        
        # 创建多个跨度
        spans: List[TraceSpan] = []
        for i in range(min(num_spans, len(span_kinds))):
            span = service.start_span(
                trace_id=trace_id,
                kind=span_kinds[i],
                name=f"span_{i}",
            )
            spans.append(span)
        
        # 验证所有跨度的 trace_id 相同
        for span in spans:
            assert span.trace_id == trace_id, (
                f"跨度 trace_id 不一致:\n"
                f"  expected: {trace_id}\n"
                f"  actual: {span.trace_id}"
            )
    
    @given(
        depth=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50)
    def test_trace_id_preserved_in_parent_child_chain(self, depth):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        对于任意深度的父子跨度链，trace_id 应当在整个链中保持一致。
        """
        service = create_tracing_service()
        
        trace_id = service.generate_trace_id()
        
        # 构建父子链
        spans: List[TraceSpan] = []
        parent_span_id = None
        
        for i in range(depth):
            span = service.start_span(
                trace_id=trace_id,
                kind=SpanKind.INTERNAL,
                name=f"level_{i}",
                parent_span_id=parent_span_id,
            )
            spans.append(span)
            parent_span_id = span.span_id
        
        # 验证所有跨度的 trace_id 相同
        for i, span in enumerate(spans):
            assert span.trace_id == trace_id, f"层级 {i} 的 trace_id 不一致"
        
        # 验证父子关系正确
        for i in range(1, len(spans)):
            assert spans[i].parent_span_id == spans[i-1].span_id, (
                f"层级 {i} 的父跨度 ID 不正确"
            )
    
    @given(
        attributes=attributes_strategy,
    )
    @settings(max_examples=100)
    def test_trace_context_preserves_trace_id(self, attributes):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        TraceContext 在序列化和反序列化后应当保持 trace_id 不变。
        """
        service = create_tracing_service()
        
        trace_id = service.generate_trace_id()
        span_id = service.generate_span_id()
        
        # 创建上下文
        context = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            attributes=attributes,
        )
        
        # 序列化和反序列化
        context_dict = context.to_dict()
        recovered_context = TraceContext.from_dict(context_dict)
        
        # 验证 trace_id 保持不变
        assert recovered_context.trace_id == trace_id
        assert recovered_context.span_id == span_id
        assert recovered_context.attributes == attributes
    
    @given(
        num_children=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50)
    def test_child_context_inherits_trace_id(self, num_children):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        子上下文应当继承父上下文的 trace_id。
        """
        service = create_tracing_service()
        
        trace_id = service.generate_trace_id()
        parent_context = TraceContext(
            trace_id=trace_id,
            span_id=service.generate_span_id(),
            attributes={"parent": True},
        )
        
        # 创建多个子上下文
        child_contexts: List[TraceContext] = []
        for i in range(num_children):
            child_span_id = service.generate_span_id()
            child_context = parent_context.child_context(child_span_id)
            child_contexts.append(child_context)
        
        # 验证所有子上下文继承了 trace_id
        for i, child in enumerate(child_contexts):
            assert child.trace_id == trace_id, f"子上下文 {i} 的 trace_id 不一致"
            assert child.span_id != parent_context.span_id, f"子上下文 {i} 的 span_id 应当不同"


class TestSpanIdUniqueness:
    """跨度 ID 唯一性测试
    
    **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
    **验证: 需求 5.1, 5.2, 5.3**
    """
    
    @given(
        num_spans=st.integers(min_value=2, max_value=100),
    )
    @settings(max_examples=50)
    def test_span_ids_unique_within_trace(self, num_spans):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        同一追踪中的所有跨度应当有唯一的 span_id。
        """
        service = create_tracing_service()
        
        trace_id = service.generate_trace_id()
        
        span_ids = set()
        for i in range(num_spans):
            span = service.start_span(
                trace_id=trace_id,
                kind=SpanKind.INTERNAL,
                name=f"span_{i}",
            )
            
            # 验证 span_id 唯一
            assert span.span_id not in span_ids, (
                f"span_id 重复: {span.span_id}"
            )
            span_ids.add(span.span_id)
        
        assert len(span_ids) == num_spans
    
    @given(
        num_traces=st.integers(min_value=2, max_value=50),
    )
    @settings(max_examples=50)
    def test_trace_ids_unique(self, num_traces):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1**
        
        生成的 trace_id 应当唯一。
        """
        service = create_tracing_service()
        
        trace_ids = set()
        for _ in range(num_traces):
            trace_id = service.generate_trace_id()
            
            # 验证 trace_id 唯一
            assert trace_id not in trace_ids, f"trace_id 重复: {trace_id}"
            trace_ids.add(trace_id)
        
        assert len(trace_ids) == num_traces


class TestCrossComponentPropagation:
    """跨组件传递测试
    
    **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
    **验证: 需求 5.1, 5.2, 5.3**
    """
    
    @given(
        workflow_name=span_name_strategy,
        activity_names=st.lists(span_name_strategy, min_size=1, max_size=5),
        node_names=st.lists(span_name_strategy, min_size=1, max_size=5),
    )
    @settings(max_examples=50)
    def test_trace_id_propagates_through_components(
        self, workflow_name, activity_names, node_names
    ):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        trace_id 应当正确传递给 Temporal 工作流、Activity 和 LangGraph 节点。
        """
        service = create_tracing_service()
        
        # 模拟 API 请求生成 trace_id
        trace_id = service.generate_trace_id()
        
        # 模拟 API 跨度
        api_span = service.start_span(
            trace_id=trace_id,
            kind=SpanKind.API,
            name="api_request",
        )
        
        # 模拟 Temporal 工作流跨度
        workflow_span = service.start_span(
            trace_id=trace_id,
            kind=SpanKind.TEMPORAL_WORKFLOW,
            name=workflow_name,
            parent_span_id=api_span.span_id,
        )
        
        # 模拟 Activity 跨度
        activity_spans = []
        for activity_name in activity_names:
            activity_span = service.start_span(
                trace_id=trace_id,
                kind=SpanKind.TEMPORAL_ACTIVITY,
                name=activity_name,
                parent_span_id=workflow_span.span_id,
            )
            activity_spans.append(activity_span)
        
        # 模拟 LangGraph 节点跨度
        node_spans = []
        parent_id = activity_spans[0].span_id if activity_spans else workflow_span.span_id
        for node_name in node_names:
            node_span = service.start_span(
                trace_id=trace_id,
                kind=SpanKind.LANGGRAPH_NODE,
                name=node_name,
                parent_span_id=parent_id,
            )
            node_spans.append(node_span)
            parent_id = node_span.span_id
        
        # 收集所有跨度
        all_spans = [api_span, workflow_span] + activity_spans + node_spans
        
        # 验证所有跨度的 trace_id 相同
        for span in all_spans:
            assert span.trace_id == trace_id, (
                f"跨度 '{span.name}' (kind={span.kind.value}) 的 trace_id 不一致"
            )
    
    @given(
        attributes=attributes_strategy,
    )
    @settings(max_examples=100)
    def test_span_attributes_preserved(self, attributes):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        跨度属性应当正确保存和传递。
        """
        service = create_tracing_service()
        
        trace_id = service.generate_trace_id()
        
        span = service.start_span(
            trace_id=trace_id,
            kind=SpanKind.API,
            name="test_span",
            attributes=attributes,
        )
        
        # 验证属性正确保存
        assert span.attributes == attributes
        
        # 验证序列化后属性保持不变
        span_dict = span.to_dict()
        assert span_dict["attributes"] == attributes
        
        # 验证反序列化后属性保持不变
        recovered_span = TraceSpan.from_dict(span_dict)
        assert recovered_span.attributes == attributes


class TestTraceSpanSerialization:
    """跨度序列化测试
    
    **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
    **验证: 需求 5.1, 5.2, 5.3**
    """
    
    @given(
        kind=span_kind_strategy,
        name=span_name_strategy,
        attributes=attributes_strategy,
        status=st.sampled_from(list(SpanStatus)),
    )
    @settings(max_examples=100)
    def test_span_round_trip_serialization(self, kind, name, attributes, status):
        """
        **功能: architecture-deep-integration, 属性 10: 追踪标识传递完整性**
        **验证: 需求 5.1, 5.2, 5.3**
        
        跨度序列化和反序列化应当保持所有字段不变。
        """
        service = create_tracing_service()
        
        trace_id = service.generate_trace_id()
        parent_span_id = service.generate_span_id()
        
        # 创建跨度
        span = TraceSpan(
            trace_id=trace_id,
            span_id=service.generate_span_id(),
            kind=kind,
            name=name,
            start_time=datetime.now(timezone.utc),
            parent_span_id=parent_span_id,
            end_time=datetime.now(timezone.utc),
            duration_ms=100,
            attributes=attributes,
            status=status,
        )
        
        # 序列化和反序列化
        span_dict = span.to_dict()
        recovered_span = TraceSpan.from_dict(span_dict)
        
        # 验证所有字段保持不变
        assert recovered_span.trace_id == span.trace_id
        assert recovered_span.span_id == span.span_id
        assert recovered_span.parent_span_id == span.parent_span_id
        assert recovered_span.kind == span.kind
        assert recovered_span.name == span.name
        assert recovered_span.attributes == span.attributes
        assert recovered_span.status == span.status
        assert recovered_span.duration_ms == span.duration_ms
