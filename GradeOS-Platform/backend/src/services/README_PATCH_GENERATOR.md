# 补丁生成器服务 (PatchGenerator)

## 概述

补丁生成器服务负责根据失败模式生成候选规则补丁。它是自动规则升级引擎的核心组件之一。

## 功能

### 1. 补丁生成 (`generate_patch`)

根据失败模式的类型和特征，生成对应的规则补丁：

- **提取阶段补丁**：优化提示词，增强答案提取能力
- **规范化阶段补丁**：扩展规范化规则，处理更多变体
- **匹配阶段补丁**：添加同义词规则，提高匹配成功率
- **评分阶段补丁**：调整评分规则（仅限可自动修复的情况）

## 使用示例

```python
from src.services.patch_generator import get_patch_generator
from src.models.failure_pattern import FailurePattern, PatternType

# 获取补丁生成器
generator = get_patch_generator()

# 创建失败模式
pattern = FailurePattern(
    pattern_type=PatternType.NORMALIZATION,
    description="规范化规则 'unit_conversion' 应用后仍然匹配失败",
    frequency=15,
    sample_log_ids=["log_001", "log_002"],
    confidence=0.85,
    is_fixable=True,
    error_signature="normalization_unit_conversion"
)

# 生成补丁
patch = await generator.generate_patch(pattern)

if patch:
    print(f"生成补丁：{patch.patch_id}")
    print(f"版本：{patch.version}")
    print(f"类型：{patch.patch_type}")
    print(f"描述：{patch.description}")
```

## 补丁类型

### 1. 规则补丁 (RULE)

用于扩展或修改批改规则：

```python
{
    "patch_target": "normalization_rules",
    "pattern_type": "normalization",
    "rule_name": "unit_conversion",
    "enhancement": {
        "type": "rule_extension",
        "description": "扩展规范化规则以处理更多变体",
        "new_variants": ["cm->m", "mm->cm", "kg->g"],
        "examples": [...]
    }
}
```

### 2. 提示词补丁 (PROMPT)

用于优化提示词：

```python
{
    "patch_target": "extraction_prompt",
    "pattern_type": "extraction",
    "affected_questions": ["Q1", "Q2"],
    "enhancement": {
        "type": "prompt_optimization",
        "description": "优化答案提取提示词",
        "prompt_additions": [
            "请特别注意答案区域的边界标记",
            "如果答案包含多个部分，请完整提取所有部分"
        ]
    }
}
```

### 3. 示例补丁 (EXEMPLAR)

用于添加新的判例示例（暂未实现）。

## 补丁生成策略

### 提取阶段

- **问题**：答案提取失败或置信度低
- **策略**：优化提示词，增加答案区域识别规则
- **补丁类型**：PROMPT

### 规范化阶段

- **问题**：规范化规则应用后仍然匹配失败
- **策略**：扩展规范化规则，添加更多变体
- **补丁类型**：RULE

### 匹配阶段

- **问题**：答案与标准答案匹配失败
- **策略**：添加同义词规则，放宽匹配条件
- **补丁类型**：RULE

### 评分阶段

- **问题**：评分偏差
- **策略**：调整评分规则（仅限明确的扣分错误）
- **补丁类型**：RULE
- **注意**：大多数评分失败需要人工介入

## 版本管理

补丁生成器自动分配版本号，格式为 `v1.0.N`：

- `v1`：版本前缀（可配置）
- `0`：主版本号（固定）
- `N`：补丁序号（自动递增）

## 工作流集成

补丁生成器在自动规则升级流程中的位置：

```
RuleMiner → PatchGenerator → RegressionTester → PatchDeployer
   ↓              ↓                  ↓                ↓
识别模式      生成补丁          回归测试         灰度发布
```

## 配置选项

```python
generator = PatchGenerator(
    version_prefix="v1"  # 版本号前缀
)
```

## 注意事项

1. **可修复性检查**：只有 `is_fixable=True` 的模式才会生成补丁
2. **评分补丁限制**：评分阶段的补丁生成非常保守，大多数情况需要人工介入
3. **版本号唯一性**：每次生成补丁都会分配新的版本号
4. **补丁内容格式**：不同类型的补丁有不同的内容格式，需要下游组件正确解析

## 相关组件

- `RuleMiner`：识别失败模式
- `RegressionTester`：测试补丁有效性
- `PatchDeployer`：部署补丁
- `VersionManager`：管理补丁版本

## 验证需求

- **需求 9.2**：识别到可修复的失败模式时生成候选规则补丁
