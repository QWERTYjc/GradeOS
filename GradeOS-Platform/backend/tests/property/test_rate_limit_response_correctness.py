"""
限流响应正确性属性测试

**功能: architecture-deep-integration, 属性 14: 限流响应正确性**
**验证: 需求 7.5**
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import Dict, Any

from src.services.enhanced_api import EnhancedAPIService


@st.composite
def rate_limit_params_strategy(draw):
    retry_after = draw(st.integers(min_value=1, max_value=3600))
    limit = draw(st.integers(min_value=1, max_value=10000))
    window_seconds = draw(st.integers(min_value=1, max_value=3600))
    remaining = draw(st.integers(min_value=0, max_value=limit))
    return {
        "retry_after": retry_after,
        "limit": limit,
        "window_seconds": window_seconds,
        "remaining": remaining,
    }


class TestRateLimitResponseCorrectness:
    @given(params=rate_limit_params_strategy())
    @settings(max_examples=100)
    def test_rate_limit_response_structure(self, params: Dict[str, Any]):
        response = EnhancedAPIService.create_rate_limit_response(
            retry_after=params["retry_after"],
            limit=params["limit"],
            window_seconds=params["window_seconds"]
        )
        assert "error" in response
        assert "retry_after" in response
        assert response["retry_after"] > 0
    
    @given(params=rate_limit_params_strategy())
    @settings(max_examples=100)
    def test_retry_after_header_is_string(self, params: Dict[str, Any]):
        headers = EnhancedAPIService.get_rate_limit_headers(
            retry_after=params["retry_after"],
            limit=params["limit"],
            remaining=params["remaining"]
        )
        assert "Retry-After" in headers
        assert isinstance(headers["Retry-After"], str)
        assert int(headers["Retry-After"]) > 0
