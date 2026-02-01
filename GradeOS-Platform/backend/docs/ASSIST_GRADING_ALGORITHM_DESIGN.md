# 辅助批改系统 - 核心算法设计文档

**版本**: 1.0  
**日期**: 2026-01-28  
**技术栈**: Google Gemini 3.0 Flash + LangGraph + Python 3.11+

---

## 目录

1. [系统概述](#系统概述)
2. [算法1: 作业深度理解算法](#算法1-作业深度理解算法)
3. [算法2: 智能纠错算法](#算法2-智能纠错算法)
4. [算法3: 分析报告生成算法](#算法3-分析报告生成算法)
5. [性能优化方案](#性能优化方案)
6. [Prompt 工程](#prompt-工程)
7. [实现建议](#实现建议)

---

## 系统概述

### 设计目标

在**无标准答案**的场景下，通过 LLM 的深度理解和推理能力：
1. 理解作业的知识点、解题思路、逻辑链条
2. 发现计算错误、逻辑错误、概念错误、表达错误
3. 生成高质量的分析报告，为教师提供可操作的建议

### 核心约束

- **性能约束**: 不能拖慢主批改系统，可以比主批改慢，但要有合理的性能预期
- **成本约束**: 优化 LLM 调用次数和 token 使用
- **质量约束**: 避免废话，提供建设性的、可操作的分析

### 技术优势

利用 **Google Gemini 3.0 Flash** 的能力：
- **长上下文**: 支持 1M+ tokens，可以一次性处理多页作业
- **多模态**: 直接分析图像，无需 OCR
- **推理能力**: 深度理解数学、物理、化学等学科逻辑
- **结构化输出**: 支持 JSON 格式输出，便于解析

---

## 算法1: 作业深度理解算法

### 1.1 算法目标

在无标准答案的情况下，理解作业内容：
- 识别涉及的知识点
- 分析解题思路和逻辑链条
- 评估学生的理解程度
- 处理多种题型（选择、填空、计算、证明、开放题）

### 1.2 算法流程

```
输入: 作业图像列表 [image1, image2, ...]
输出: 深度理解结果 UnderstandingResult

算法: DeepUnderstandingAlgorithm
┌─────────────────────────────────────────┐
│ 1. 粗读阶段 (Coarse Reading)             │
│    - 识别题目类型和数量                   │
│    - 提取题目主题和关键词                 │
│    - 评估作业整体难度                     │
│    时间复杂度: O(1) - 单次 LLM 调用       │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 2. 精读阶段 (Fine Reading)               │
│    - 逐题分析解题步骤                     │
│    - 识别使用的公式、定理、方法           │
│    - 提取关键推理步骤                     │
│    时间复杂度: O(n) - n 为题目数量        │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 3. 推理验证阶段 (Reasoning Verification) │
│    - 验证解题逻辑的严密性                 │
│    - 检查推理链条的完整性                 │
│    - 识别概念应用是否正确                 │
│    时间复杂度: O(n * k) - k 为平均步骤数  │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 4. 知识点映射 (Knowledge Mapping)        │
│    - 映射到知识图谱（可选）               │
│    - 标注理解程度                         │
│    - 识别薄弱环节                         │
│    时间复杂度: O(n) - 基于规则映射        │
└─────────────────────────────────────────┘
```

### 1.3 关键数据结构

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

class QuestionType(Enum):
    """题目类型"""
    MULTIPLE_CHOICE = "multiple_choice"      # 选择题
    FILL_IN_BLANK = "fill_in_blank"         # 填空题
    CALCULATION = "calculation"              # 计算题
    PROOF = "proof"                          # 证明题
    OPEN_ENDED = "open_ended"                # 开放题
    ANALYSIS = "analysis"                    # 分析题

class UnderstandingLevel(Enum):
    """理解程度"""
    EXCELLENT = "excellent"      # 优秀 (90-100%)
    GOOD = "good"                # 良好 (75-89%)
    FAIR = "fair"                # 及格 (60-74%)
    POOR = "poor"                # 不及格 (<60%)

@dataclass
class KnowledgePoint:
    """知识点"""
    id: str                              # 知识点 ID
    name: str                            # 知识点名称
    category: str                        # 分类（如 "线性代数", "微积分"）
    confidence: float                    # 识别置信度 (0.0-1.0)
    applied_correctly: bool              # 是否正确应用
    description: Optional[str] = None    # 描述

@dataclass
class ReasoningStep:
    """推理步骤"""
    step_index: int                      # 步骤编号
    description: str                     # 步骤描述
    formula_used: Optional[str] = None   # 使用的公式
    is_correct: bool = True              # 是否正确
    error_type: Optional[str] = None     # 错误类型（如果有）
    suggestion: Optional[str] = None     # 改进建议

@dataclass
class QuestionUnderstanding:
    """单题理解结果"""
    question_id: str                     # 题目 ID
    question_type: QuestionType          # 题目类型
    page_indices: List[int]              # 页面索引
    
    # 题目内容
    question_text: str                   # 题目文本（OCR 提取）
    student_answer: str                  # 学生答案
    
    # 知识点分析
    knowledge_points: List[KnowledgePoint]  # 涉及的知识点
    
    # 解题过程分析
    reasoning_steps: List[ReasoningStep]    # 推理步骤
    logic_chain_complete: bool              # 逻辑链条是否完整
    
    # 理解程度评估
    understanding_level: UnderstandingLevel  # 理解程度
    understanding_score: float               # 理解得分 (0.0-1.0)
    
    # 优缺点
    strengths: List[str]                 # 优点
    weaknesses: List[str]                # 不足
    
    # 元数据
    confidence: float = 0.8              # 分析置信度
    processing_time_ms: float = 0.0      # 处理时间

@dataclass
class UnderstandingResult:
    """整体理解结果"""
    batch_id: str                        # 批次 ID
    total_questions: int                 # 题目总数
    
    # 逐题分析
    question_understandings: List[QuestionUnderstanding]
    
    # 整体评估
    overall_level: UnderstandingLevel    # 整体理解程度
    overall_score: float                 # 整体得分 (0.0-1.0)
    
    # 知识点统计
    knowledge_coverage: Dict[str, int]   # 知识点覆盖度
    weak_areas: List[str]                # 薄弱领域
    
    # 元数据
    total_processing_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
```

### 1.4 算法伪代码

```python
async def deep_understanding_algorithm(
    images: List[str],
    api_key: str,
    config: UnderstandingConfig
) -> UnderstandingResult:
    """
    作业深度理解算法
    
    时间复杂度: O(n) - n 为题目数量，主要是 LLM 调用
    空间复杂度: O(n * k) - k 为平均步骤数
    """
    
    # ===== 阶段 1: 粗读 =====
    # 一次性处理所有图像，利用 Gemini 的长上下文能力
    coarse_result = await llm_call(
        prompt=COARSE_READING_PROMPT,
        images=images,
        response_format="json"
    )
    # 提取: 题目类型、数量、主题、难度
    
    # ===== 阶段 2: 精读（逐题） =====
    question_understandings = []
    
    # 批量处理：将题目分组，每组 3-5 题一起调用 LLM
    question_groups = group_questions(coarse_result.questions, group_size=3)
    
    for group in question_groups:
        # 批量精读
        fine_results = await llm_call(
            prompt=FINE_READING_PROMPT,
            images=extract_relevant_images(images, group),
            context=coarse_result,
            response_format="json"
        )
        
        for question_result in fine_results:
            # 提取: 解题步骤、公式、推理链条
            question_understandings.append(question_result)
    
    # ===== 阶段 3: 推理验证 =====
    # 对复杂题目（计算题、证明题）进行推理验证
    complex_questions = filter_complex_questions(question_understandings)
    
    for question in complex_questions:
        verification_result = await llm_call(
            prompt=REASONING_VERIFICATION_PROMPT,
            images=question.images,
            context={
                "question": question,
                "reasoning_steps": question.reasoning_steps
            },
            response_format="json"
        )
        
        # 更新推理步骤的正确性标记
        update_reasoning_correctness(question, verification_result)
    
    # ===== 阶段 4: 知识点映射 =====
    # 基于规则或知识图谱映射知识点
    for question in question_understandings:
        question.knowledge_points = map_knowledge_points(
            question.question_text,
            question.reasoning_steps
        )
    
    # ===== 汇总结果 =====
    return UnderstandingResult(
        batch_id=batch_id,
        total_questions=len(question_understandings),
        question_understandings=question_understandings,
        overall_level=calculate_overall_level(question_understandings),
        overall_score=calculate_overall_score(question_understandings),
        knowledge_coverage=calculate_knowledge_coverage(question_understandings),
        weak_areas=identify_weak_areas(question_understandings)
    )
```

### 1.5 复杂度分析

| 操作 | 时间复杂度 | 空间复杂度 | 说明 |
|------|-----------|-----------|------|
| 粗读阶段 | O(1) | O(n) | 单次 LLM 调用，处理所有图像 |
| 精读阶段 | O(n/g) | O(n*k) | n 题目数，g 分组大小，k 平均步骤数 |
| 推理验证 | O(m) | O(m*k) | m 为复杂题目数 (m << n) |
| 知识点映射 | O(n) | O(n*p) | p 为平均知识点数 |
| **总计** | **O(n)** | **O(n*k)** | 线性复杂度，可并行优化 |

---

## 算法2: 智能纠错算法

### 2.1 算法目标

在无标准答案的情况下，发现作业中的各类错误：
- **计算错误**: 数值计算、公式应用错误
- **逻辑错误**: 推理不严密、前后矛盾
- **概念错误**: 概念理解偏差、公式误用
- **表达错误**: 表述不清、符号错误

### 2.2 算法流程

```
输入: UnderstandingResult (深度理解结果)
输出: ErrorDetectionResult (纠错结果)

算法: IntelligentErrorDetection
┌─────────────────────────────────────────┐
│ 1. 多维度错误扫描 (Multi-Dimension Scan) │
│    - 计算错误扫描                         │
│    - 逻辑错误扫描                         │
│    - 概念错误扫描                         │
│    - 表达错误扫描                         │
│    并行执行: 4 个维度同时扫描              │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 2. 交叉验证 (Cross Validation)          │
│    - 不同维度的错误可能关联               │
│    - 避免重复报告同一问题                 │
│    - 识别根本原因                         │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 3. 错误分级 (Error Prioritization)       │
│    - 严重错误 (影响答案正确性)            │
│    - 中等错误 (部分影响)                  │
│    - 轻微错误 (表述问题)                  │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 4. 建议生成 (Suggestion Generation)      │
│    - 针对每个错误生成改进建议             │
│    - 避免只指出问题，必须给出方案         │
└─────────────────────────────────────────┘
```

### 2.3 关键数据结构

```python
from enum import Enum

class ErrorType(Enum):
    """错误类型"""
    CALCULATION = "calculation"      # 计算错误
    LOGIC = "logic"                  # 逻辑错误
    CONCEPT = "concept"              # 概念错误
    EXPRESSION = "expression"        # 表达错误

class ErrorSeverity(Enum):
    """错误严重程度"""
    CRITICAL = "critical"    # 严重 (导致答案完全错误)
    MAJOR = "major"          # 中等 (部分影响答案)
    MINOR = "minor"          # 轻微 (不影响答案，仅表述问题)

@dataclass
class ErrorInstance:
    """单个错误实例"""
    error_id: str                    # 错误 ID
    error_type: ErrorType            # 错误类型
    severity: ErrorSeverity          # 严重程度
    
    # 位置信息
    question_id: str                 # 所在题目
    step_index: Optional[int] = None # 所在步骤（如果适用）
    page_index: Optional[int] = None # 所在页面
    
    # 错误描述
    description: str                 # 错误描述
    incorrect_content: str           # 错误内容
    correct_content: Optional[str] = None  # 正确内容（如果能确定）
    
    # 建议
    suggestion: str                  # 改进建议（必须有！）
    explanation: Optional[str] = None  # 解释为什么错误
    
    # 元数据
    confidence: float = 0.8          # 检测置信度
    is_confirmed: bool = False       # 是否已确认（用于人工复核）

@dataclass
class ErrorDetectionResult:
    """纠错结果"""
    batch_id: str
    question_id: str
    
    # 错误列表（按严重程度排序）
    errors: List[ErrorInstance]
    
    # 统计信息
    total_errors: int
    errors_by_type: Dict[ErrorType, int]
    errors_by_severity: Dict[ErrorSeverity, int]
    
    # 整体评估
    has_critical_errors: bool        # 是否有严重错误
    overall_quality_score: float     # 整体质量得分 (0.0-1.0)
    
    # 元数据
    processing_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
```

### 2.4 算法伪代码

```python
async def intelligent_error_detection(
    understanding_result: UnderstandingResult,
    images: List[str],
    api_key: str,
    config: ErrorDetectionConfig
) -> List[ErrorDetectionResult]:
    """
    智能纠错算法
    
    时间复杂度: O(n * 4) = O(n) - n 为题目数，4 为错误维度数
    空间复杂度: O(n * e) - e 为平均错误数
    """
    
    results = []
    
    for question in understanding_result.question_understandings:
        errors = []
        
        # ===== 并行执行 4 个维度的错误扫描 =====
        scan_tasks = [
            scan_calculation_errors(question, images),
            scan_logic_errors(question, images),
            scan_concept_errors(question, images),
            scan_expression_errors(question, images)
        ]
        
        scan_results = await asyncio.gather(*scan_tasks)
        
        # 合并结果
        for scan_result in scan_results:
            errors.extend(scan_result.errors)
        
        # ===== 交叉验证：去重和关联 =====
        errors = cross_validate_errors(errors)
        
        # ===== 错误分级 =====
        errors = prioritize_errors(errors)
        
        # ===== 建议生成（对于没有建议的错误） =====
        for error in errors:
            if not error.suggestion:
                error.suggestion = await generate_suggestion(
                    error, question, images
                )
        
        # ===== 构建结果 =====
        result = ErrorDetectionResult(
            batch_id=understanding_result.batch_id,
            question_id=question.question_id,
            errors=errors,
            total_errors=len(errors),
            errors_by_type=count_by_type(errors),
            errors_by_severity=count_by_severity(errors),
            has_critical_errors=any(
                e.severity == ErrorSeverity.CRITICAL for e in errors
            ),
            overall_quality_score=calculate_quality_score(errors)
        )
        
        results.append(result)
    
    return results


async def scan_calculation_errors(
    question: QuestionUnderstanding,
    images: List[str]
) -> ErrorScanResult:
    """扫描计算错误"""
    
    # 只对计算题、填空题进行计算验证
    if question.question_type not in [
        QuestionType.CALCULATION,
        QuestionType.FILL_IN_BLANK
    ]:
        return ErrorScanResult(errors=[])
    
    # 调用 LLM 进行计算验证
    result = await llm_call(
        prompt=CALCULATION_VERIFICATION_PROMPT,
        images=extract_relevant_images(images, question),
        context={
            "question": question.question_text,
            "student_answer": question.student_answer,
            "reasoning_steps": question.reasoning_steps
        },
        response_format="json"
    )
    
    # 构建错误实例
    errors = []
    for calc_error in result.get("errors", []):
        errors.append(ErrorInstance(
            error_id=generate_error_id(),
            error_type=ErrorType.CALCULATION,
            severity=ErrorSeverity.CRITICAL,
            question_id=question.question_id,
            step_index=calc_error.get("step_index"),
            description=calc_error["description"],
            incorrect_content=calc_error["incorrect"],
            correct_content=calc_error.get("correct"),
            suggestion=calc_error["suggestion"],
            confidence=calc_error.get("confidence", 0.8)
        ))
    
    return ErrorScanResult(errors=errors)


async def scan_logic_errors(
    question: QuestionUnderstanding,
    images: List[str]
) -> ErrorScanResult:
    """扫描逻辑错误"""
    
    # 对证明题、分析题、开放题进行逻辑检查
    if question.question_type not in [
        QuestionType.PROOF,
        QuestionType.ANALYSIS,
        QuestionType.OPEN_ENDED
    ]:
        return ErrorScanResult(errors=[])
    
    # 调用 LLM 进行逻辑验证
    result = await llm_call(
        prompt=LOGIC_VERIFICATION_PROMPT,
        images=extract_relevant_images(images, question),
        context={
            "question": question.question_text,
            "reasoning_steps": question.reasoning_steps,
            "logic_chain_complete": question.logic_chain_complete
        },
        response_format="json"
    )
    
    # 构建错误实例（逻辑错误通常是 MAJOR 级别）
    errors = []
    for logic_error in result.get("errors", []):
        severity = (
            ErrorSeverity.CRITICAL
            if logic_error.get("breaks_conclusion")
            else ErrorSeverity.MAJOR
        )
        
        errors.append(ErrorInstance(
            error_id=generate_error_id(),
            error_type=ErrorType.LOGIC,
            severity=severity,
            question_id=question.question_id,
            step_index=logic_error.get("step_index"),
            description=logic_error["description"],
            incorrect_content=logic_error["problematic_reasoning"],
            suggestion=logic_error["suggestion"],
            explanation=logic_error.get("explanation"),
            confidence=logic_error.get("confidence", 0.7)
        ))
    
    return ErrorScanResult(errors=errors)


async def scan_concept_errors(
    question: QuestionUnderstanding,
    images: List[str]
) -> ErrorScanResult:
    """扫描概念错误"""
    
    # 基于知识点分析检查概念应用
    concept_errors = []
    
    for kp in question.knowledge_points:
        if not kp.applied_correctly:
            # 调用 LLM 分析概念错误
            result = await llm_call(
                prompt=CONCEPT_VERIFICATION_PROMPT,
                images=extract_relevant_images(images, question),
                context={
                    "knowledge_point": kp,
                    "student_answer": question.student_answer
                },
                response_format="json"
            )
            
            if result.get("has_error"):
                concept_errors.append(ErrorInstance(
                    error_id=generate_error_id(),
                    error_type=ErrorType.CONCEPT,
                    severity=ErrorSeverity.MAJOR,
                    question_id=question.question_id,
                    description=result["description"],
                    incorrect_content=result["misapplied_concept"],
                    correct_content=result.get("correct_application"),
                    suggestion=result["suggestion"],
                    explanation=result.get("explanation"),
                    confidence=result.get("confidence", 0.75)
                ))
    
    return ErrorScanResult(errors=concept_errors)


async def scan_expression_errors(
    question: QuestionUnderstanding,
    images: List[str]
) -> ErrorScanResult:
    """扫描表达错误"""
    
    # 调用 LLM 检查表述问题
    result = await llm_call(
        prompt=EXPRESSION_CHECK_PROMPT,
        images=extract_relevant_images(images, question),
        context={
            "student_answer": question.student_answer
        },
        response_format="json"
    )
    
    # 表达错误通常是 MINOR 级别
    errors = []
    for expr_error in result.get("errors", []):
        errors.append(ErrorInstance(
            error_id=generate_error_id(),
            error_type=ErrorType.EXPRESSION,
            severity=ErrorSeverity.MINOR,
            question_id=question.question_id,
            description=expr_error["description"],
            incorrect_content=expr_error["unclear_expression"],
            correct_content=expr_error.get("suggested_expression"),
            suggestion=expr_error["suggestion"],
            confidence=expr_error.get("confidence", 0.85)
        ))
    
    return ErrorScanResult(errors=errors)


def cross_validate_errors(errors: List[ErrorInstance]) -> List[ErrorInstance]:
    """
    交叉验证：去重和关联错误
    
    例如：同一个计算错误可能导致后续逻辑错误，应该合并。
    """
    # 使用哈希表去重（基于错误位置和内容）
    error_map: Dict[str, ErrorInstance] = {}
    
    for error in errors:
        # 生成唯一键
        key = f"{error.question_id}:{error.step_index}:{error.error_type}"
        
        if key in error_map:
            # 保留置信度更高的
            if error.confidence > error_map[key].confidence:
                error_map[key] = error
        else:
            error_map[key] = error
    
    # 识别关联错误（简化实现）
    # TODO: 可以使用 LLM 进行更智能的关联分析
    
    return list(error_map.values())


def prioritize_errors(errors: List[ErrorInstance]) -> List[ErrorInstance]:
    """
    错误分级：按严重程度排序
    """
    severity_order = {
        ErrorSeverity.CRITICAL: 0,
        ErrorSeverity.MAJOR: 1,
        ErrorSeverity.MINOR: 2
    }
    
    return sorted(
        errors,
        key=lambda e: (severity_order[e.severity], -e.confidence)
    )
```

### 2.5 复杂度分析

| 操作 | 时间复杂度 | 空间复杂度 | 说明 |
|------|-----------|-----------|------|
| 计算错误扫描 | O(n_calc) | O(e_calc) | n_calc 为计算题数 |
| 逻辑错误扫描 | O(n_logic) | O(e_logic) | n_logic 为推理题数 |
| 概念错误扫描 | O(n * p) | O(e_concept) | p 为平均知识点数 |
| 表达错误扫描 | O(n) | O(e_expr) | 所有题目 |
| 并行执行 | O(max(above)) | O(e_total) | 并行执行 4 个维度 |
| 交叉验证 | O(e) | O(e) | e 为错误总数 |
| **总计** | **O(n)** | **O(n * e)** | 线性复杂度 |

---

## 算法3: 分析报告生成算法

### 3.1 算法目标

为教师提供高质量的分析报告：
- 作业整体质量评估
- 优点与不足
- 改进建议（可操作）
- 学生理解程度分析
- 常见问题汇总（批量分析时）

### 3.2 算法流程

```
输入: UnderstandingResult + ErrorDetectionResult
输出: AnalysisReport

算法: AnalysisReportGeneration
┌─────────────────────────────────────────┐
│ 1. 数据聚合 (Data Aggregation)          │
│    - 汇总理解结果                         │
│    - 汇总纠错结果                         │
│    - 计算统计指标                         │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 2. 模板选择 (Template Selection)        │
│    - 根据科目选择报告模板                 │
│    - 根据题型调整报告结构                 │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 3. 结构化生成 (Structured Generation)   │
│    - 整体评估（1-2 句话）                 │
│    - 优点（2-3 条，具体）                 │
│    - 不足（2-3 条，具体）                 │
│    - 改进建议（3-5 条，可操作）           │
│    - 理解程度分析（按知识点）             │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 4. 批量汇总（可选）                       │
│    - 识别常见问题模式                     │
│    - 生成班级层面的分析                   │
└─────────────────────────────────────────┘
```

### 3.3 关键数据结构

```python
@dataclass
class AnalysisReport:
    """分析报告"""
    batch_id: str
    student_id: Optional[str] = None  # 单个学生（可选）
    
    # ===== 整体评估 =====
    overall_summary: str              # 整体评估（1-2 句话，精炼）
    quality_score: float              # 质量得分 (0.0-1.0)
    understanding_level: UnderstandingLevel
    
    # ===== 优点 =====
    strengths: List[str]              # 优点列表（2-3 条，具体）
    
    # ===== 不足 =====
    weaknesses: List[str]             # 不足列表（2-3 条，具体）
    
    # ===== 改进建议 =====
    suggestions: List[ActionableSuggestion]  # 可操作的建议（3-5 条）
    
    # ===== 理解程度分析 =====
    knowledge_analysis: Dict[str, KnowledgeAnalysis]  # 按知识点分析
    
    # ===== 错误分析 =====
    error_summary: ErrorSummary       # 错误汇总
    
    # ===== 元数据 =====
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    report_format: str = "markdown"   # 输出格式

@dataclass
class ActionableSuggestion:
    """可操作的建议"""
    priority: int                     # 优先级 (1=高, 2=中, 3=低)
    category: str                     # 分类（如 "计算技巧", "逻辑推理"）
    suggestion: str                   # 建议内容（必须具体、可操作）
    related_questions: List[str]      # 相关题目 ID
    expected_improvement: str         # 预期改进效果

@dataclass
class KnowledgeAnalysis:
    """知识点分析"""
    knowledge_point: str              # 知识点名称
    mastery_level: str                # 掌握程度（"优秀/良好/及格/不及格"）
    evidence: List[str]               # 证据（来自哪些题目）
    suggestion: Optional[str] = None  # 针对性建议

@dataclass
class ErrorSummary:
    """错误汇总"""
    total_errors: int
    critical_errors: int
    major_errors: int
    minor_errors: int
    most_common_error_type: ErrorType
    key_issues: List[str]             # 关键问题（3 条以内）

@dataclass
class ClassReport:
    """班级报告（批量分析）"""
    batch_id: str
    total_students: int
    
    # ===== 整体统计 =====
    average_score: float
    score_distribution: Dict[str, int]  # 分数段分布
    
    # ===== 常见问题 =====
    common_mistakes: List[CommonMistake]  # 按频率排序
    
    # ===== 知识点分析 =====
    class_knowledge_coverage: Dict[str, float]  # 知识点掌握率
    weak_knowledge_points: List[str]  # 全班薄弱知识点
    
    # ===== 建议 =====
    teaching_suggestions: List[str]   # 给教师的教学建议
    
    # ===== 元数据 =====
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class CommonMistake:
    """常见错误"""
    error_type: ErrorType
    description: str                  # 错误描述
    frequency: int                    # 出现频率
    affected_students: int            # 影响学生数
    example_question_ids: List[str]   # 示例题目
    suggestion: str                   # 改进建议
```

### 3.4 算法伪代码

```python
async def generate_analysis_report(
    understanding_result: UnderstandingResult,
    error_results: List[ErrorDetectionResult],
    config: ReportConfig
) -> AnalysisReport:
    """
    生成分析报告
    
    时间复杂度: O(n + e) - n 为题目数，e 为错误数
    空间复杂度: O(n + e)
    """
    
    # ===== 1. 数据聚合 =====
    aggregated_data = aggregate_results(understanding_result, error_results)
    
    # ===== 2. 模板选择 =====
    template = select_report_template(
        subject=config.subject,
        question_types=aggregated_data.question_types
    )
    
    # ===== 3. 结构化生成 =====
    
    # 3.1 整体评估（使用 LLM 生成精炼的评估）
    overall_summary = await generate_overall_summary(
        aggregated_data, template
    )
    
    # 3.2 提取优点（基于理解结果）
    strengths = extract_strengths(understanding_result, max_items=3)
    
    # 3.3 提取不足（基于错误结果）
    weaknesses = extract_weaknesses(error_results, max_items=3)
    
    # 3.4 生成可操作的建议
    suggestions = await generate_actionable_suggestions(
        understanding_result,
        error_results,
        max_suggestions=5
    )
    
    # 3.5 知识点分析
    knowledge_analysis = analyze_knowledge_points(
        understanding_result.knowledge_coverage,
        understanding_result.weak_areas
    )
    
    # 3.6 错误汇总
    error_summary = summarize_errors(error_results)
    
    # ===== 4. 构建报告 =====
    report = AnalysisReport(
        batch_id=understanding_result.batch_id,
        overall_summary=overall_summary,
        quality_score=calculate_quality_score(
            understanding_result, error_results
        ),
        understanding_level=understanding_result.overall_level,
        strengths=strengths,
        weaknesses=weaknesses,
        suggestions=suggestions,
        knowledge_analysis=knowledge_analysis,
        error_summary=error_summary,
        report_format=config.output_format
    )
    
    return report


async def generate_overall_summary(
    aggregated_data: AggregatedData,
    template: ReportTemplate
) -> str:
    """
    生成整体评估（1-2 句话，精炼）
    
    使用 LLM 生成，但严格限制输出长度。
    """
    result = await llm_call(
        prompt=OVERALL_SUMMARY_PROMPT,
        context={
            "understanding_level": aggregated_data.understanding_level,
            "total_errors": aggregated_data.total_errors,
            "critical_errors": aggregated_data.critical_errors,
            "strengths_count": len(aggregated_data.strengths),
            "weaknesses_count": len(aggregated_data.weaknesses)
        },
        response_format="json",
        max_tokens=100  # 严格限制长度
    )
    
    return result["summary"]


def extract_strengths(
    understanding_result: UnderstandingResult,
    max_items: int = 3
) -> List[str]:
    """
    提取优点（基于理解结果）
    
    优先级：
    1. 推理完整、逻辑严密
    2. 知识点应用正确
    3. 计算准确
    4. 表述清晰
    """
    strengths = []
    
    # 统计各类优点
    complete_logic_count = sum(
        1 for q in understanding_result.question_understandings
        if q.logic_chain_complete
    )
    
    correct_knowledge_count = sum(
        len([kp for kp in q.knowledge_points if kp.applied_correctly])
        for q in understanding_result.question_understandings
    )
    
    # 按优先级生成优点描述
    if complete_logic_count / understanding_result.total_questions > 0.8:
        strengths.append(
            f"推理逻辑严密，{complete_logic_count} 道题逻辑链条完整"
        )
    
    if correct_knowledge_count > understanding_result.total_questions * 2:
        strengths.append(
            f"知识点应用准确，正确应用 {correct_knowledge_count} 个知识点"
        )
    
    # 从单题的 strengths 中提取（去重）
    question_strengths = set()
    for q in understanding_result.question_understandings:
        question_strengths.update(q.strengths[:1])  # 每题最多取 1 个
    
    strengths.extend(list(question_strengths)[:max_items - len(strengths)])
    
    return strengths[:max_items]


def extract_weaknesses(
    error_results: List[ErrorDetectionResult],
    max_items: int = 3
) -> List[str]:
    """
    提取不足（基于错误结果）
    
    优先级：
    1. 严重错误（CRITICAL）
    2. 中等错误（MAJOR）
    3. 频繁出现的错误类型
    """
    weaknesses = []
    
    # 统计错误类型
    error_type_count: Dict[ErrorType, int] = {}
    critical_errors = []
    
    for result in error_results:
        for error in result.errors:
            error_type_count[error.error_type] = (
                error_type_count.get(error.error_type, 0) + 1
            )
            if error.severity == ErrorSeverity.CRITICAL:
                critical_errors.append(error)
    
    # 严重错误
    if critical_errors:
        most_critical = critical_errors[0]
        weaknesses.append(
            f"存在 {len(critical_errors)} 处严重错误，"
            f"主要是{ERROR_TYPE_CN[most_critical.error_type]}"
        )
    
    # 频繁错误类型
    if error_type_count:
        most_common_type = max(error_type_count, key=error_type_count.get)
        count = error_type_count[most_common_type]
        if count >= 3:
            weaknesses.append(
                f"{ERROR_TYPE_CN[most_common_type]}较多，"
                f"共 {count} 处需要改进"
            )
    
    return weaknesses[:max_items]


async def generate_actionable_suggestions(
    understanding_result: UnderstandingResult,
    error_results: List[ErrorDetectionResult],
    max_suggestions: int = 5
) -> List[ActionableSuggestion]:
    """
    生成可操作的建议
    
    基于错误和薄弱知识点生成具体建议。
    """
    suggestions = []
    
    # 1. 基于严重错误的建议
    for result in error_results:
        critical_errors = [
            e for e in result.errors
            if e.severity == ErrorSeverity.CRITICAL
        ]
        for error in critical_errors[:2]:  # 最多 2 个
            suggestions.append(ActionableSuggestion(
                priority=1,
                category=ERROR_TYPE_CN[error.error_type],
                suggestion=error.suggestion,
                related_questions=[error.question_id],
                expected_improvement="避免此类严重错误，提高答案正确性"
            ))
    
    # 2. 基于薄弱知识点的建议
    for weak_area in understanding_result.weak_areas[:2]:
        # 调用 LLM 生成针对性建议
        suggestion_text = await llm_call(
            prompt=KNOWLEDGE_SUGGESTION_PROMPT,
            context={
                "knowledge_point": weak_area,
                "student_level": understanding_result.overall_level
            },
            response_format="json",
            max_tokens=150
        )
        
        suggestions.append(ActionableSuggestion(
            priority=2,
            category="知识点强化",
            suggestion=suggestion_text["suggestion"],
            related_questions=suggestion_text.get("related_questions", []),
            expected_improvement=f"加强{weak_area}的理解和应用"
        ))
    
    # 3. 按优先级排序
    suggestions.sort(key=lambda s: s.priority)
    
    return suggestions[:max_suggestions]


async def generate_class_report(
    student_reports: List[AnalysisReport],
    config: ReportConfig
) -> ClassReport:
    """
    生成班级报告（批量分析）
    
    时间复杂度: O(n * e) - n 为学生数，e 为平均错误数
    空间复杂度: O(n + m) - m 为常见错误数
    """
    
    # ===== 1. 整体统计 =====
    total_students = len(student_reports)
    average_score = sum(r.quality_score for r in student_reports) / total_students
    
    score_distribution = calculate_score_distribution(student_reports)
    
    # ===== 2. 识别常见问题 =====
    # 使用哈希表统计错误模式
    error_pattern_count: Dict[str, CommonMistakeData] = {}
    
    for report in student_reports:
        for error_type, count in report.error_summary.errors_by_type.items():
            key = error_type.value
            if key not in error_pattern_count:
                error_pattern_count[key] = CommonMistakeData(
                    error_type=error_type,
                    count=0,
                    affected_students=set()
                )
            error_pattern_count[key].count += count
            error_pattern_count[key].affected_students.add(report.student_id)
    
    # 转换为 CommonMistake 列表并排序
    common_mistakes = []
    for pattern_data in error_pattern_count.values():
        # 为每种常见错误生成描述和建议
        mistake_desc = await llm_call(
            prompt=COMMON_MISTAKE_SUMMARY_PROMPT,
            context={
                "error_type": pattern_data.error_type,
                "frequency": pattern_data.count,
                "affected_students": len(pattern_data.affected_students),
                "total_students": total_students
            },
            response_format="json",
            max_tokens=200
        )
        
        common_mistakes.append(CommonMistake(
            error_type=pattern_data.error_type,
            description=mistake_desc["description"],
            frequency=pattern_data.count,
            affected_students=len(pattern_data.affected_students),
            example_question_ids=mistake_desc.get("example_questions", []),
            suggestion=mistake_desc["suggestion"]
        ))
    
    # 按频率排序
    common_mistakes.sort(key=lambda m: m.frequency, reverse=True)
    
    # ===== 3. 知识点分析 =====
    class_knowledge_coverage = calculate_class_knowledge_coverage(student_reports)
    weak_knowledge_points = identify_class_weak_points(
        class_knowledge_coverage,
        threshold=0.6  # 掌握率低于 60% 的知识点
    )
    
    # ===== 4. 教学建议 =====
    teaching_suggestions = await generate_teaching_suggestions(
        common_mistakes,
        weak_knowledge_points,
        average_score
    )
    
    # ===== 5. 构建报告 =====
    return ClassReport(
        batch_id=student_reports[0].batch_id,
        total_students=total_students,
        average_score=average_score,
        score_distribution=score_distribution,
        common_mistakes=common_mistakes[:10],  # 最多 10 个
        class_knowledge_coverage=class_knowledge_coverage,
        weak_knowledge_points=weak_knowledge_points,
        teaching_suggestions=teaching_suggestions
    )
```

### 3.5 复杂度分析

| 操作 | 时间复杂度 | 空间复杂度 | 说明 |
|------|-----------|-----------|------|
| 数据聚合 | O(n + e) | O(n + e) | n 题目数，e 错误数 |
| 整体评估生成 | O(1) | O(1) | 单次 LLM 调用 |
| 优点提取 | O(n) | O(n) | 遍历理解结果 |
| 不足提取 | O(e) | O(e) | 遍历错误结果 |
| 建议生成 | O(k) | O(k) | k 为建议数 (≤5) |
| 知识点分析 | O(n * p) | O(p) | p 为知识点数 |
| **单份报告** | **O(n + e)** | **O(n + e)** | 线性复杂度 |
| **班级报告** | **O(s * (n + e))** | **O(s + m)** | s 学生数，m 常见错误数 |

---

## 性能优化方案

### 4.1 并发策略

#### 4.1.1 多级并发

```python
class AssistGradingOrchestrator:
    """辅助批改编排器"""
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        # 三级并发控制
        self.stage_semaphore = asyncio.Semaphore(1)  # 阶段级（串行）
        self.question_semaphore = asyncio.Semaphore(5)  # 题目级（5 并发）
        self.dimension_semaphore = asyncio.Semaphore(4)  # 维度级（4 并发）
    
    async def process_batch(
        self,
        images: List[str],
        api_key: str
    ) -> Tuple[UnderstandingResult, List[ErrorDetectionResult], AnalysisReport]:
        """
        批量处理（三阶段流水线）
        
        阶段 1: 深度理解（不能并发，需要全局视角）
        阶段 2: 错误检测（可以按题目并发）
        阶段 3: 报告生成（基于阶段 1 和 2 的结果）
        """
        
        # ===== 阶段 1: 深度理解（串行） =====
        async with self.stage_semaphore:
            understanding_result = await deep_understanding_algorithm(
                images, api_key, self.config
            )
        
        # ===== 阶段 2: 错误检测（按题目并发） =====
        async def detect_errors_for_question(question):
            async with self.question_semaphore:
                return await intelligent_error_detection_for_question(
                    question, images, api_key, self.config
                )
        
        error_results = await asyncio.gather(*[
            detect_errors_for_question(q)
            for q in understanding_result.question_understandings
        ])
        
        # ===== 阶段 3: 报告生成（串行） =====
        async with self.stage_semaphore:
            report = await generate_analysis_report(
                understanding_result, error_results, self.config
            )
        
        return understanding_result, error_results, report
```

#### 4.1.2 流水线并行

```
时间线:
t0    t1    t2    t3    t4    t5
│     │     │     │     │     │
├─ 阶段1（深度理解）─┤
│                   ├─ 阶段2（错误检测-Q1）─┤
│                   ├─ 阶段2（错误检测-Q2）─┤
│                   ├─ 阶段2（错误检测-Q3）─┤
│                   └─ 阶段2（错误检测-Q4）─┤
│                                           ├─ 阶段3（报告生成）─┤
```

### 4.2 Token 优化策略

#### 4.2.1 批量处理（减少调用次数）

```python
class TokenOptimizer:
    """Token 优化器"""
    
    @staticmethod
    def batch_questions(
        questions: List[QuestionUnderstanding],
        max_tokens_per_batch: int = 30000
    ) -> List[List[QuestionUnderstanding]]:
        """
        将题目分批，每批的 token 数不超过阈值
        
        策略：
        1. 估算每题的 token 数（基于图像大小）
        2. 贪心分组，尽量填满每批
        3. 保证每批至少有 1 题
        """
        batches = []
        current_batch = []
        current_tokens = 0
        
        for question in questions:
            # 估算 token 数（图像 + 文本）
            estimated_tokens = estimate_question_tokens(question)
            
            if current_tokens + estimated_tokens > max_tokens_per_batch:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [question]
                current_tokens = estimated_tokens
            else:
                current_batch.append(question)
                current_tokens += estimated_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    @staticmethod
    def estimate_question_tokens(question: QuestionUnderstanding) -> int:
        """
        估算题目的 token 数
        
        Gemini 计费规则：
        - 文本: ~1.3 tokens/字（中文）
        - 图像: 258 tokens/tile (每张图约 4-16 tiles)
        """
        # 文本 token
        text_tokens = len(question.question_text) * 1.3
        text_tokens += len(question.student_answer) * 1.3
        
        # 图像 token（假设每张图 1024 tokens）
        image_tokens = len(question.page_indices) * 1024
        
        # Prompt token（固定开销）
        prompt_tokens = 1000
        
        return int(text_tokens + image_tokens + prompt_tokens)
```

#### 4.2.2 增量处理（避免重复传输）

```python
class IncrementalProcessor:
    """增量处理器（利用缓存）"""
    
    def __init__(self):
        self.image_cache: Dict[str, str] = {}  # 图像哈希 -> 缓存 ID
        self.context_cache: Dict[str, Any] = {}  # 上下文缓存
    
    async def process_with_cache(
        self,
        images: List[str],
        context: Dict[str, Any]
    ) -> Any:
        """
        使用缓存的增量处理
        
        Gemini 支持 Cached Content，可以减少重复传输。
        """
        # 1. 检查图像是否已缓存
        cached_images = []
        new_images = []
        
        for img in images:
            img_hash = hash_image(img)
            if img_hash in self.image_cache:
                cached_images.append(self.image_cache[img_hash])
            else:
                new_images.append(img)
        
        # 2. 如果有新图像，创建缓存
        if new_images:
            cache_id = await create_gemini_cache(
                images=new_images,
                ttl_seconds=3600  # 1 小时
            )
            for img in new_images:
                self.image_cache[hash_image(img)] = cache_id
        
        # 3. 使用缓存调用 LLM
        result = await llm_call_with_cache(
            cached_content_ids=cached_images,
            new_images=new_images,
            context=context
        )
        
        return result
```

#### 4.2.3 Prompt 压缩

```python
# ❌ 冗余的 Prompt（浪费 token）
BAD_PROMPT = """
请你仔细分析这道题目，认真思考学生的答案，深入理解解题思路，
全面评估知识点掌握情况，详细指出存在的问题，并给出具体的改进建议。
请务必认真对待，不要遗漏任何细节，确保分析的全面性和准确性。
"""

# ✅ 精简的 Prompt（节省 token）
GOOD_PROMPT = """
分析题目和学生答案：
1. 识别知识点
2. 评估解题思路
3. 指出错误（如有）
4. 给出改进建议

输出 JSON 格式。
"""
```

### 4.3 缓存策略

#### 4.3.1 多级缓存

```python
from functools import lru_cache
import hashlib
import json

class MultiLevelCache:
    """多级缓存"""
    
    def __init__(self):
        # L1: 内存缓存（LRU）
        self.memory_cache: Dict[str, Any] = {}
        self.max_memory_items = 100
        
        # L2: Redis 缓存（可选）
        self.redis_client = None  # 如果需要跨进程共享
        
        # L3: Gemini Cached Content
        self.gemini_cache_ids: Dict[str, str] = {}
    
    @lru_cache(maxsize=100)
    def get_understanding_result(self, cache_key: str) -> Optional[UnderstandingResult]:
        """获取理解结果（L1 缓存）"""
        return self.memory_cache.get(cache_key)
    
    def set_understanding_result(self, cache_key: str, result: UnderstandingResult):
        """设置理解结果（L1 缓存）"""
        # LRU 淘汰
        if len(self.memory_cache) >= self.max_memory_items:
            oldest_key = next(iter(self.memory_cache))
            del self.memory_cache[oldest_key]
        
        self.memory_cache[cache_key] = result
    
    def generate_cache_key(self, images: List[str], config: Any) -> str:
        """生成缓存键（基于图像哈希和配置）"""
        # 图像哈希
        image_hashes = [hashlib.md5(img.encode()).hexdigest() for img in images]
        
        # 配置哈希
        config_str = json.dumps(config, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()
        
        # 组合
        return f"understanding:{'-'.join(image_hashes[:3])}:{config_hash}"
```

#### 4.3.2 缓存失效策略

```python
class CacheInvalidation:
    """缓存失效策略"""
    
    @staticmethod
    def should_invalidate(
        cache_entry: CacheEntry,
        current_time: datetime
    ) -> bool:
        """
        判断是否应该失效缓存
        
        失效条件：
        1. 超过 TTL（Time To Live）
        2. 配置发生变化
        3. 模型版本更新
        """
        # 1. TTL 检查
        if (current_time - cache_entry.created_at).seconds > cache_entry.ttl:
            return True
        
        # 2. 配置变化检查
        if cache_entry.config_version != get_current_config_version():
            return True
        
        # 3. 模型版本检查
        if cache_entry.model_version != get_current_model_version():
            return True
        
        return False
```

### 4.4 性能监控

```python
@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_processing_time_ms: float
    understanding_time_ms: float
    error_detection_time_ms: float
    report_generation_time_ms: float
    
    llm_call_count: int
    total_tokens_used: int
    total_cost_usd: float
    
    cache_hit_rate: float
    average_question_time_ms: float

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
    
    async def track_operation(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, PerformanceMetrics]:
        """追踪操作性能"""
        start_time = datetime.now()
        
        # 执行操作
        result = await operation(*args, **kwargs)
        
        # 计算耗时
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        # 收集指标
        metrics = PerformanceMetrics(
            total_processing_time_ms=elapsed,
            # ... 其他指标
        )
        
        self.metrics.append(metrics)
        
        return result, metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.metrics:
            return {}
        
        return {
            "average_time_ms": sum(m.total_processing_time_ms for m in self.metrics) / len(self.metrics),
            "total_llm_calls": sum(m.llm_call_count for m in self.metrics),
            "total_tokens": sum(m.total_tokens_used for m in self.metrics),
            "total_cost_usd": sum(m.total_cost_usd for m in self.metrics),
            "average_cache_hit_rate": sum(m.cache_hit_rate for m in self.metrics) / len(self.metrics),
        }
```

### 4.5 预期性能指标

基于 Google Gemini 3.0 Flash 的性能：

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 单题深度理解 | 2-5 秒 | 取决于题目复杂度 |
| 单题错误检测 | 3-8 秒 | 4 个维度并行扫描 |
| 报告生成 | 1-3 秒 | 基于聚合结果 |
| **单份作业总耗时** | **10-30 秒** | 假设 5-10 题 |
| **批量作业（30 份）** | **5-10 分钟** | 并发处理 |
| Token 使用 | 5K-15K/份 | 取决于题目数和图像数 |
| 成本 | $0.001-0.005/份 | Gemini Flash 价格 |
| 缓存命中率 | >60% | 在批量处理时 |

---

## Prompt 工程

### 5.1 核心 Prompt 模板

#### 5.1.1 粗读阶段 Prompt

```python
COARSE_READING_PROMPT = """你是一名经验丰富的作业分析专家。请快速浏览这份学生作业，提取关键信息。

**任务**：
1. 识别作业中有多少道题目
2. 判断每道题的题型（选择/填空/计算/证明/开放/分析）
3. 提取每道题的主题和关键词
4. 评估作业整体难度（简单/中等/困难）

**输出格式**（JSON）：
```json
{
  "total_questions": 5,
  "overall_difficulty": "中等",
  "questions": [
    {
      "question_id": "1",
      "question_type": "calculation",
      "topic": "二次方程求解",
      "keywords": ["配方法", "求根公式"],
      "estimated_difficulty": "简单",
      "page_indices": [0]
    },
    ...
  ]
}
```

**注意**：
- 只需要快速概览，不需要深入分析
- 如果题目跨页，记录所有页面索引
- 题目编号使用字符串格式（支持 "1a", "2.1" 等）
"""


#### 5.1.2 精读阶段 Prompt

FINE_READING_PROMPT = """你是一名学科专家。请深入分析以下题目的学生答案。

**题目信息**：
{question_context}

**任务**：
1. 提取学生的完整解题步骤
2. 识别每一步使用的公式、定理、方法
3. 判断推理链条是否完整
4. 识别涉及的知识点
5. 评估学生的理解程度

**输出格式**（JSON）：
```json
{
  "question_id": "1",
  "question_text": "...",
  "student_answer": "...",
  "reasoning_steps": [
    {
      "step_index": 1,
      "description": "设方程为 x² + bx + c = 0",
      "formula_used": "二次方程标准形式",
      "is_correct": true
    },
    ...
  ],
  "logic_chain_complete": true,
  "knowledge_points": [
    {
      "id": "kp_quadratic_formula",
      "name": "求根公式",
      "category": "代数",
      "applied_correctly": true,
      "confidence": 0.95
    },
    ...
  ],
  "understanding_level": "good",
  "understanding_score": 0.82,
  "strengths": [
    "公式应用正确",
    "步骤清晰"
  ],
  "weaknesses": [
    "缺少必要的验证步骤"
  ]
}
```

**评估标准**：
- **excellent** (0.9-1.0): 推理严密，知识点应用准确，无明显不足
- **good** (0.75-0.89): 整体正确，有小的不足
- **fair** (0.6-0.74): 部分正确，存在明显问题
- **poor** (<0.6): 错误较多或理解偏差
"""


#### 5.1.3 推理验证 Prompt

REASONING_VERIFICATION_PROMPT = """你是一名逻辑验证专家。请严格检查以下推理步骤的正确性和严密性。

**题目**：{question_text}

**学生推理步骤**：
{reasoning_steps}

**任务**：
1. 逐步验证每个推理步骤的正确性
2. 检查步骤之间的逻辑连接
3. 识别推理漏洞或跳跃
4. 验证最终结论是否由前提推出

**输出格式**（JSON）：
```json
{
  "verification_results": [
    {
      "step_index": 1,
      "is_correct": true,
      "is_rigorous": true,
      "issues": []
    },
    {
      "step_index": 3,
      "is_correct": false,
      "is_rigorous": false,
      "issues": [
        {
          "issue_type": "logic_gap",
          "description": "从步骤 2 到步骤 3 缺少中间推导",
          "suggestion": "需要说明为什么可以这样变形"
        }
      ]
    },
    ...
  ],
  "overall_logic_valid": false,
  "critical_issues": [
    "步骤 3 的推导缺少依据"
  ]
}
```

**验证标准**：
- 每一步必须有明确的依据（公式、定理、前提）
- 步骤之间必须有逻辑连接
- 不允许跳跃推理（除非是显而易见的）
- 最终结论必须从前提严格推出
"""


#### 5.1.4 计算错误扫描 Prompt

CALCULATION_VERIFICATION_PROMPT = """你是一名计算验证专家。请仔细检查学生答案中的所有计算步骤。

**题目**：{question_text}

**学生答案**：{student_answer}

**推理步骤**：
{reasoning_steps}

**任务**：
1. 重新计算每个数值结果
2. 验证公式应用是否正确
3. 检查单位换算是否正确
4. 识别计算错误（如果有）

**输出格式**（JSON）：
```json
{
  "errors": [
    {
      "step_index": 3,
      "error_type": "calculation_error",
      "description": "计算错误：2 * 5 = 12 应为 10",
      "incorrect": "2 * 5 = 12",
      "correct": "2 * 5 = 10",
      "suggestion": "重新计算该步骤，注意运算顺序",
      "confidence": 1.0
    },
    {
      "step_index": 5,
      "error_type": "formula_misuse",
      "description": "公式应用错误：应使用 a² + b² = c²，而非 a + b = c",
      "incorrect": "a + b = c",
      "correct": "a² + b² = c²",
      "suggestion": "复习勾股定理的正确形式",
      "confidence": 0.95
    }
  ],
  "calculation_accuracy": 0.7,
  "has_critical_errors": true
}
```

**注意**：
- 只报告确实的计算错误，不要猜测
- 如果学生的方法不同但结果正确，不算错误
- 对于近似计算，允许合理的误差范围
"""


#### 5.1.5 逻辑错误扫描 Prompt

LOGIC_VERIFICATION_PROMPT = """你是一名逻辑分析专家。请检查学生答案中的逻辑推理。

**题目**：{question_text}

**推理步骤**：
{reasoning_steps}

**任务**：
1. 检查每个推理步骤的逻辑依据
2. 识别前后矛盾
3. 识别循环论证
4. 识别逻辑跳跃

**输出格式**（JSON）：
```json
{
  "errors": [
    {
      "step_index": 4,
      "error_type": "logical_gap",
      "description": "逻辑跳跃：从 A > B 直接推出 A² > B²，未考虑负数情况",
      "problematic_reasoning": "因为 A > B，所以 A² > B²",
      "suggestion": "需要分情况讨论：当 A, B 都为正数时...",
      "explanation": "平方函数在负数区间不保持单调性",
      "breaks_conclusion": true,
      "confidence": 0.9
    },
    {
      "step_index": 6,
      "error_type": "contradiction",
      "description": "前后矛盾：步骤 3 假设 x > 0，但步骤 6 又假设 x < 0",
      "problematic_reasoning": "...",
      "suggestion": "统一假设条件，或分情况讨论",
      "explanation": "不能在同一推导中使用相互矛盾的假设",
      "breaks_conclusion": true,
      "confidence": 0.95
    }
  ],
  "logic_soundness_score": 0.6
}
```

**重点关注**：
- 隐含假设是否合理
- 充分性和必要性
- 反例的存在性
- 特殊情况的处理
"""


#### 5.1.6 概念错误扫描 Prompt

CONCEPT_VERIFICATION_PROMPT = """你是一名学科教学专家。请检查学生对核心概念的理解。

**知识点**：{knowledge_point}

**学生答案**：{student_answer}

**任务**：
1. 判断学生是否正确理解该知识点
2. 识别概念混淆
3. 识别公式误用
4. 提供正确的概念解释

**输出格式**（JSON）：
```json
{
  "has_error": true,
  "description": "混淆了"导数"和"微分"的概念",
  "misapplied_concept": "将导数定义错误地应用于离散变量",
  "correct_application": "导数是连续函数的局部变化率，对于离散变量应使用差分",
  "suggestion": "复习导数的定义和适用条件，区分连续和离散情况",
  "explanation": "导数要求函数在该点的邻域内连续，而离散变量不满足此条件",
  "confidence": 0.85,
  "related_resources": [
    "微积分基础 - 导数定义",
    "连续与离散的区别"
  ]
}
```

**概念检查清单**：
- 定义是否准确
- 适用条件是否满足
- 是否混淆相似概念
- 是否误用公式或定理
"""


#### 5.1.7 表达错误扫描 Prompt

EXPRESSION_CHECK_PROMPT = """你是一名学术写作专家。请检查学生答案的表述质量。

**学生答案**：{student_answer}

**任务**：
1. 识别表述不清晰的地方
2. 识别符号使用错误
3. 识别逻辑连接词误用
4. 提供改进建议

**输出格式**（JSON）：
```json
{
  "errors": [
    {
      "error_type": "unclear_expression",
      "description": "表述不清：没有明确说明 'x' 代表什么",
      "unclear_expression": "解方程得 x = 5",
      "suggested_expression": "设未知数为 x (单位: 米)，解方程得 x = 5",
      "suggestion": "在首次使用变量时明确其含义和单位",
      "confidence": 0.9
    },
    {
      "error_type": "symbol_error",
      "description": "符号错误：混用等号和约等号",
      "unclear_expression": "π = 3.14",
      "suggested_expression": "π ≈ 3.14",
      "suggestion": "对于近似值使用约等号 ≈",
      "confidence": 0.95
    }
  ]
}
```

**表达规范**：
- 变量定义清晰
- 符号使用规范
- 逻辑连接清晰
- 单位标注完整
"""


#### 5.1.8 整体评估 Prompt

OVERALL_SUMMARY_PROMPT = """你是一名作业评估专家。请用 1-2 句话概括这份作业的整体质量。

**数据**：
- 理解程度：{understanding_level}
- 错误总数：{total_errors}
- 严重错误：{critical_errors}
- 优点数量：{strengths_count}
- 不足数量：{weaknesses_count}

**要求**：
1. 精炼、客观、有信息量
2. 不超过 50 字
3. 突出核心问题或亮点

**输出格式**（JSON）：
```json
{
  "summary": "作业整体质量良好，推理逻辑清晰，但存在 2 处计算错误需要改进。"
}
```

**示例**：
- ✅ "解题思路正确，步骤完整，但第 3 题计算错误导致最终答案不对。"
- ✅ "基础知识掌握扎实，表述清晰，仅有少量符号使用不规范。"
- ❌ "这份作业非常好，学生很努力，值得表扬。"（太泛泛）
"""


#### 5.1.9 可操作建议生成 Prompt

KNOWLEDGE_SUGGESTION_PROMPT = """你是一名个性化学习顾问。请为学生生成针对性的学习建议。

**薄弱知识点**：{knowledge_point}

**学生水平**：{student_level}

**任务**：
生成 1 条具体、可操作的学习建议。

**输出格式**（JSON）：
```json
{
  "suggestion": "针对"求根公式"的掌握不足，建议：1) 重新推导公式 3 次，理解配方法的原理；2) 练习 10 道不同类型的二次方程（包括无实根、重根情况）；3) 总结判别式 Δ 与根的关系。",
  "related_questions": ["1", "3"],
  "expected_time": "30-45 分钟",
  "resources": [
    "教材第 3 章例 5",
    "Khan Academy: Quadratic Formula"
  ]
}
```

**建议原则**：
1. 具体可操作（有明确的步骤）
2. 有数量目标（如"练习 10 道题"）
3. 有时间预期
4. 推荐相关资源
"""


#### 5.1.10 常见错误汇总 Prompt

COMMON_MISTAKE_SUMMARY_PROMPT = """你是一名教学分析专家。请分析这个班级的常见错误模式。

**错误类型**：{error_type}

**出现频率**：{frequency}

**影响学生数**：{affected_students} / {total_students}

**任务**：
生成该错误类型的摘要和教学建议。

**输出格式**（JSON）：
```json
{
  "description": "全班有 23/30 名学生在计算二次方程判别式时出错，主要错误是混淆 b² - 4ac 和 b² + 4ac",
  "example_questions": ["1", "3", "7"],
  "suggestion": "建议课上重点讲解判别式的推导过程，强调负号的来源（配方法的展开），并设计针对性练习",
  "root_cause": "对配方法的理解不够深入，记忆公式而非理解原理",
  "teaching_priority": "high"
}
```
"""
```

### 5.2 Prompt 设计原则

1. **明确任务**: 每个 Prompt 只负责一个明确的任务
2. **结构化输出**: 强制使用 JSON 格式，便于解析
3. **示例驱动**: 提供正例和反例
4. **约束清晰**: 明确输出长度、格式、内容要求
5. **上下文最小化**: 只传递必要的上下文信息

---

## 实现建议

### 6.1 技术选型

| 组件 | 推荐技术 | 原因 |
|------|---------|------|
| LLM | Google Gemini 3.0 Flash | 长上下文、多模态、成本低 |
| 工作流编排 | LangGraph | 与主系统一致 |
| 异步框架 | asyncio + aiohttp | Python 原生，性能好 |
| 缓存 | Redis（可选）| 跨进程共享 |
| 监控 | Prometheus + Grafana | 标准监控方案 |

### 6.2 项目结构

```
GradeOS-Platform/backend/src/
├── graphs/
│   ├── assist_grading.py          # 辅助批改 LangGraph 工作流
│   └── assist_grading_nodes.py    # 节点实现
├── services/
│   ├── understanding_service.py    # 深度理解服务
│   ├── error_detection_service.py  # 纠错服务
│   ├── report_generation_service.py # 报告生成服务
│   └── assist_grading_optimizer.py # 性能优化器
├── models/
│   ├── assist_grading_models.py    # 数据模型
│   └── assist_grading_prompts.py   # Prompt 模板
└── utils/
    ├── token_optimizer.py          # Token 优化工具
    └── cache_manager.py            # 缓存管理器
```

### 6.3 集成方案

#### 6.3.1 与主批改系统的集成

```python
# 在 BatchGradingGraphState 中添加字段
class BatchGradingGraphState(TypedDict, total=False):
    # ... 现有字段 ...
    
    # ===== 辅助批改相关 =====
    grading_mode: Optional[str]  # "standard" / "assist_teacher" / "assist_student"
    assist_grading_enabled: bool  # 是否启用辅助批改
    assist_grading_results: Dict[str, Any]  # 辅助批改结果


# 在批改工作流中添加条件分支
def should_run_assist_grading(state: BatchGradingGraphState) -> bool:
    """判断是否需要运行辅助批改"""
    mode = state.get("grading_mode", "standard")
    return mode in ["assist_teacher", "assist_student"]


# 添加辅助批改节点
async def assist_grading_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """辅助批改节点（可选执行）"""
    if not should_run_assist_grading(state):
        return {}
    
    # 执行辅助批改
    orchestrator = AssistGradingOrchestrator(config)
    understanding, errors, report = await orchestrator.process_batch(
        images=state["processed_images"],
        api_key=state["api_key"]
    )
    
    return {
        "assist_grading_results": {
            "understanding": understanding.to_dict(),
            "errors": [e.to_dict() for e in errors],
            "report": report.to_dict()
        }
    }
```

#### 6.3.2 异步执行（不阻塞主流程）

```python
# 方案 1: 使用 LangGraph 的并行节点
graph_builder.add_node("standard_grading", standard_grading_node)
graph_builder.add_node("assist_grading", assist_grading_node)

# 并行执行
graph_builder.add_edge("preprocess", "standard_grading")
graph_builder.add_edge("preprocess", "assist_grading")  # 同时启动

# 在后续节点中合并结果
graph_builder.add_node("merge_results", merge_results_node)
graph_builder.add_edge("standard_grading", "merge_results")
graph_builder.add_edge("assist_grading", "merge_results")


# 方案 2: 使用异步任务队列（Celery / RQ）
@celery_app.task
def run_assist_grading_async(batch_id: str, images: List[str]):
    """异步运行辅助批改"""
    result = await assist_grading_pipeline(images)
    # 保存结果到数据库
    save_assist_grading_result(batch_id, result)
```

### 6.4 API 接口设计

```python
from fastapi import APIRouter, Depends
from src.models.assist_grading_models import (
    AssistGradingRequest,
    AssistGradingResponse
)

router = APIRouter(prefix="/api/v1/assist-grading", tags=["辅助批改"])


@router.post("/analyze", response_model=AssistGradingResponse)
async def analyze_homework(
    request: AssistGradingRequest,
    api_key: str = Depends(get_api_key)
):
    """
    辅助批改接口
    
    无标准答案场景，深度理解作业并生成分析报告。
    """
    orchestrator = AssistGradingOrchestrator(config)
    
    understanding, errors, report = await orchestrator.process_batch(
        images=request.images,
        api_key=api_key
    )
    
    return AssistGradingResponse(
        batch_id=request.batch_id,
        understanding_result=understanding,
        error_detection_results=errors,
        analysis_report=report,
        processing_time_ms=orchestrator.get_total_time()
    )


@router.get("/report/{batch_id}", response_model=AnalysisReport)
async def get_analysis_report(batch_id: str):
    """获取分析报告"""
    report = await get_report_from_db(batch_id)
    return report


@router.post("/class-report", response_model=ClassReport)
async def generate_class_report(
    batch_id: str,
    student_ids: List[str]
):
    """生成班级报告（批量分析）"""
    student_reports = [
        await get_report_from_db(f"{batch_id}:{sid}")
        for sid in student_ids
    ]
    
    class_report = await generate_class_report_func(student_reports)
    return class_report
```

### 6.5 测试策略

#### 6.5.1 单元测试

```python
import pytest
from src.services.understanding_service import DeepUnderstandingService

@pytest.mark.asyncio
async def test_deep_understanding():
    """测试深度理解算法"""
    service = DeepUnderstandingService()
    
    result = await service.analyze(
        images=["test_image_1.png"],
        api_key="test_key"
    )
    
    assert result.total_questions > 0
    assert len(result.question_understandings) == result.total_questions
    assert result.overall_score >= 0.0 and result.overall_score <= 1.0


@pytest.mark.asyncio
async def test_error_detection():
    """测试纠错算法"""
    understanding_result = create_mock_understanding_result()
    
    service = ErrorDetectionService()
    errors = await service.detect(understanding_result, images=[])
    
    # 验证错误检测结果
    for error in errors:
        assert error.suggestion  # 每个错误必须有建议
        assert error.confidence >= 0.0 and error.confidence <= 1.0
```

#### 6.5.2 集成测试

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_assist_grading_pipeline():
    """测试完整的辅助批改流程"""
    orchestrator = AssistGradingOrchestrator(config)
    
    # 使用真实的测试图像
    images = load_test_images("test_homework_1")
    
    understanding, errors, report = await orchestrator.process_batch(
        images=images,
        api_key=os.getenv("GEMINI_API_KEY")
    )
    
    # 验证结果完整性
    assert understanding.total_questions > 0
    assert len(errors) == understanding.total_questions
    assert report.overall_summary
    assert len(report.suggestions) > 0
```

#### 6.5.3 性能测试

```python
@pytest.mark.performance
@pytest.mark.asyncio
async def test_performance_single_homework():
    """测试单份作业的处理性能"""
    import time
    
    start = time.time()
    
    await assist_grading_pipeline(images=test_images)
    
    elapsed = time.time() - start
    
    # 应该在 30 秒内完成
    assert elapsed < 30.0


@pytest.mark.performance
@pytest.mark.asyncio
async def test_performance_batch():
    """测试批量作业的处理性能"""
    import time
    
    batch_size = 30
    start = time.time()
    
    await process_batch_homework(batch_size=batch_size)
    
    elapsed = time.time() - start
    
    # 30 份作业应该在 10 分钟内完成
    assert elapsed < 600.0
    
    # 平均每份 < 20 秒
    assert elapsed / batch_size < 20.0
```

### 6.6 部署建议

1. **独立部署（推荐）**: 辅助批改作为独立服务，不影响主批改系统
2. **资源配置**: 建议独立的 GPU 实例（如果使用本地模型）或独立的 API Key 配额
3. **监控**: 重点监控 LLM 调用次数、Token 使用、成本
4. **降级策略**: 如果辅助批改失败，不应影响主批改系统

### 6.7 潜在挑战与解决方案

| 挑战 | 解决方案 |
|------|---------|
| LLM 理解不准确 | 多次验证 + 置信度评分 + 人工复核 |
| Token 成本过高 | 批量处理 + 缓存 + Prompt 优化 |
| 处理速度慢 | 并发 + 异步 + 流水线 |
| 不同学科差异大 | 学科特定的 Prompt 模板 |
| 错误检测假阳性 | 交叉验证 + 置信度阈值 |
| 报告质量不稳定 | 结构化生成 + 模板约束 |

---

## 总结

本文档设计了辅助批改系统的三大核心算法：

1. **作业深度理解算法**: 通过多阶段分析（粗读→精读→推理验证→知识点映射），在无标准答案的情况下理解作业内容，时间复杂度 O(n)。

2. **智能纠错算法**: 通过多维度并行扫描（计算→逻辑→概念→表达），发现各类错误并生成可操作的建议，时间复杂度 O(n)。

3. **分析报告生成算法**: 基于理解和纠错结果，生成高质量的结构化报告，避免废话，提供可操作的建议，时间复杂度 O(n + e)。

**性能优化方案**包括：
- 三级并发（阶段级→题目级→维度级）
- Token 优化（批量处理、增量处理、Prompt 压缩）
- 多级缓存（内存→Redis→Gemini Cache）
- 性能监控和指标追踪

**预期性能**：
- 单份作业（5-10 题）: 10-30 秒
- 批量作业（30 份）: 5-10 分钟
- Token 使用: 5K-15K/份
- 成本: $0.001-0.005/份

通过充分利用 Google Gemini 3.0 Flash 的长上下文和多模态能力，结合高效的算法设计和性能优化，辅助批改系统可以在不拖慢主系统的前提下，为教师提供有价值的深度分析。
