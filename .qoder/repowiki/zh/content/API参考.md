# API参考

<cite>
**本文档引用的文件**
- [API_REFERENCE.md](file://ai_correction/docs/API_REFERENCE.md)
- [main.py](file://ai_correction/main.py)
- [test_multimodal_grading.py](file://ai_correction/test_multimodal_grading.py)
- [workflow_multimodal.py](file://ai_correction/functions/langgraph/workflow_multimodal.py)
- [langgraph_integration.py](file://ai_correction/functions/langgraph_integration.py)
- [state.py](file://ai_correction/functions/langgraph/state.py)
- [correction_service.py](file://ai_correction/functions/correction_service.py)
- [config.py](file://ai_correction/config.py)
- [redis_cache_session.md](file://ai_correction/docs/redis_cache_session.md)
- [ai_agent_implementation_summary.md](file://ai_correction/docs/ai_agent_implementation_summary.md)
</cite>

## 目录
1. [核心异步批改函数](#核心异步批改函数)
2. [HTTP API端点](#http-api端点)
3. [内部模块公共接口](#内部模块公共接口)
4. [数据模型](#数据模型)
5. [客户端调用示例](#客户端调用示例)
6. [错误处理](#错误处理)

## 核心异步批改函数

`run_multimodal_grading` 是系统的核心异步批改函数，用于执行多模态批改工作流。该函数提供便捷的接口来启动批改任务，并返回批改结果。

**函数签名**:
```python
async def run_multimodal_grading(
    task_id: str,
    user_id: str,
    question_files: list,
    answer_files: list,
    marking_files: list,
    strictness_level: str = "中等",
    language: str = "zh"
) -> Dict[str, Any]
```

**参数说明**:
- `task_id`: 任务唯一标识符，用于跟踪和查询批改进度
- `user_id`: 用户ID，标识发起批改的用户
- `question_files`: 题目文件路径列表，包含题目内容的文件
- `answer_files`: 答案文件路径列表，包含学生答案的文件
- `marking_files`: 评分标准文件路径列表，包含评分细则的文件
- `strictness_level`: 批改严格程度，可选值为"宽松"、"中等"、"严格"
- `language`: 输出语言，可选值为"zh"(中文)或"en"(英文)

**返回值结构**:
```python
{
    'task_id': str,
    'status': str,
    'total_score': float,
    'grade_level': str,
    'detailed_feedback': List[Dict],
    'criteria_evaluations': List[Dict],
    'errors': List[Dict],
    'warnings': List[Dict]
}
```

**可能抛出的异常**:
- `Exception`: 当工作流执行失败时抛出，包含详细的错误信息
- `ValueError`: 当输入参数无效时抛出
- `FileNotFoundError`: 当指定的文件路径不存在时抛出

**函数执行流程**:
1. 创建初始状态对象 `GradingState`
2. 获取多模态工作流实例
3. 执行工作流并获取最终状态
4. 返回格式化的批改结果

**Section sources**
- [workflow_multimodal.py](file://ai_correction/functions/langgraph/workflow_multimodal.py#L268-L372)

## HTTP API端点

系统提供RESTful API端点，支持外部系统集成。所有API端点遵循RESTful规范，使用JSON格式进行数据交换。

### 认证方式
API使用Bearer Token进行认证，需要在请求头中包含Authorization字段：
```
Authorization: Bearer <your_api_key>
```

### API端点列表

#### 健康检查
- **URL**: `/health/redis`
- **HTTP方法**: GET
- **请求头**: 无特殊要求
- **请求体**: 无
- **响应格式**:
```json
{
    "redis": "healthy" | "unhealthy"
}
```
- **状态码**:
  - 200: 健康检查成功
  - 500: 服务异常

#### 批改任务提交
- **URL**: `/api/correction/submit`
- **HTTP方法**: POST
- **请求头**:
  - `Authorization`: Bearer Token
  - `Content-Type`: application/json
- **请求体JSON Schema**:
```json
{
    "task_id": "string",
    "files": ["string"],
    "mode": "auto" | "efficient" | "professional",
    "strictness": "宽松" | "中等" | "严格",
    "language": "zh" | "en"
}
```
- **响应格式**:
```json
{
    "task_id": "string",
    "status": "pending" | "processing" | "completed" | "failed",
    "phase": "uploading" | "analyzing" | "correcting" | "generating" | "completed",
    "progress": 0-100,
    "created_at": "string",
    "result": "string",
    "error": "string"
}
```
- **状态码**:
  - 200: 任务提交成功
  - 400: 请求参数错误
  - 401: 认证失败
  - 500: 服务器内部错误

#### 任务状态查询
- **URL**: `/api/correction/status/{task_id}`
- **HTTP方法**: GET
- **请求头**:
  - `Authorization`: Bearer Token
- **请求体**: 无
- **响应格式**:
```json
{
    "task_id": "string",
    "status": "pending" | "processing" | "completed" | "failed",
    "phase": "uploading" | "analyzing" | "correcting" | "generating" | "completed",
    "progress": 0-100,
    "created_at": "string",
    "started_at": "string",
    "completed_at": "string",
    "result": "string",
    "error": "string"
}
```
- **状态码**:
  - 200: 查询成功
  - 404: 任务不存在
  - 401: 认证失败

**Section sources**
- [redis_cache_session.md](file://ai_correction/docs/redis_cache_session.md#L353-L403)
- [ai_agent_implementation_summary.md](file://ai_correction/docs/ai_agent_implementation_summary.md#L83-L113)
- [correction_service.py](file://ai_correction/functions/correction_service.py#L181-L196)

## 内部模块公共接口

系统内部模块间的公共接口定义了Agent之间的数据传递协议和交互方式。

### LangGraph集成接口
`LangGraphIntegration` 类提供了与现有Streamlit应用的集成接口，确保新旧系统之间的兼容性。

**类定义**:
```python
class LangGraphIntegration:
    def __init__(self)
    async def intelligent_correction_with_langgraph(
        self,
        question_files: List[str],
        answer_files: List[str],
        marking_scheme_files: Optional[List[str]] = None,
        strictness_level: str = "中等",
        language: str = "zh",
        mode: str = "auto",
        user_id: str = "default_user"
    ) -> Dict[str, Any]
    def _convert_to_compatible_format(self, langgraph_result: Dict[str, Any]) -> Dict[str, Any]
    async def get_task_progress(self, task_id: str) -> Dict[str, Any]
    def get_active_tasks(self) -> Dict[str, Any]
    def cleanup_completed_tasks(self, max_age_hours: int = 24)
```

**数据传递协议**:
- 使用 `GradingState` 对象作为状态传递的载体
- 各Agent通过修改状态对象中的特定字段来传递数据
- 支持异步调用和进度更新

**Section sources**
- [langgraph_integration.py](file://ai_correction/functions/langgraph_integration.py#L19-L208)

## 数据模型

### GradingState
`GradingState` 是系统的核心数据模型，定义了批改过程中的所有状态信息。

```python
class GradingState(TypedDict):
    # 基础任务信息
    task_id: str
    user_id: str
    assignment_id: str
    timestamp: datetime
    
    # 文件信息
    question_files: List[str]
    answer_files: List[str]
    marking_files: List[str]
    images: List[str]
    
    # 多模态文件信息
    question_multimodal_files: List[Dict[str, Any]]
    answer_multimodal_files: List[Dict[str, Any]]
    marking_multimodal_files: List[Dict[str, Any]]
    
    # 批改参数
    strictness_level: str
    language: str
    mode: str
    
    # 多模态提取结果
    mm_tokens: List[Dict[str, Any]]
    student_info: Dict[str, Any]
    
    # 评分标准解析
    rubric_text: str
    rubric_struct: Dict[str, Any]
    rubric_data: Dict[str, Any]
    scoring_criteria: List[Dict]
    
    # 理解结果
    question_understanding: Optional[Dict[str, Any]]
    answer_understanding: Optional[Dict[str, Any]]
    rubric_understanding: Optional[Dict[str, Any]]
    
    # 题目识别与批次规划
    questions: List[Dict[str, Any]]
    batches: List[Dict[str, Any]]
    
    # AI评分结果
    evaluations: List[Dict[str, Any]]
    scoring_results: Dict[str, Any]
    detailed_feedback: List[Dict]
    
    # 基于标准的评估结果
    criteria_evaluations: List[Dict[str, Any]]
    
    # 坐标标注
    annotations: List[Dict[str, Any]]
    coordinate_annotations: List[Dict]
    error_regions: List[Dict]
    cropped_regions: List[Dict]
    
    # 知识点挖掘
    knowledge_points: List[Dict]
    error_analysis: Dict[str, Any]
    learning_suggestions: List[str]
    difficulty_assessment: Dict[str, Any]
    
    # 专业模式扩展字段
    total_score: float
    section_scores: Dict[str, float]
    student_evaluation: Dict[str, Any]
    class_evaluation: Dict[str, Any]
    
    # 导出与集成
    export_payload: Dict[str, Any]
    final_report: Dict[str, Any]
    export_data: Dict[str, Any]
    visualization_data: Dict[str, Any]
    
    # 深度协作相关字段
    students_info: List[Any]
    batches_info: List[Any]
    batch_rubric_packages: Dict[str, Any]
    question_context_packages: Dict[str, Any]
    grading_results: List[Dict[str, Any]]
    student_reports: List[Dict[str, Any]]
    class_analysis: Dict[str, Any]
    
    # 处理状态
    current_step: str
    progress_percentage: float
    completion_status: str
    completed_at: str
    
    # 错误和步骤记录
    errors: List[Dict[str, Any]]
    step_results: Dict[str, Any]
    
    # 最终结果
    final_score: float
    grade_level: str
    warnings: List[str]
    
    # 元数据
    processing_time: float
    model_versions: Dict[str, str]
    quality_metrics: Dict[str, float]
```

**Section sources**
- [state.py](file://ai_correction/functions/langgraph/state.py#L0-L268)

## 客户端调用示例

以下Python代码示例展示了如何从外部系统集成此批改服务。

```python
import asyncio
import os
from pathlib import Path

# 导入必要的模块
from functions.langgraph.workflow_multimodal import run_multimodal_grading

async def main():
    """
    客户端调用示例：使用多模态批改系统
    """
    # 准备测试数据路径
    test_data_dir = Path(__file__).parent / "test_data_debug"
    test_data_dir.mkdir(exist_ok=True)
    
    # 创建测试文件
    question_file = test_data_dir / "question.txt"
    answer_file = test_data_dir / "answer.txt"
    marking_file = test_data_dir / "marking.txt"
    
    # 写入测试数据
    question_file.write_text("请解释什么是三角形。", encoding='utf-8')
    
    answer_file.write_text("""三角形是由三条边组成的封闭图形。
它是几何学中最基本的图形之一。
三角形具有稳定性，在建筑和工程中应用广泛。""", encoding='utf-8')
    
    marking_file.write_text("""评分标准（总分10分）：
1. 说明三角形的定义 (3分)
2. 指出三角形有三条边 (2分)
3. 提到三角形是封闭图形 (2分)
4. 说明三角形有三个角 (3分)""", encoding='utf-8')
    
    # 运行批改
    result = await run_multimodal_grading(
        task_id="test_001",
        user_id="test_user",
        question_files=[str(question_file)],
        answer_files=[str(answer_file)],
        marking_files=[str(marking_file)],
        strictness_level="中等",
        language="zh"
    )
    
    # 输出结果
    print(f"任务ID: {result['task_id']}")
    print(f"状态: {result['status']}")
    print(f"总分: {result['total_score']}")
    print(f"等级: {result['grade_level']}")
    
    # 验证结果
    total_score = result['total_score']
    if total_score < 10.0:
        print("✅ 测试通过！系统正确识别出学生未提及'三个角'，没有给满分")
    else:
        print("❌ 测试失败！学生得分不应该是满分")

if __name__ == '__main__':
    asyncio.run(main())
```

**Section sources**
- [test_multimodal_grading.py](file://ai_correction/test_multimodal_grading.py#L0-L165)

## 错误处理

系统采用统一的错误处理机制，确保错误信息的一致性和可读性。

### 错误格式
所有错误都遵循以下标准格式：
```python
error = {
    'step': str,  # 错误发生的步骤
    'error': str,  # 错误信息
    'timestamp': str  # 时间戳
}
```

### 错误处理策略
- **优雅降级**: 当缓存服务不可用时，自动降级到数据库查询
- **重试机制**: 对于临时性错误，系统会自动重试
- **详细日志**: 所有错误都会记录详细的日志信息，便于排查问题
- **用户友好**: 向用户展示友好的错误信息，避免暴露敏感信息

### 常见错误类型
- `CacheError`: 缓存服务错误
- `DatabaseError`: 数据库连接错误
- `FileNotFoundError`: 文件不存在
- `ValidationError`: 输入参数验证失败
- `ProcessingError`: 批改处理过程中出现的错误

**Section sources**
- [API_REFERENCE.md](file://ai_correction/docs/API_REFERENCE.md#L180-L204)
- [redis_cache_session.md](file://ai_correction/docs/redis_cache_session.md#L300-L353)