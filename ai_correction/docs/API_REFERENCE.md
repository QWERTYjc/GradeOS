# AI批改系统 - API参考文档

## 核心API

### 1. 运行生产批改

```python
async def run_production_grading(
    task_id: str,
    user_id: str,
    question_files: List[str],
    answer_files: List[str],
    marking_files: List[str] = None,
    mode: str = "professional"
) -> Dict[str, Any]
```

**参数**:
- `task_id`: 任务唯一标识
- `user_id`: 用户ID
- `question_files`: 题目文件路径列表
- `answer_files`: 答案文件路径列表
- `marking_files`: 评分标准文件路径列表（可选）
- `mode`: 批改模式 ("efficient" | "professional")

**返回**:
```python
{
    'task_id': str,
    'total_score': float,
    'max_score': float,
    'grade_level': str,  # A, B, C, D, F
    'evaluations': List[Dict],
    'annotations': List[Dict],
    'student_evaluation': Dict,
    'export_payload': Dict,
    'push_status': str,
    'errors': List[Dict]
}
```

### 2. Agent API

#### 2.1 OrchestratorAgent

```python
from functions.langgraph.agents.orchestrator import create_orchestrator_agent

orchestrator = create_orchestrator_agent()
sends = orchestrator(state)
```

#### 2.2 StudentEvaluationGenerator

```python
from functions.langgraph.agents.student_evaluation_generator import create_student_evaluation_generator

generator = create_student_evaluation_generator()
evaluation = generator.generate_evaluation(state)
```

#### 2.3 ClassEvaluationGenerator

```python
from functions.langgraph.agents.class_evaluation_generator import create_class_evaluation_generator

generator = create_class_evaluation_generator()
class_eval = generator.generate_evaluation(student_results, assignment_info)
```

### 3. 数据库API

#### 3.1 学生匹配

```python
from functions.database.student_matcher import StudentMatcher

matcher = StudentMatcher(db_session, similarity_threshold=0.75)
student, confidence, match_type = matcher.match_student(
    {'name': '张三', 'student_id': '20210001'},
    class_id='class_001'
)
```

#### 3.2 数据库迁移

```python
from functions.database.migration import DatabaseMigrationManager

manager = DatabaseMigrationManager(database_url)
manager.create_migration("添加新表")
manager.upgrade()
```

### 4. 工作流API

#### 4.1 流式监控

```python
from functions.langgraph.streaming import StreamingWorkflowRunner, ProgressMonitor

monitor = ProgressMonitor(callback=progress_callback)
runner = StreamingWorkflowRunner(workflow.graph, monitor)
result = await runner.run_with_progress(initial_state)
```

#### 4.2 Checkpoint管理

```python
from functions.langgraph.checkpointer import get_checkpointer

checkpointer = get_checkpointer('production')
graph = workflow.compile(checkpointer=checkpointer)
```

### 5. 提示词API

#### 5.1 高效模式

```python
from functions.langgraph.prompts.efficient_mode import build_efficient_prompt

prompt = build_efficient_prompt(question, rubric_struct, mm_tokens)
```

#### 5.2 专业模式

```python
from functions.langgraph.prompts.professional_mode import build_professional_prompt

prompt = build_professional_prompt(question, rubric_struct, mm_tokens)
```

## 数据模型

### GradingState

```python
class GradingState(TypedDict):
    task_id: str
    user_id: str
    mode: str  # efficient | professional
    mm_tokens: List[Dict]
    student_info: Dict
    questions: List[Dict]
    batches: List[Dict]
    evaluations: List[Dict]
    annotations: List[Dict]
    total_score: float
    grade_level: str
    student_evaluation: Dict
    export_payload: Dict
    errors: List[Dict]
```

### 评价数据

```python
evaluation = {
    'student_name': str,
    'total_score': float,
    'max_score': float,
    'percentage': float,
    'grade_level': str,
    'strengths': List[str],
    'weaknesses': List[str],
    'suggestions': List[str],
    'knowledge_points': List[str]
}
```

## 配置选项

### 环境变量

```bash
DATABASE_URL=sqlite:///ai_correction.db
OPENAI_API_KEY=your-key
ENVIRONMENT=development
DEFAULT_MODE=professional
EFFICIENT_MODE_THRESHOLD=6000
PROFESSIONAL_MODE_THRESHOLD=4000
MAX_PARALLEL_WORKERS=4
```

## 错误处理

所有Agent都返回标准错误格式：

```python
error = {
    'step': str,  # 错误发生的步骤
    'error': str,  # 错误信息
    'timestamp': str  # 时间戳
}
```

## 性能指标

| 指标 | 高效模式 | 专业模式 |
|------|---------|---------|
| Token/题 | ~500 | ~1500 |
| 处理时间 | 2秒 | 5秒 |
| 并行加速 | 6.7x | 6.7x |
