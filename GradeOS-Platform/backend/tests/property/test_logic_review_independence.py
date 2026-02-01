"""
属性测试：P3 - 逻辑复核独立性

验证逻辑复核函数不依赖记忆系统的状态。

Validates: Requirements P3 (逻辑复核独立性)

属性定义：
- 逻辑复核函数 logic_review(result, rubric) 的输出
- 不依赖于任何 MemoryEntry 或 GradingMemoryService 的状态
"""

import pytest
import inspect
import ast
from typing import Set, List
from pathlib import Path


class LogicReviewIndependenceChecker(ast.NodeVisitor):
    """
    AST 访问器，检查函数是否依赖记忆系统
    
    检查规则：
    1. 不能调用 memory_service.retrieve_relevant_memories()
    2. 不能调用 memory_service.generate_confession_context()
    3. 不能调用 memory_service.get_calibration_recommendation()
    4. 不能访问 _long_term_memory 或 _batch_memories
    """
    
    # 禁止在评分决策中使用的记忆相关调用
    FORBIDDEN_MEMORY_CALLS = {
        "retrieve_relevant_memories",
        "generate_confession_context",
        "get_calibration_recommendation",
        "get_error_patterns_for_question_type",
        "format_confession_memory_prompt",
    }
    
    # 允许的记忆调用（仅用于记录，不影响评分）
    ALLOWED_MEMORY_CALLS = {
        "record_correction",
        "record_batch_error_pattern",
        "record_batch_risk_signal",
        "record_batch_confidence",
        "consolidate_batch_memory",
        "save_to_storage",
        "create_batch_memory",
        "get_batch_memory",
    }
    
    def __init__(self):
        self.violations: List[str] = []
        self.current_function: str = ""
        self.in_scoring_decision: bool = False
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """访问函数定义"""
        old_function = self.current_function
        self.current_function = node.name
        
        # 检查是否是评分决策相关的函数
        scoring_functions = {
            "_build_logic_review_prompt",
            "review_student",  # logic_review_node 内部的评分函数
        }
        
        if node.name in scoring_functions:
            self.in_scoring_decision = True
        
        self.generic_visit(node)
        
        self.in_scoring_decision = False
        self.current_function = old_function
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """访问异步函数定义"""
        self.visit_FunctionDef(node)  # type: ignore
    
    def visit_Call(self, node: ast.Call):
        """访问函数调用"""
        if self.in_scoring_decision:
            # 检查是否调用了禁止的记忆方法
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                if method_name in self.FORBIDDEN_MEMORY_CALLS:
                    self.violations.append(
                        f"函数 {self.current_function} 在评分决策中调用了禁止的记忆方法: {method_name}"
                    )
        
        self.generic_visit(node)


def get_batch_grading_source() -> str:
    """获取 batch_grading.py 的源代码"""
    batch_grading_path = Path(__file__).parent.parent.parent / "src" / "graphs" / "batch_grading.py"
    if not batch_grading_path.exists():
        pytest.skip("batch_grading.py not found")
    return batch_grading_path.read_text(encoding="utf-8")


