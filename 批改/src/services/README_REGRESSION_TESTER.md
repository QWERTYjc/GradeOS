# 回归测试器服务 (RegressionTester)

## 概述

回归测试器负责在评测集上验证规则补丁的有效性，确保补丁能够改进批改质量而不引入新的问题。

## 核心功能

### 1. 运行回归测试 (`run_regression`)

在评测集上对比应用补丁前后的批改结果：

```python
from src.services.regression_tester import get_regression_tester
from src.models.rule_patch import RulePatch, PatchType

# 创建补丁
patch = RulePatch(
    patch_type=PatchType.RULE,
    version="v1.0.0",
    description="添加单位换算规则",
    content={"rule_type": "unit_conversion"},
    source_pattern_id="pattern_001"
)

# 运行回归测试
tester = get_regression_tester()
result = await tester.run_regression(
    patch=patch,
    eval_set_id="eval_001"
)

print(f"测试结果：{'通过' if result.passed else '未通过'}")
print(f"误判率：{result.old_error_rate:.2%} -> {result.new_error_rate:.2%}")
print(f"漏判率：{result.old_miss_rate:.2%} -> {result.new_miss_rate:.2%}")
print(f"复核率：{result.old_review_rate:.2%} -> {result.new_review_rate:.2%}")
```

### 2. 判断是否为改进 (`is_improvement`)

根据指标变化判断补丁是否真正改进了批改质量：

```python
# 判断改进
is_better = tester.is_improvement(
    old_error_rate=0.15,
    new_error_rate=0.08,
    old_miss_rate=0.10,
    new_miss_rate=0.05,
    old_review_rate=0.20,
    new_review_rate=0.12,
    degraded_samples=3,
    total_samples=100
)

print(f"是否改进：{is_better}")
```

## 改进判断标准

补丁被认为是改进需要满足以下所有条件：

1. **无恶化**：误判率、漏判率、复核率都不能上升
2. **显著改进**：至少有一项指标下降超过阈值（默认 5%）
3. **退化可控**：退化样本比例不超过最大允许值（默认 2%）

## 评测指标

### 误判率 (Error Rate)

预测分数与标准分数差异超过阈值的样本比例：

```
误判率 = 误判样本数 / 总样本数
```

### 漏判率 (Miss Rate)

应该扣分但预测给了满分的样本比例：

```
漏判率 = 漏判样本数 / 总样本数
```

### 复核率 (Review Rate)

置信度低于阈值需要人工复核的样本比例：

```
复核率 = 低置信度样本数 / 总样本数
```

## 配置参数

```python
tester = RegressionTester(
    improvement_threshold=0.05,  # 改进阈值（5%）
    max_degradation_rate=0.02    # 最大退化率（2%）
)
```

## 评测集格式

评测集应包含以下字段：

```python
{
    "sample_id": "sample_001",
    "question_id": "q1",
    "student_answer": "x = 5",
    "ground_truth_score": 8.5,
    "ground_truth_feedback": "计算正确，步骤清晰",
    "max_score": 10.0
}
```

## 测试结果

回归测试返回 `RegressionResult` 对象：

```python
{
    "patch_id": "patch_001",
    "passed": True,
    "old_error_rate": 0.15,
    "new_error_rate": 0.08,
    "old_miss_rate": 0.10,
    "new_miss_rate": 0.05,
    "old_review_rate": 0.20,
    "new_review_rate": 0.12,
    "total_samples": 100,
    "improved_samples": 25,
    "degraded_samples": 3,
    "eval_set_id": "eval_001",
    "tested_at": "2025-12-20T14:00:00Z"
}
```

## 工作流程

```mermaid
graph LR
    A[加载评测集] --> B[运行旧版本批改]
    B --> C[运行新版本批改]
    C --> D[计算指标]
    D --> E[对比样本变化]
    E --> F[判断是否改进]
    F --> G[返回测试结果]
```

## 注意事项

1. **评测集质量**：评测集应该包含足够多的样本，覆盖各种题型和错误模式
2. **标注准确性**：ground_truth_score 应该由专业教师标注，确保准确性
3. **阈值调整**：根据实际情况调整 improvement_threshold 和 max_degradation_rate
4. **性能考虑**：大规模评测集可能需要较长时间，考虑使用批处理或并行执行

## 验证需求

- **需求 9.3**：生成候选补丁后，必须在评测集上运行回归测试
- **需求 9.4**：回归测试通过且误判率下降，补丁才能加入灰度发布队列

