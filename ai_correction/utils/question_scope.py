#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
题号范围解析工具
支持逗号与区间组合输入，自动去重、排序并返回统一格式
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from typing import List


class QuestionScopeError(ValueError):
    """题号范围解析异常"""


@dataclass
class QuestionScopeResult:
    """题号范围解析结果"""

    raw_input: str
    question_ids: List[str] = field(default_factory=list)
    normalized_expression: str = ""
    warnings: List[str] = field(default_factory=list)


_RANGE_TOKEN_PATTERN = re.compile(
    r"^(?P<start>(?:Q|q)?\d+)\s*[-~–－至到]+\s*(?P<end>(?:Q|q)?\d+)$"
)
_SINGLE_TOKEN_PATTERN = re.compile(r"^(?:Q|q)?\d+$")
_NON_DIGIT_PATTERN = re.compile(r"[^\dQq,\-\s~–－至到]")


def parse_question_scope(scope_str: str) -> QuestionScopeResult:
    """
    解析题号范围字符串，返回题号列表

    支持输入示例:
        "3,5-8,12"
        "Q1,Q2,Q5-Q8"
        "1-5, 7 , 10"
    """

    raw_input = scope_str or ""
    cleaned_input = _normalize_delimiters(raw_input.strip())

    if not cleaned_input:
        return QuestionScopeResult(
            raw_input=raw_input,
            question_ids=[],
            normalized_expression="",
            warnings=[]
        )

    invalid_chars = _NON_DIGIT_PATTERN.findall(cleaned_input)
    if invalid_chars:
        unique_chars = sorted(set(invalid_chars))
        raise QuestionScopeError(f"检测到非法字符: {' '.join(unique_chars)}")

    tokens = [token.strip() for token in cleaned_input.split(',')]
    tokens = [token for token in tokens if token]

    if not tokens:
        raise QuestionScopeError("请输入有效的题号范围，如 3,5-8")

    question_numbers: List[int] = []
    seen_numbers = set()
    warnings: List[str] = []

    for token in tokens:
        if _RANGE_TOKEN_PATTERN.match(token):
            _expand_range_token(token, question_numbers, seen_numbers)
        elif _SINGLE_TOKEN_PATTERN.match(token):
            number = int(_strip_prefix(token))
            if number < 1:
                raise QuestionScopeError("题号必须大于等于1")
            if number in seen_numbers:
                warnings.append(f"检测到重复题号: Q{number}")
            else:
                seen_numbers.add(number)
                question_numbers.append(number)
        else:
            raise QuestionScopeError(f"无法解析的题号表达式: {token}")

    if not question_numbers:
        raise QuestionScopeError("未能解析出任何题号，请检查输入格式")

    # 去重保持顺序
    ordered_unique = []
    seen_in_order = set()
    for num in question_numbers:
        if num not in seen_in_order:
            seen_in_order.add(num)
            ordered_unique.append(num)

    normalized_expression = ",".join(f"Q{num}" for num in ordered_unique)

    return QuestionScopeResult(
        raw_input=raw_input,
        question_ids=[f"Q{num}" for num in ordered_unique],
        normalized_expression=normalized_expression,
        warnings=warnings
    )


def _normalize_delimiters(value: str) -> str:
    """统一中英文分隔符"""
    translation_table = str.maketrans(
        {
            "，": ",",
            "、": ",",
            "；": ",",
            ";": ",",
            "—": "-",
            "－": "-",
            "–": "-",
            "～": "-",
            "至": "-",
            "到": "-",
        }
    )
    return value.translate(translation_table)


def _strip_prefix(token: str) -> str:
    """去除题号前缀Q"""
    return token.lstrip("Qq")


def _expand_range_token(
    token: str,
    bucket: List[int],
    seen_numbers: set
) -> None:
    """展开区间表达式"""
    match = _RANGE_TOKEN_PATTERN.match(token)
    if not match:
        raise QuestionScopeError(f"无法解析的区间: {token}")

    start_val = int(_strip_prefix(match.group("start")))
    end_val = int(_strip_prefix(match.group("end")))

    if start_val < 1 or end_val < 1:
        raise QuestionScopeError("题号必须大于等于1")
    if end_val < start_val:
        raise QuestionScopeError(f"区间起止顺序错误: {token}")
    if end_val - start_val > 500:
        raise QuestionScopeError("单个区间跨度过大，请分段输入")

    for number in range(start_val, end_val + 1):
        if number in seen_numbers:
            continue
        seen_numbers.add(number)
        bucket.append(number)


def format_question_list(question_ids: List[str]) -> str:
    """将题号列表格式化为人类可读字符串"""
    if not question_ids:
        return "全部题目"
    return "、".join(question_ids[:10]) + ("..." if len(question_ids) > 10 else "")





