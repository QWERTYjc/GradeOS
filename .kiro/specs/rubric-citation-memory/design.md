# 评分标准引用与记忆系统优化 - 设计文档

## 架构概述

```
┌─────────────────────────────────────────────────────────────────┐
│                        批改工作流                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ 证据提取 │───▶│ 评分映射 │───▶│ 自我反思 │───▶│ 逻辑复核 │  │
│  └──────────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘  │
│                       │               │               │         │
│                       ▼               ▼               │         │
│              ┌────────────────────────────┐          │         │
│              │      记忆系统 (分层)        │◀─────────┘         │
│              │  ┌─────┐ ┌─────┐ ┌─────┐  │    (只读对比)       │
│              │  │待验证│ │已验证│ │核心 │  │                    │
│              │  └─────┘ └─────┘ └─────┘  │                    │
│              └────────────────────────────┘                    │
│                       │                                        │
│                       ▼                                        │
│              ┌────────────────────────────┐                    │
│              │        自白生成            │                    │
│              └────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## 数据模型变更

### 1. ScoringPointResult 扩展

```python
@dataclass
class ScoringPointResult:
    """得分点评分结果 - 扩展版"""
    scoring_point: ScoringPoint
    awarded: float
    evidence: str = ""
    
    # 新增字段
    rubric_reference: Optional[str] = None  # 评分标准引用，如 "1.2.a" 或原文摘要
    is_alternative_solution: bool = False   # 是否为另类解法
    alternative_description: str = ""       # 另类解法描述
    point_confidence: float = 0.9           # 该得分点的置信度
    citation_quality: str = "exact"         # exact/partial/none
```

### 2. MemoryEntry 扩展

```python
class MemoryVerificationStatus(str, Enum):
    """记忆验证状态"""
    PENDING = "pending"       # 待验证
    VERIFIED = "verified"     # 已验证
    CORE = "core"             # 核心记忆
    SUSPICIOUS = "suspicious" # 可疑（可信度低）
    DEPRECATED = "deprecated" # 已废弃

@dataclass
class MemoryEntry:
    # ... 现有字段 ...
    
    # 新增字段
    verification_status: MemoryVerificationStatus = MemoryVerificationStatus.PENDING
    verification_history: List[Dict[str, Any]] = field(default_factory=list)
    source_self_report_id: Optional[str] = None  # 来源自白ID
    is_soft_deleted: bool = False
    deleted_at: Optional[str] = None
    deleted_reason: Optional[str] = None
```

### 3. SelfReportIssue 扩展

```python
@dataclass
class SelfReportIssue:
    """自白问题条目"""
    issue_id: str
    type: str  # low_confidence, missing_evidence, alternative_solution, memory_conflict
    severity: str  # info, warning, error
    question_id: str
    point_id: Optional[str] = None
    message: str = ""
    suggestion: str = ""
    
    # 新增字段
    should_create_memory: bool = False  # 是否应创建记忆
    memory_type: Optional[MemoryType] = None
    memory_pattern: Optional[str] = None
    memory_lesson: Optional[str] = None
```

## 核心算法

### 1. 置信度计算算法

```python
def calculate_point_confidence(
    has_rubric_reference: bool,
    citation_quality: str,  # exact/partial/none
    is_alternative_solution: bool,
    base_confidence: float = 0.9
) -> float:
    """
    计算单个得分点的置信度
    
    规则：
    1. 有精确引用：base_confidence (0.9)
    2. 有部分引用：base_confidence * 0.9 (0.81)
    3. 无引用：min(base_confidence, 0.7)
    4. 另类解法：再降低 25%
    """
    confidence = base_confidence
    
    if not has_rubric_reference:
        confidence = min(confidence, 0.7)
    elif citation_quality == "partial":
        confidence *= 0.9
    
    if is_alternative_solution:
        confidence *= 0.75
    
    return round(confidence, 3)

def calculate_question_confidence(
    point_results: List[ScoringPointResult]
) -> float:
    """
    计算题目整体置信度（加权平均）
    
    权重 = 得分点分值 / 总分值
    """
    if not point_results:
        return 0.5
    
    total_weight = sum(p.scoring_point.score for p in point_results)
    if total_weight == 0:
        return sum(p.point_confidence for p in point_results) / len(point_results)
    
    weighted_sum = sum(
        p.point_confidence * p.scoring_point.score 
        for p in point_results
    )
    return round(weighted_sum / total_weight, 3)
```

### 2. 自白驱动的记忆更新算法

```python
async def update_memory_from_self_report(
    self_report: Dict[str, Any],
    memory_service: GradingMemoryService,
    batch_id: str,
    subject: str
) -> List[str]:
    """
    从自白结果更新记忆系统
    
    返回：新创建的记忆ID列表
    """
    created_memory_ids = []
    
    for issue in self_report.get("issues", []):
        if not issue.get("should_create_memory"):
            continue
        
        # 检查是否已存在相似记忆
        existing = memory_service.retrieve_relevant_memories(
            memory_types=[issue["memory_type"]],
            subject=subject,
            max_results=1
        )
        
        if existing and _is_similar_pattern(existing[0].pattern, issue["memory_pattern"]):
            # 更新已有记忆
            memory_service.confirm_memory(existing[0].memory_id)
            continue
        
        # 创建新记忆（待验证状态）
        memory_id = await memory_service.save_memory_async(
            memory_type=issue["memory_type"],
            pattern=issue["memory_pattern"],
            lesson=issue["memory_lesson"],
            context={
                "source": "self_report",
                "issue_type": issue["type"],
                "question_id": issue["question_id"],
            },
            importance=_severity_to_importance(issue["severity"]),
            batch_id=batch_id,
            subject=subject,
        )
        created_memory_ids.append(memory_id)
    
    return created_memory_ids
