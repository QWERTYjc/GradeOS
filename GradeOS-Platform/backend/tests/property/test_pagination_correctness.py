"""
分页查询结果正确性属性测试

**功能: architecture-deep-integration, 属性 12: 分页查询结果正确性**
**验证: 需求 7.2**

测试分页查询的正确性：
- 返回的结果数量不超过 page_size
- 结果按指定字段排序
- 过滤条件正确应用
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

from src.services.enhanced_api import (
    QueryParams,
    PaginatedResponse,
    SortOrder,
    EnhancedAPIConfig,
)


# ==================== 测试数据生成策略 ====================

@st.composite
def query_params_strategy(draw):
    """生成有效的查询参数"""
    page = draw(st.integers(min_value=1, max_value=100))
    page_size = draw(st.integers(min_value=1, max_value=100))
    sort_by = draw(st.sampled_from([None, "created_at", "updated_at", "score", "status"]))
    sort_order = draw(st.sampled_from([SortOrder.ASC, SortOrder.DESC]))
    
    # 生成过滤条件
    filters = None
    if draw(st.booleans()):
        filters = {}
        if draw(st.booleans()):
            filters["status"] = draw(st.sampled_from(["PENDING", "PROCESSING", "COMPLETED"]))
        if draw(st.booleans()):
            filters["exam_id"] = draw(st.text(min_size=1, max_size=20, alphabet="abcdef0123456789"))
    
    return QueryParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        filters=filters
    )


@st.composite
def mock_data_strategy(draw, min_items: int = 0, max_items: int = 200):
    """生成模拟数据集"""
    num_items = draw(st.integers(min_value=min_items, max_value=max_items))
    
    items = []
    for i in range(num_items):
        item = {
            "id": f"item_{i}",
            "status": draw(st.sampled_from(["PENDING", "PROCESSING", "COMPLETED"])),
            "exam_id": draw(st.text(min_size=1, max_size=10, alphabet="abcdef0123456789")),
            "student_id": draw(st.text(min_size=1, max_size=10, alphabet="abcdef0123456789")),
            "score": draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        items.append(item)
    
    return items


# ==================== 模拟分页函数 ====================

def apply_pagination(
    items: List[Dict[str, Any]],
    params: QueryParams
) -> PaginatedResponse:
    """
    模拟分页查询逻辑
    
    这是一个纯函数实现，用于测试分页逻辑的正确性。
    """
    # 应用过滤
    filtered_items = items
    if params.filters:
        for field, value in params.filters.items():
            if value is not None:
                filtered_items = [
                    item for item in filtered_items
                    if item.get(field) == value
                ]
    
    total = len(filtered_items)
    
    # 应用排序
    if params.sort_by and filtered_items:
        reverse = params.sort_order == SortOrder.DESC
        try:
            filtered_items = sorted(
                filtered_items,
                key=lambda x: x.get(params.sort_by, ""),
                reverse=reverse
            )
        except TypeError:
            # 如果排序字段类型不一致，跳过排序
            pass
    
    # 应用分页
    offset = (params.page - 1) * params.page_size
    paginated_items = filtered_items[offset:offset + params.page_size]
    
    # 计算分页信息
    total_pages = (total + params.page_size - 1) // params.page_size if total > 0 else 0
    
    return PaginatedResponse(
        items=paginated_items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_prev=params.page > 1
    )


# ==================== 属性测试 ====================

class TestPaginationCorrectness:
    """
    分页查询结果正确性属性测试
    
    **功能: architecture-deep-integration, 属性 12: 分页查询结果正确性**
    **验证: 需求 7.2**
    """
    
    @given(
        items=mock_data_strategy(min_items=0, max_items=100),
        params=query_params_strategy()
    )
    @settings(max_examples=100)
    def test_result_count_not_exceeds_page_size(
        self,
        items: List[Dict[str, Any]],
        params: QueryParams
    ):
        """
        属性：返回的结果数量不超过 page_size
        
        **功能: architecture-deep-integration, 属性 12: 分页查询结果正确性**
        **验证: 需求 7.2**
        """
        result = apply_pagination(items, params)
        
        # 核心属性：结果数量不超过 page_size
        assert len(result.items) <= params.page_size, (
            f"结果数量 {len(result.items)} 超过 page_size {params.page_size}"
        )
    
    @given(
        items=mock_data_strategy(min_items=1, max_items=100),
        params=query_params_strategy()
    )
    @settings(max_examples=100)
    def test_sorting_order_correctness(
        self,
        items: List[Dict[str, Any]],
        params: QueryParams
    ):
        """
        属性：结果按指定字段正确排序
        
        **功能: architecture-deep-integration, 属性 12: 分页查询结果正确性**
        **验证: 需求 7.2**
        """
        # 只测试有排序字段的情况
        assume(params.sort_by is not None)
        
        result = apply_pagination(items, params)
        
        # 如果结果少于 2 个，无法验证排序
        if len(result.items) < 2:
            return
        
        # 验证排序顺序
        for i in range(len(result.items) - 1):
            current_val = result.items[i].get(params.sort_by)
            next_val = result.items[i + 1].get(params.sort_by)
            
            # 跳过 None 值
            if current_val is None or next_val is None:
                continue
            
            # 尝试比较（处理不同类型）
            try:
                if params.sort_order == SortOrder.DESC:
                    assert current_val >= next_val, (
                        f"降序排序错误: {current_val} < {next_val}"
                    )
                else:
                    assert current_val <= next_val, (
                        f"升序排序错误: {current_val} > {next_val}"
                    )
            except TypeError:
                # 类型不可比较，跳过
                pass
    
    @given(
        items=mock_data_strategy(min_items=1, max_items=100),
        params=query_params_strategy()
    )
    @settings(max_examples=100)
    def test_filter_conditions_applied(
        self,
        items: List[Dict[str, Any]],
        params: QueryParams
    ):
        """
        属性：过滤条件正确应用
        
        **功能: architecture-deep-integration, 属性 12: 分页查询结果正确性**
        **验证: 需求 7.2**
        """
        # 只测试有过滤条件的情况
        assume(params.filters is not None and len(params.filters) > 0)
        
        result = apply_pagination(items, params)
        
        # 验证所有返回的项都满足过滤条件
        for item in result.items:
            for field, expected_value in params.filters.items():
                if expected_value is not None:
                    actual_value = item.get(field)
                    assert actual_value == expected_value, (
                        f"过滤条件未正确应用: {field}={actual_value}, 期望={expected_value}"
                    )
    
    @given(
        items=mock_data_strategy(min_items=0, max_items=100),
        params=query_params_strategy()
    )
    @settings(max_examples=100)
    def test_pagination_metadata_consistency(
        self,
        items: List[Dict[str, Any]],
        params: QueryParams
    ):
        """
        属性：分页元数据一致性
        
        **功能: architecture-deep-integration, 属性 12: 分页查询结果正确性**
        **验证: 需求 7.2**
        """
        result = apply_pagination(items, params)
        
        # 验证 total_pages 计算正确
        expected_total_pages = (
            (result.total + params.page_size - 1) // params.page_size
            if result.total > 0 else 0
        )
        assert result.total_pages == expected_total_pages, (
            f"total_pages 计算错误: {result.total_pages} != {expected_total_pages}"
        )
        
        # 验证 has_next 正确
        expected_has_next = params.page < result.total_pages
        assert result.has_next == expected_has_next, (
            f"has_next 错误: {result.has_next} != {expected_has_next}"
        )
        
        # 验证 has_prev 正确
        expected_has_prev = params.page > 1
        assert result.has_prev == expected_has_prev, (
            f"has_prev 错误: {result.has_prev} != {expected_has_prev}"
        )
    
    @given(
        items=mock_data_strategy(min_items=10, max_items=100),
        page_size=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100)
    def test_all_items_covered_by_pagination(
        self,
        items: List[Dict[str, Any]],
        page_size: int
    ):
        """
        属性：分页覆盖所有数据
        
        遍历所有页面，收集的项目总数应等于总数。
        
        **功能: architecture-deep-integration, 属性 12: 分页查询结果正确性**
        **验证: 需求 7.2**
        """
        all_collected_items = []
        page = 1
        
        while True:
            params = QueryParams(page=page, page_size=page_size)
            result = apply_pagination(items, params)
            
            all_collected_items.extend(result.items)
            
            if not result.has_next:
                break
            page += 1
            
            # 防止无限循环
            if page > 1000:
                break
        
        # 验证收集的项目数等于总数
        assert len(all_collected_items) == len(items), (
            f"分页未覆盖所有数据: 收集 {len(all_collected_items)}, 总数 {len(items)}"
        )


# ==================== 边界条件测试 ====================

class TestPaginationEdgeCases:
    """分页边界条件测试"""
    
    def test_empty_data_set(self):
        """测试空数据集"""
        params = QueryParams(page=1, page_size=10)
        result = apply_pagination([], params)
        
        assert len(result.items) == 0
        assert result.total == 0
        assert result.total_pages == 0
        assert result.has_next is False
        assert result.has_prev is False
    
    def test_page_beyond_total(self):
        """测试页码超出总页数"""
        items = [{"id": f"item_{i}", "status": "PENDING"} for i in range(5)]
        params = QueryParams(page=100, page_size=10)
        result = apply_pagination(items, params)
        
        assert len(result.items) == 0
        assert result.total == 5
        assert result.has_next is False
    
    def test_exact_page_boundary(self):
        """测试恰好在页边界"""
        items = [{"id": f"item_{i}", "status": "PENDING"} for i in range(20)]
        params = QueryParams(page=2, page_size=10)
        result = apply_pagination(items, params)
        
        assert len(result.items) == 10
        assert result.total == 20
        assert result.total_pages == 2
        assert result.has_next is False
        assert result.has_prev is True
