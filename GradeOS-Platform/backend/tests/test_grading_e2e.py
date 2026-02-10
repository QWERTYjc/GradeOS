"""
End-to-end grading tests.

This project has optional E2E tests that require:
- External LLM credentials
- Network access
- Non-deterministic model outputs

They are disabled by default to keep CI and local unit test runs stable.
"""

import pytest


pytest.skip("E2E tests disabled by default (requires external LLM + assets).", allow_module_level=True)