```

### 3. 记忆审查算法

```python
def review_memory_conflict(
    memory_entry: MemoryEntry,
    logic_review_result: Dict[str, Any],
    grading_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    当逻辑复核与记忆建议冲突时，进行记忆审查
    
    返回：审查结果
    """
    # 逻辑复核是"无记忆"的，它的判断更客观
    logic_confidence = logic_review_result.get("confidence", 0.8)
    memory_confidence = memory_entry.confidence
    
    # 如果逻辑复核置信度高于记忆置信度，倾向于信任逻辑复核
    if logic_confidence > memory_confidence + 0.1:
        action = "contradict"
        reason = "逻辑复核置信度更高，记忆可能有误"
    elif memory_confidence > logic_confidence + 0.2:
        action = "confirm"
        reason = "记忆置信度显著更高，保持记忆"
    else:
        action = "flag_for_review"
        reason = "置信度接近，需要人工审查"
    
    return {
        "action": action,
        "reason": reason,
        "memory_id": memory_entry.memory_id,
        "logic_confidence": logic_confidence,
        "memory_confidence": memory_confidence,
    }
```

## LLM Prompt 设计

### 评分映射 Prompt（强制引用）

```
你是一个专业的批改助手。请根据评分标准逐条评分，并**必须**引用具体的评分标准条目。

## 评分标准
{rubric_json}

## 学生答案
{student_answer}

## 输出要求
对每个得分点，你必须：
1. 引用具体的评分标准条目（如 "1.2.a" 或原文摘要）
2. 提供学生答案中的证据
3. 判断是否为另类解法

返回 JSON 格式：
{
  "scoring_results": [
    {
      "point_id": "1.1",
      "rubric_reference": "评分标准 1.1: xxx",  // 必须填写
      "citation_quality": "exact|partial|none",
      "evidence": "学生答案中的证据",
      "awarded": 2,
      "max_score": 2,
      "is_alternative_solution": false,
      "alternative_description": "",  // 如果是另类解法，描述解法
      "reasoning": "评分理由"
    }
  ],
  "total_score": 8,
  "max_score": 10
}

注意：
- 如果学生使用了另类解法但答案正确，仍然给分，但标记 is_alternative_solution: true
- 如果无法找到匹配的评分标准，rubric_reference 填 null，citation_quality 填 "none"
```

## 接口设计

### 1. 记忆管理 API

```python
# GET /api/memory/stats
# 获取记忆统计
{
    "total_count": 1234,
    "by_status": {
        "pending": 500,
        "verified": 600,
        "core": 100,
        "suspicious": 34
    },
    "by_subject": {
        "economics": 400,
        "mathematics": 300,
        ...
    },
    "avg_confidence": 0.72
}

# GET /api/memory/list?subject=economics&status=verified&limit=20
# 查询记忆列表

# POST /api/memory/{memory_id}/verify
# 手动验证记忆
{
    "action": "verify|reject|promote_to_core",
    "reason": "验证理由"
}

# DELETE /api/memory/{memory_id}
# 软删除记忆
{
    "reason": "删除理由"
}

# POST /api/memory/{memory_id}/rollback
# 回滚记忆到之前状态
```

### 2. 自白增强 API

```python
# GET /api/grading/{batch_id}/self-report
# 获取批改自白（增强版）
{
    "batch_id": "xxx",
    "overall_status": "needs_review",
    "issues": [
        {
            "issue_id": "issue_001",
            "type": "alternative_solution",
            "severity": "warning",
            "question_id": "Q1",
            "point_id": "1.2",
            "message": "学生使用了另类解法",
            "suggestion": "建议人工确认解法是否有效",
            "rubric_reference": "1.2.a",
            "should_create_memory": true,
            "memory_created": true,
            "memory_id": "mem_xxx"
        }
    ],
    "memory_updates": [
        {
            "memory_id": "mem_xxx",
            "action": "created|confirmed|contradicted",
            "pattern": "xxx"
        }
    ]
}
```

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/models/grading_models.py` | 修改 | 扩展 ScoringPointResult |
| `src/services/grading_memory.py` | 修改 | 添加验证状态、软删除、回滚 |
| `src/services/grading_self_report.py` | 修改 | 添加记忆更新逻辑 |
| `src/services/llm_reasoning.py` | 修改 | 更新 prompt，强制引用 |
| `src/services/confidence_calculator.py` | 新增 | 置信度计算服务 |
| `src/api/routes/memory_api.py` | 新增 | 记忆管理 API |
| `tests/unit/test_confidence_calculator.py` | 新增 | 置信度计算测试 |
| `tests/unit/test_memory_verification.py` | 新增 | 记忆验证测试 |

## 正确性属性

### P1: 置信度计算正确性
```
对于任意得分点结果 r:
  - 如果 r.rubric_reference 为 null，则 r.point_confidence <= 0.7
  - 如果 r.is_alternative_solution 为 true，则 r.point_confidence <= 0.75
  - r.point_confidence 始终在 [0, 1] 范围内
```

### P2: 记忆状态转换正确性
```
记忆状态只能按以下路径转换：
  PENDING → VERIFIED → CORE
  PENDING → SUSPICIOUS → DEPRECATED
  VERIFIED → SUSPICIOUS（当 contradiction_count 过高时）
  任意状态 → DEPRECATED（软删除）
```

### P3: 逻辑复核独立性
```
逻辑复核函数 logic_review(result, rubric) 的输出
不依赖于任何 MemoryEntry 或 GradingMemoryService 的状态
```

### P4: 自白-记忆一致性
```
对于自白中标记 should_create_memory=true 的问题：
  - 必须在 memory_updates 中有对应的记录
  - 记录的 action 为 "created" 或 "confirmed"
```
