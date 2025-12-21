# 学生边界检测器文档

## 概述

学生边界检测器（StudentBoundaryDetector）是自我成长批改系统的核心组件之一，负责从批改结果中智能识别学生边界，支持多学生合卷场景。

## 核心功能

### 1. 多策略检测

系统支持两种主要检测策略：

#### 策略1：基于学生标识
- 从批改结果中提取学生姓名、学号等标识信息
- 通过标识变化检测学生边界
- 适用于有明确学生信息的场景

#### 策略2：基于题目循环
- 分析题目编号的循环模式
- 当题目编号从大变小（如从5回到1）时，推断换了学生
- 适用于无学生标识但题目顺序规律的场景

### 2. 置信度计算

系统综合考虑多个因素计算边界置信度：

1. **学生标识置信度**：原始学生信息的可靠程度
2. **题目序列连续性**：题目编号是否连续递增
3. **边界清晰度**：边界处是否有明确的学生标识变化

### 3. 低置信度标记

- 默认阈值：0.8
- 当边界置信度 < 0.8 时，自动标记 `needs_confirmation = True`
- 支持自定义阈值

## 数据模型

### StudentBoundary

```python
@dataclass
class StudentBoundary:
    student_key: str              # 学生标识（姓名/学号/代号）
    start_page: int               # 起始页码（从0开始）
    end_page: int                 # 结束页码（包含）
    confidence: float             # 置信度 (0.0-1.0)
    needs_confirmation: bool      # 是否需要人工确认
    student_info: Optional[StudentInfo]  # 学生详细信息
    detection_method: str         # 检测方法：student_info, question_cycle, hybrid
```

### BoundaryDetectionResult

```python
@dataclass
class BoundaryDetectionResult:
    boundaries: List[StudentBoundary]  # 检测到的学生边界
    total_students: int                # 学生总数
    unassigned_pages: List[int]        # 未分配的页面
    detection_timestamp: datetime      # 检测时间戳
    total_pages: int                   # 总页数
```

## 使用方法

### 基本用法

```python
from src.services.student_boundary_detector import StudentBoundaryDetector

# 创建检测器
detector = StudentBoundaryDetector(confidence_threshold=0.8)

# 准备批改结果
grading_results = [
    {
        "page_index": 0,
        "question_id": "1",
        "student_info": {
            "name": "张三",
            "student_id": "2024001",
            "confidence": 0.95
        }
    },
    # ... 更多页面
]

# 执行检测
result = await detector.detect_boundaries(grading_results)

# 处理结果
for boundary in result.boundaries:
    print(f"学生: {boundary.student_key}")
    print(f"页面范围: {boundary.start_page} - {boundary.end_page}")
    print(f"置信度: {boundary.confidence}")
    if boundary.needs_confirmation:
        print("⚠️ 需要人工确认")
```

### 自定义置信度阈值

```python
# 使用更严格的阈值
detector = StudentBoundaryDetector(confidence_threshold=0.9)

# 使用更宽松的阈值
detector = StudentBoundaryDetector(confidence_threshold=0.6)
```

### 集成 StudentIdentificationService

```python
from src.services.student_identification import StudentIdentificationService

# 创建学生识别服务
student_service = StudentIdentificationService(api_key="your_api_key")

# 创建检测器并集成服务
detector = StudentBoundaryDetector(
    student_identification_service=student_service,
    confidence_threshold=0.8
)
```

## 输入数据格式

检测器支持多种批改结果格式：

### 格式1：包含 student_info 字段

```python
{
    "page_index": 0,
    "question_id": "1",
    "student_info": {
        "name": "张三",
        "student_id": "2024001",
        "confidence": 0.95
    }
}
```

### 格式2：包含 metadata 字段

```python
{
    "page_index": 0,
    "question_id": "1",
    "metadata": {
        "student_name": "张三",
        "student_id": "2024001",
        "student_confidence": 0.95
    }
}
```

### 格式3：包含 agent_trace 字段

```python
{
    "page_index": 0,
    "question_id": "1",
    "agent_trace": {
        "student_identification": {
            "name": "张三",
            "student_id": "2024001",
            "confidence": 0.95
        }
    }
}
```

### 格式4：仅包含题目信息

```python
{
    "page_index": 0,
    "question_id": "1",
    "question_numbers": ["1", "2"]
}
```

## 检测逻辑

### 学生标识提取

1. 遍历所有批改结果
2. 从多个可能的字段中提取学生信息
3. 过滤置信度 < 0.6 的学生信息
4. 构建页码到学生信息的映射

### 题目循环检测

1. 提取每页的题目编号
2. 标准化题目编号（如 "Question 1" → "1"）
3. 检测题目编号的回退（如 5 → 1）
4. 在回退点标记新学生的开始

### 置信度计算

```python
综合置信度 = (学生标识置信度 + 题目连续性得分 + 边界清晰度得分) / 3
```

- **学生标识置信度**：直接使用原始置信度
- **题目连续性得分**：相邻题目编号差值为1的比例
- **边界清晰度得分**：
  - 起始页有明确学生标识：0.9
  - 前一页有不同学生标识：0.8
  - 默认：0.6

## 测试

### 属性测试

系统包含以下属性测试：

1. **Property 5**：边界检测触发 - 验证检测总是被触发并产生结果
2. **Property 6**：边界标记正确性 - 验证 start_page ≤ end_page 且边界不重叠
3. **Property 7**：低置信度边界标记 - 验证置信度 < 0.8 时 needs_confirmation = True

### 单元测试

- 低置信度边界标记
- 置信度阈值自定义
- 学生标识提取
- 题目循环检测
- 置信度计算因素
- 检测方法跟踪

### 运行测试

```bash
# 运行所有测试
pytest tests/property/test_student_boundary_detection.py tests/unit/test_student_boundary_detector.py -v

# 运行属性测试
pytest tests/property/test_student_boundary_detection.py -v

# 运行单元测试
pytest tests/unit/test_student_boundary_detector.py -v
```

## 示例

完整示例请参考：`examples/student_boundary_detection_example.py`

```bash
python examples/student_boundary_detection_example.py
```

## 性能考虑

- 时间复杂度：O(n)，其中 n 是页面数量
- 空间复杂度：O(n)
- 适用于大规模批改场景（数千页）

## 未来改进

1. 支持更多检测策略（如基于页面布局相似度）
2. 机器学习模型优化置信度计算
3. 支持增量检测（流式处理）
4. 多语言支持（当前主要支持中文和英文）

## 相关文档

- [需求文档](../.kiro/specs/self-evolving-grading/requirements.md)
- [设计文档](../.kiro/specs/self-evolving-grading/design.md)
- [任务列表](../.kiro/specs/self-evolving-grading/tasks.md)
- [学生识别服务](../src/services/student_identification.py)
