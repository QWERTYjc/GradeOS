# GradeOS Platform - 技术实现细节文档

**版本**: v2.0  
**最后更新**: 2025-12-27  
**作者**: AI Grading System Team

---

## 📚 目录

1. [架构概述](#架构概述)
2. [LangGraph 工作流](#langgraph-工作流)
3. [API 设计](#api-设计)
4. [前端集成](#前端集成)
5. [提示词优化](#提示词优化)
6. [错误处理](#错误处理)
7. [性能优化](#性能优化)

---

## 架构概述

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Console Page                                        │   │
│  │  ├─ File Upload Component                           │   │
│  │  ├─ Real-time Monitor                               │   │
│  │  └─ Results View                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Routes                                          │   │
│  │  ├─ /batch/submit (POST)                            │   │
│  │  ├─ /batch/status/{batch_id} (GET)                  │   │
│  │  └─ /batch/results/{batch_id} (GET)                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  LangGraph Orchestrator                              │   │
│  │  ├─ Graph Registry                                  │   │
│  │  ├─ Execution Engine                                │   │
│  │  └─ State Management                                │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Batch Grading Graph (LangGraph)                     │   │
│  │  ├─ Intake Node                                     │   │
│  │  ├─ Preprocess Node                                 │   │
│  │  ├─ Rubric Parse Node                               │   │
│  │  ├─ Grade Batch Node (Parallel)                     │   │
│  │  ├─ Segment Node                                    │   │
│  │  ├─ Review Node                                     │   │
│  │  └─ Export Node                                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Services                                            │   │
│  │  ├─ Gemini Reasoning Service                        │   │
│  │  ├─ Rubric Parser Service                           │   │
│  │  ├─ PDF Processing Service                          │   │
│  │  └─ Student Boundary Detection                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## LangGraph 工作流

### 工作流设计

```python
# 工作流顺序（优先级从高到低）
1. INTAKE
   - 接收上传的试卷和评分标准
   - 验证文件格式和大小
   - 初始化批处理状态

2. PREPROCESS
   - PDF 解析和页面提取
   - 图像识别和文本提取
   - 页面元数据收集

3. RUBRIC_PARSE
   - 评分标准 PDF 解析
   - 标准结构化处理
   - 评分点提取

4. GRADE_BATCH (并行处理)
   - 将试卷分配给多个 Worker
   - 每个 Worker 独立批改
   - 实时进度推送

5. SEGMENT
   - 学生边界检测
   - 答卷分段聚合
   - 学生身份识别

6. REVIEW
   - 结果一致性检查
   - 质量审核
   - 异常处理

7. EXPORT
   - 结果格式化
   - 数据持久化
   - 通知推送
```

### 节点实现

#### 1. Intake Node

```python
def intake_node(state: BatchGradingState) -> BatchGradingState:
    """
    接收和验证上传的文件
    
    输入:
    - exam_id: 考试 ID
    - files: 学生答卷 PDF 列表
    - rubrics: 评分标准 PDF 列表
    
    输出:
    - validated_files: 验证后的文件列表
    - total_pages: 总页数
    - status: UPLOADED
    """
    # 文件验证
    # 元数据收集
    # 状态初始化
    return state
```

#### 2. Preprocess Node

```python
def preprocess_node(state: BatchGradingState) -> BatchGradingState:
    """
    预处理试卷文件
    
    处理流程:
    1. PDF 解析
    2. 页面提取
    3. 图像识别
    4. 文本提取
    """
    # 使用 PyMuPDF (fitz) 解析 PDF
    # 提取每一页的图像和文本
    # 生成页面元数据
    return state
```

#### 3. Rubric Parse Node

```python
def rubric_parse_node(state: BatchGradingState) -> BatchGradingState:
    """
    解析评分标准
    
    处理流程:
    1. 读取评分标准 PDF
    2. 提取评分点
    3. 结构化处理
    4. 验证完整性
    """
    # 使用 Gemini 解析评分标准
    # 提取评分点和权重
    # 生成结构化标准
    return state
```

#### 4. Grade Batch Node (并行)

```python
def grade_batch_node(state: BatchGradingState) -> BatchGradingState:
    """
    并行批改学生答卷
    
    处理流程:
    1. 将试卷分配给 Worker
    2. 每个 Worker 独立批改
    3. 实时推送进度
    4. 收集批改结果
    
    并行策略:
    - Worker 数量: 3 (可配置)
    - 每个 Worker 处理的页数: total_pages / num_workers
    - 超时时间: 300 秒
    """
    # 创建 Worker 任务
    # 并行执行批改
    # 实时推送进度
    # 收集结果
    return state
```

#### 5. Segment Node

```python
def segment_node(state: BatchGradingState) -> BatchGradingState:
    """
    学生边界检测和答卷分段
    
    处理流程:
    1. 分析批改结果
    2. 检测学生边界
    3. 聚合学生答卷
    4. 生成学生结果
    
    边界检测算法:
    - 基于批改结果的学生识别
    - 置信度评估
    - 手动确认标记
    """
    # 分析批改结果
    # 检测学生边界
    # 聚合学生数据
    return state
```

#### 6. Review Node

```python
def review_node(state: BatchGradingState) -> BatchGradingState:
    """
    结果审核和质量检查
    
    检查项:
    1. 数据完整性
    2. 评分一致性
    3. 异常值检测
    4. 置信度评估
    """
    # 验证数据完整性
    # 检查评分一致性
    # 标记异常值
    return state
```

#### 7. Export Node

```python
def export_node(state: BatchGradingState) -> BatchGradingState:
    """
    结果导出和通知
    
    导出内容:
    1. 学生成绩
    2. 详细反馈
    3. 评分点详情
    4. 统计数据
    """
    # 格式化结果
    # 持久化数据
    # 推送通知
    return state
```

---

## API 设计

### 1. 批改提交 API

**端点**: `POST /batch/submit`

**请求**:
```json
{
  "exam_id": "exam_2025_001",
  "files": ["file1.pdf", "file2.pdf"],
  "rubrics": ["rubric.pdf"],
  "api_key": "gemini_api_key",
  "auto_identify": true
}
```

**响应**:
```json
{
  "batch_id": "batch_uuid_123",
  "status": "UPLOADED",
  "total_pages": 50,
  "estimated_completion_time": 120
}
```

**实现细节**:
```python
@router.post("/submit", response_model=BatchSubmissionResponse)
async def submit_batch(
    exam_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    rubrics: List[UploadFile] = File(...),
    api_key: Optional[str] = Form(None),
    auto_identify: bool = Form(True),
    orchestrator: Orchestrator = Depends(get_orchestrator)
) -> BatchSubmissionResponse:
    """
    提交批改任务
    
    流程:
    1. 验证文件
    2. 保存文件到临时目录
    3. 启动 LangGraph 工作流
    4. 返回批次 ID
    """
    # 生成批次 ID
    batch_id = str(uuid.uuid4())
    
    # 保存文件
    temp_dir = Path(tempfile.gettempdir()) / batch_id
    temp_dir.mkdir(exist_ok=True)
    
    # 启动工作流
    await orchestrator.invoke(
        graph_name="batch_grading",
        input_data={
            "batch_id": batch_id,
            "exam_id": exam_id,
            "files": files,
            "rubrics": rubrics,
            "api_key": api_key,
            "auto_identify": auto_identify
        }
    )
    
    return BatchSubmissionResponse(
        batch_id=batch_id,
        status=SubmissionStatus.UPLOADED,
        total_pages=total_pages,
        estimated_completion_time=120
    )
```

### 2. 状态查询 API

**端点**: `GET /batch/status/{batch_id}`

**响应**:
```json
{
  "batch_id": "batch_uuid_123",
  "exam_id": "exam_2025_001",
  "status": "PROCESSING",
  "total_students": 30,
  "completed_students": 15,
  "unidentified_pages": 5
}
```

### 3. 结果获取 API

**端点**: `GET /batch/results/{batch_id}`

**响应**:
```json
{
  "batch_id": "batch_uuid_123",
  "students": [
    {
      "studentName": "张三",
      "score": 85,
      "maxScore": 100,
      "percentage": 85,
      "questionResults": [
        {
          "questionId": "q1",
          "score": 10,
          "maxScore": 10,
          "feedback": "正确",
          "confidence": 0.95,
          "scoringPoints": [
            {
              "description": "逻辑清晰",
              "score": 5,
              "maxScore": 5,
              "isCorrect": true,
              "explanation": "答案逻辑严密"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 前端集成

### 1. API 客户端

**文件**: `frontend/src/services/api.ts`

```typescript
export const submitBatch = async (
  examId: string,
  files: File[],
  rubrics: File[],
  apiKey?: string
): Promise<BatchSubmissionResponse> => {
  const formData = new FormData();
  formData.append('exam_id', examId);
  
  files.forEach(file => {
    formData.append('files', file);
  });
  
  rubrics.forEach(file => {
    formData.append('rubrics', file);
  });
  
  if (apiKey) {
    formData.append('api_key', apiKey);
  }
  
  const response = await axios.post(
    `${API_BASE_URL}/batch/submit`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }
  );
  
  return response.data;
};

export const getBatchStatus = async (
  batchId: string
): Promise<BatchStatusResponse> => {
  const response = await axios.get(
    `${API_BASE_URL}/batch/status/${batchId}`
  );
  return response.data;
};

export const getBatchResults = async (
  batchId: string
): Promise<BatchResultsResponse> => {
  const response = await axios.get(
    `${API_BASE_URL}/batch/results/${batchId}`
  );
  return response.data;
};
```

### 2. 状态管理

**文件**: `frontend/src/store/consoleStore.ts`

```typescript
export const useConsoleStore = create<ConsoleStore>((set) => ({
  // 状态
  workflowStatus: 'IDLE',
  batchId: null,
  nodes: [],
  results: [],
  
  // 操作
  submitBatch: async (examId, files, rubrics) => {
    set({ workflowStatus: 'UPLOADING' });
    
    try {
      const response = await submitBatch(examId, files, rubrics);
      set({
        batchId: response.batch_id,
        workflowStatus: 'RUNNING'
      });
      
      // 启动轮询
      pollBatchStatus(response.batch_id);
    } catch (error) {
      set({ workflowStatus: 'FAILED' });
    }
  },
  
  pollBatchStatus: async (batchId) => {
    const status = await getBatchStatus(batchId);
    
    if (status.status === 'COMPLETED') {
      const results = await getBatchResults(batchId);
      set({
        results: results.students,
        workflowStatus: 'COMPLETED'
      });
    } else if (status.status === 'FAILED') {
      set({ workflowStatus: 'FAILED' });
    } else {
      // 继续轮询
      setTimeout(() => pollBatchStatus(batchId), 2000);
    }
  }
}));
```

### 3. 结果显示组件

**文件**: `frontend/src/components/console/ResultsView.tsx`

```typescript
export const ResultsView: React.FC<ResultsViewProps> = ({ results }) => {
  return (
    <div className="results-container">
      {results.map((student) => (
        <div key={student.studentName} className="student-result">
          <div className="student-header">
            <h3>{student.studentName}</h3>
            <div className="score">
              {student.score} / {student.maxScore}
              <span className="percentage">
                ({student.percentage}%)
              </span>
            </div>
          </div>
          
          <div className="questions">
            {student.questionResults?.map((question) => (
              <div key={question.questionId} className="question">
                <div className="question-header">
                  <span className="question-id">{question.questionId}</span>
                  <span className="score">
                    {question.score} / {question.maxScore}
                  </span>
                  {question.confidence && question.confidence < 0.8 && (
                    <span className="warning">⚠️ 低置信度</span>
                  )}
                </div>
                
                <div className="feedback">
                  {question.feedback}
                </div>
                
                {question.scoringPoints && (
                  <div className="scoring-points">
                    {question.scoringPoints.map((point, idx) => (
                      <div key={idx} className="scoring-point">
                        <span className="description">
                          {point.description}
                        </span>
                        <span className="score">
                          {point.score} / {point.maxScore}
                        </span>
                        <span className={`status ${point.isCorrect ? 'correct' : 'incorrect'}`}>
                          {point.isCorrect ? '✓' : '✗'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
```

---

## 提示词优化

### Gemini 推理提示

**文件**: `backend/src/services/gemini_reasoning.py`

```python
GRADING_PROMPT = """
你是一个专业的教育评估专家。你的任务是根据提供的评分标准对学生答卷进行评分。

## 评分标准
{rubric}

## 学生答卷
{answer}

## 评分要求

1. **逐题评分**
   - 对每一题进行独立评分
   - 严格按照评分标准评分
   - 记录每个评分点的得分情况

2. **置信度评估**
   - 对每个评分给出置信度（0-1）
   - 置信度 < 0.8 时标记为需要人工审核
   - 说明置信度低的原因

3. **详细反馈**
   - 为每题提供具体的反馈意见
   - 指出答题的优点和不足
   - 提供改进建议

4. **异常处理**
   - 如果答卷不清晰，标记为"需要澄清"
   - 如果答卷超出范围，标记为"无效答卷"
   - 如果无法判断，标记为"需要人工审核"

## 输出格式

```json
{
  "questions": [
    {
      "questionId": "q1",
      "score": 10,
      "maxScore": 10,
      "confidence": 0.95,
      "feedback": "答案正确，逻辑清晰",
      "scoringPoints": [
        {
          "description": "理解题意",
          "score": 3,
          "maxScore": 3,
          "isCorrect": true,
          "explanation": "学生正确理解了题意"
        }
      ]
    }
  ],
  "totalScore": 85,
  "totalMaxScore": 100,
  "overallFeedback": "总体表现良好，建议加强...",
  "needsReview": false,
  "reviewReason": ""
}
```

## 评分指导

- 严格按照评分标准评分
- 不要过度解释或添加额外要求
- 如果标准不清晰，使用合理的教育判断
- 保持评分的一致性和公平性
"""
```

### 提示词优化要点

1. **清晰的结构** - 分段落、分步骤
2. **具体的要求** - 明确的输出格式
3. **异常处理** - 处理边界情况
4. **置信度评估** - 评估评分的可靠性
5. **详细反馈** - 提供有价值的反馈

---

## 错误处理

### 1. 文件验证错误

```python
class FileValidationError(Exception):
    """文件验证错误"""
    pass

def validate_file(file: UploadFile) -> None:
    """验证上传的文件"""
    # 检查文件类型
    if not file.filename.endswith('.pdf'):
        raise FileValidationError("只支持 PDF 文件")
    
    # 检查文件大小
    if file.size > 100 * 1024 * 1024:  # 100MB
        raise FileValidationError("文件过大，最大 100MB")
    
    # 检查文件内容
    try:
        pdf = fitz.open(stream=file.file, filetype="pdf")
        pdf.close()
    except Exception as e:
        raise FileValidationError(f"无效的 PDF 文件: {str(e)}")
```

### 2. API 错误处理

```python
@router.post("/submit")
async def submit_batch(...) -> BatchSubmissionResponse:
    try:
        # 验证文件
        for file in files:
            validate_file(file)
        
        # 启动工作流
        batch_id = await orchestrator.invoke(...)
        
        return BatchSubmissionResponse(batch_id=batch_id, ...)
        
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"批改提交失败: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")
```

### 3. WebSocket 错误处理

```python
@router.websocket("/ws/{batch_id}")
async def websocket_endpoint(websocket: WebSocket, batch_id: str):
    try:
        await websocket.accept()
        
        while True:
            # 获取批改状态
            status = await get_batch_status(batch_id)
            
            # 发送更新
            await websocket.send_json({
                "type": "status_update",
                "data": status
            })
            
            if status.is_completed:
                break
            
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket 连接断开: {batch_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: {str(e)}")
        await websocket.close(code=1011, reason="服务器错误")
```

---

## 性能优化

### 1. 并行处理

```python
# 使用 asyncio 并行处理多个学生答卷
async def grade_batch_parallel(
    pages: List[Page],
    rubric: Rubric,
    num_workers: int = 3
) -> List[GradingResult]:
    """并行批改"""
    
    # 分配任务
    tasks = []
    pages_per_worker = len(pages) // num_workers
    
    for i in range(num_workers):
        start = i * pages_per_worker
        end = start + pages_per_worker if i < num_workers - 1 else len(pages)
        
        task = grade_pages(pages[start:end], rubric)
        tasks.append(task)
    
    # 并行执行
    results = await asyncio.gather(*tasks)
    
    # 合并结果
    return [r for result_list in results for r in result_list]
```

### 2. 缓存优化

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def parse_rubric(rubric_text: str) -> Rubric:
    """缓存评分标准解析结果"""
    # 解析评分标准
    return Rubric.parse(rubric_text)
```

### 3. 数据库查询优化

```python
# 使用连接池
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

---

## 监控和日志

### 1. 日志配置

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### 2. 性能监控

```python
import time
from functools import wraps

def monitor_performance(func):
    """监控函数执行时间"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        
        logger.info(f"{func.__name__} 执行时间: {duration:.2f}s")
        
        return result
    
    return wrapper
```

---

## 总结

本文档详细说明了 GradeOS Platform v2.0 的技术实现细节，包括：

1. ✅ 完整的 LangGraph 工作流设计
2. ✅ RESTful API 设计和实现
3. ✅ 前端集成和状态管理
4. ✅ 提示词优化策略
5. ✅ 错误处理机制
6. ✅ 性能优化方案

所有组件已集成并在生产环境中验证。