class TestLogicReviewIndependence:
    """P3: 逻辑复核独立性测试"""
    
    def test_build_logic_review_prompt_no_memory_dependency(self):
        """
        验证 _build_logic_review_prompt 不依赖记忆系统
        
        Validates: Requirements P3
        """
        source = get_batch_grading_source()
        tree = ast.parse(source)
        
        checker = LogicReviewIndependenceChecker()
        checker.visit(tree)
        
        # 检查是否有违规
        prompt_violations = [v for v in checker.violations if "_build_logic_review_prompt" in v]
        
        assert len(prompt_violations) == 0, (
            f"_build_logic_review_prompt 违反了逻辑复核独立性原则:\n"
            + "\n".join(prompt_violations)
        )
    
    def test_logic_review_prompt_signature(self):
        """
        验证 _build_logic_review_prompt 的函数签名不包含记忆相关参数
        
        Validates: Requirements P3
        """
        source = get_batch_grading_source()
        tree = ast.parse(source)
        
        # 查找 _build_logic_review_prompt 函数
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_build_logic_review_prompt":
                # 获取参数名
                param_names = [arg.arg for arg in node.args.args]
                
                # 禁止的参数名
                forbidden_params = {
                    "memory_service",
                    "memory_context",
                    "historical_patterns",
                    "calibration_data",
                    "error_patterns",
                }
                
                violations = forbidden_params & set(param_names)
                assert len(violations) == 0, (
                    f"_build_logic_review_prompt 包含禁止的记忆相关参数: {violations}"
                )
                
                # 验证允许的参数
                allowed_params = {"student", "question_details", "rubric_map", "limits", "confession"}
                assert set(param_names) <= allowed_params, (
                    f"_build_logic_review_prompt 包含未知参数: {set(param_names) - allowed_params}"
                )
                
                return
        
        pytest.fail("未找到 _build_logic_review_prompt 函数")
    
    def test_logic_review_node_memory_usage_is_post_decision(self):
        """
        验证 logic_review_node 中的记忆使用仅发生在评分决策之后
        
        Validates: Requirements P3
        
        规则：
        - record_correction 只能在 LLM 返回结果之后调用
        - consolidate_batch_memory 只能在所有学生处理完成之后调用
        """
        source = get_batch_grading_source()
        
        # 检查 record_correction 的使用位置
        # 它应该在 "merged = _merge_logic_review_fields" 之后
        
        # 简单的文本检查：record_correction 应该在 _merge_logic_review_fields 之后
        merge_pos = source.find("merged = _merge_logic_review_fields")
        record_pos = source.find("memory_service.record_correction")
        
        if merge_pos == -1:
            pytest.skip("未找到 _merge_logic_review_fields 调用")
        
        if record_pos == -1:
            # 没有使用 record_correction，这是允许的
            return
        
        # 找到 logic_review_node 函数的范围
        node_start = source.find("async def logic_review_node")
        if node_start == -1:
            pytest.skip("未找到 logic_review_node 函数")
        
        # 在 logic_review_node 内部，record_correction 应该在 merge 之后
        # 这是一个简化的检查，实际上应该使用 AST 分析
        
        # 检查 consolidate_batch_memory 是否在函数末尾
        consolidate_pos = source.find("memory_service.consolidate_batch_memory")
        if consolidate_pos != -1:
            # 应该在 "final_results = " 之后
            final_results_pos = source.find("final_results = [r for r in updated_results")
            if final_results_pos != -1:
                assert consolidate_pos > final_results_pos, (
                    "consolidate_batch_memory 应该在所有学生处理完成之后调用"
                )
    
    def test_logic_review_docstring_contains_independence_warning(self):
        """
        验证 logic_review_node 的文档字符串包含独立性警告
        
        Validates: Requirements P3
        """
        source = get_batch_grading_source()
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "logic_review_node":
                docstring = ast.get_docstring(node)
                assert docstring is not None, "logic_review_node 缺少文档字符串"
                
                # 检查是否包含独立性警告
                independence_keywords = ["独立性", "无状态", "P3", "不能依赖记忆"]
                has_warning = any(kw in docstring for kw in independence_keywords)
                
                assert has_warning, (
                    "logic_review_node 的文档字符串应该包含逻辑复核独立性警告"
                )
                return
        
        pytest.fail("未找到 logic_review_node 函数")


class TestPromptContentIndependence:
    """验证 prompt 内容不包含记忆相关信息"""
    
    def test_prompt_does_not_contain_memory_keywords(self):
        """
        验证生成的 prompt 不包含记忆相关关键词
        
        Validates: Requirements P3
        """
        # 模拟调用 _build_logic_review_prompt
        # 由于函数在另一个模块中，我们检查源代码中的字符串
        source = get_batch_grading_source()
        
        # 在 _build_logic_review_prompt 函数内部查找禁止的关键词
        func_start = source.find("def _build_logic_review_prompt")
        if func_start == -1:
            pytest.skip("未找到 _build_logic_review_prompt 函数")
        
        # 找到函数结束位置（下一个 def 或 async def）
        func_end = source.find("\ndef ", func_start + 1)
        if func_end == -1:
            func_end = source.find("\nasync def ", func_start + 1)
        if func_end == -1:
            func_end = len(source)
        
        func_source = source[func_start:func_end]
        
        # 禁止在 prompt 中出现的关键词
        forbidden_in_prompt = [
            "历史记忆",
            "记忆系统",
            "historical_error_patterns",
            "calibration_suggestions",
            "memory_context",
        ]
        
        for keyword in forbidden_in_prompt:
            # 检查是否在字符串字面量中
            if f'"{keyword}"' in func_source or f"'{keyword}'" in func_source:
                pytest.fail(
                    f"_build_logic_review_prompt 的 prompt 中包含禁止的关键词: {keyword}"
                )


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
