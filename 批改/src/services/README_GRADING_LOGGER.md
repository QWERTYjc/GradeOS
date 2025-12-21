# 批改日志服务 (GradingLogger)

批改日志服务用于记录批改过程的完整上下文，支持改判记录、日志查询和容错处理。

## 功能概述

### 1. 批改日志记录

记录批改过程各阶段的详细信息：

- **提取阶段**: extracted_answer, extraction_confidence, evidence_snippets
- **规范化阶段**: normalized_answer, normalization_rules_applied
- **匹配阶段**: match_result, match_failure_reason
- **评分阶段**: score, max_score, confidence, reasoning_trace

### 2. 改判日志记录

当教师对批改结果进行改判时，记录：

- was_overridden: 改判标记
- override_score: 改判后的分数
- override_reason: 改判原因
- override_teacher_id: 改判教师ID
- override_at: 改判时间

### 3. 改判样本查询

支持查询指定时间窗口内的改判记录，用于：

- 规则挖掘和失败模式分析
- 生成规则补丁
- 系统自我成长

### 4. 日志写入容错

- 数据库写入失败时，日志自动暂存到本地队列
- 支持批量刷新暂存日志
- 确保日志不丢失

## 使用方法

### 基本使用

```python
from src.services.grading_logger import get_grading_logger
from src.models.grading_log import GradingLog

# 获取日志服务实例
logger = get_grading_logger()

# 创建批改日志
log = GradingLog(
    submission_id="sub_001",
    question_id="q1",
    extracted_answer="x = 5",
    extraction_confidence=0.95,
    score=8.5,
    max_score=10.0,
    confidence=0.92,
    reasoning_trace=["步骤1", "步骤2"]
)

# 记录日志
log_id = await logger.log_grading(log)
```

### 记录改判

```python
# 记录教师改判
success = await logger.log_override(
    log_id="log_001",
    override_score=9.0,
    override_reason="学生答案正确，只是表达方式不同",
    teacher_id="teacher_001"
)
```

### 查询改判样本

```python
# 查询最近 7 天内的 100 条改判样本
samples = await logger.get_override_samples(
    min_count=100,
    days=7
)

for sample in samples:
    print(f"题目: {sample.question_id}")
    print(f"原始分数: {sample.score}")
    print(f"改判分数: {sample.override_score}")
    print(f"改判原因: {sample.override_reason}")
```

### 容错处理

```python
# 检查暂存队列
pending_count = logger.get_pending_count()
print(f"暂存日志数量: {pending_count}")

# 刷新暂存日志
success_count = await logger.flush_pending()
print(f"成功写入 {success_count} 条日志")
```

## 数据模型

### GradingLog

完整的批改日志模型，包含：

```python
class GradingLog(BaseModel):
    log_id: str
    submission_id: str
    question_id: str
    
    # 提取阶段
    extracted_answer: Optional[str]
    extraction_confidence: Optional[float]
    evidence_snippets: Optional[List[str]]
    
    # 规范化阶段
    normalized_answer: Optional[str]
    normalization_rules_applied: Optional[List[str]]
    
    # 匹配阶段
    match_result: Optional[bool]
    match_failure_reason: Optional[str]
    
    # 评分阶段
    score: Optional[float]
    max_score: Optional[float]
    confidence: Optional[float]
    reasoning_trace: Optional[List[str]]
    
    # 改判信息
    was_overridden: bool = False
    override_score: Optional[float]
    override_reason: Optional[str]
    override_teacher_id: Optional[str]
    override_at: Optional[datetime]
    
    created_at: datetime
```

### GradingLogOverride

改判信息模型：

```python
class GradingLogOverride(BaseModel):
    override_score: float
    override_reason: str
    override_teacher_id: str
```

## 数据库表结构

### grading_logs 表

```sql
CREATE TABLE grading_logs (
    log_id UUID PRIMARY KEY,
    submission_id UUID NOT NULL,
    question_id VARCHAR(50) NOT NULL,
    
    -- 提取阶段
    extracted_answer TEXT,
    extraction_confidence NUMERIC(3, 2),
    evidence_snippets JSONB,
    
    -- 规范化阶段
    normalized_answer TEXT,
    normalization_rules_applied JSONB,
    
    -- 匹配阶段
    match_result BOOLEAN,
    match_failure_reason TEXT,
    
    -- 评分阶段
    score NUMERIC(5, 2),
    max_score NUMERIC(5, 2),
    confidence NUMERIC(3, 2),
    reasoning_trace JSONB,
    
    -- 改判信息
    was_overridden BOOLEAN DEFAULT FALSE,
    override_score NUMERIC(5, 2),
    override_reason TEXT,
    override_teacher_id UUID,
    override_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_grading_logs_submission ON grading_logs(submission_id);
CREATE INDEX idx_grading_logs_override ON grading_logs(was_overridden) WHERE was_overridden = TRUE;
CREATE INDEX idx_grading_logs_created ON grading_logs(created_at);
```

## 正确性属性

### Property 18: 批改日志完整性

对于任意完成的批改，日志应包含：
- extracted_answer
- extraction_confidence
- score
- confidence
- reasoning_trace

**验证**: Requirements 8.1, 8.2, 8.3

### Property 19: 改判日志完整性

对于任意老师改判，日志应更新：
- was_overridden=True
- override_score
- override_reason
- override_teacher_id

**验证**: Requirements 8.4

### Property 20: 日志写入容错

对于任意日志写入失败，日志应被暂存并在恢复后重试，不应丢失。

**验证**: Requirements 8.5

## 测试

### 属性测试

```bash
# 批改日志完整性
pytest tests/property/test_grading_log_completeness.py -v

# 改判日志完整性
pytest tests/property/test_override_log_completeness.py -v

# 日志写入容错
pytest tests/property/test_log_write_fault_tolerance.py -v
```

### 单元测试

```bash
pytest tests/unit/test_grading_logger.py -v
```

## 示例代码

完整的使用示例请参考：`examples/grading_logger_example.py`

## 注意事项

1. **数据库连接**: 日志服务依赖数据库连接，确保数据库配置正确
2. **容错机制**: 写入失败时日志会暂存到本地队列，定期调用 `flush_pending()` 重试
3. **队列容量**: 暂存队列有最大容量限制（默认 1000），超出时会移除最旧的日志
4. **改判完整性**: 改判时必须提供完整的改判信息（分数、原因、教师ID）
5. **时区处理**: 所有时间戳使用 UTC 时区

## 相关文档

- [设计文档](../../.kiro/specs/self-evolving-grading/design.md)
- [需求文档](../../.kiro/specs/self-evolving-grading/requirements.md)
- [任务列表](../../.kiro/specs/self-evolving-grading/tasks.md)
