# API 接口快速参考

## 基础信息

- **Base URL**: `http://localhost:8000`
- **API 版本**: v1
- **认证方式**: 暂无（生产环境需添加）
- **数据格式**: JSON
- **字符编码**: UTF-8

## 接口概览

| 分类 | 端点 | 方法 | 描述 |
|------|------|------|------|
| **提交** | `/api/v1/submissions` | POST | 上传并提交批改 |
| | `/api/v1/submissions/{id}` | GET | 获取提交状态 |
| | `/api/v1/submissions/{id}/results` | GET | 获取批改结果 |
| | `/api/v1/submissions` | GET | 分页查询提交列表 |
| | `/api/v1/submissions/{id}/fields` | GET | 字段选择查询 |
| **评分细则** | `/api/v1/rubrics` | POST | 创建评分细则 |
| | `/api/v1/rubrics/{exam_id}/{question_id}` | GET | 获取评分细则 |
| | `/api/v1/rubrics/{rubric_id}` | PUT | 更新评分细则 |
| **人工审核** | `/api/v1/reviews/{id}/signal` | POST | 发送审核信号 |
| | `/api/v1/reviews/{id}/pending` | GET | 获取待审核项 |
| **批量提交** | `/batch/submit` | POST | 批量提交试卷 |
| | `/batch/grade-sync` | POST | 同步批改（测试） |
| | `/batch/grade-cached` | POST | 优化批改（缓存） |
| | `/batch/status/{batch_id}` | GET | 查询批量状态 |
| | `/batch/results/{batch_id}` | GET | 获取批量结果 |
| **WebSocket** | `/ws/submissions/{id}` | WS | 提交状态推送 |
| | `/batch/ws/{batch_id}` | WS | 批量进度推送 |
| **管理** | `/api/v1/admin/slow-queries` | GET | 获取慢查询记录 |
| | `/api/v1/admin/stats` | GET | 获取统计信息 |
| | `/health` | GET | 健康检查 |

## 详细接口说明

### 1. 提交管理

#### 1.1 上传并提交批改

```http
POST /api/v1/submissions
Content-Type: multipart/form-data
```

**请求参数**:
```
exam_id: string (required) - 考试 ID
student_id: string (required) - 学生 ID
file: file (required) - 试卷文件（PDF/JPEG/PNG/WEBP）
```

**响应 201**:
```json
{
  "submission_id": "sub_abc123",
  "exam_id": "exam_001",
  "student_id": "stu_001",
  "status": "UPLOADED",
  "estimated_completion_time": "2024-12-13T15:30:00Z"
}
```

**错误响应**:
- `400 Bad Request`: 文件格式不支持或参数错误
- `500 Internal Server Error`: 服务器内部错误

---

#### 1.2 获取提交状态

```http
GET /api/v1/submissions/{submission_id}
```

**路径参数**:
- `submission_id`: 提交 ID

**响应 200**:
```json
{
  "submission_id": "sub_abc123",
  "exam_id": "exam_001",
  "student_id": "stu_001",
  "status": "COMPLETED",
  "total_score": 85.5,
  "max_total_score": 100.0,
  "created_at": "2024-12-13T14:00:00Z",
  "updated_at": "2024-12-13T14:30:00Z"
}
```

**状态枚举**:
- `UPLOADED`: 已上传
- `SEGMENTING`: 分割中
- `GRADING`: 批改中
- `REVIEWING`: 待审核
- `COMPLETED`: 已完成
- `REJECTED`: 已拒绝
- `FAILED`: 失败

---

#### 1.3 获取批改结果

```http
GET /api/v1/submissions/{submission_id}/results
```

**响应 200**:
```json
{
  "submission_id": "sub_abc123",
  "exam_id": "exam_001",
  "student_id": "stu_001",
  "total_score": 85.5,
  "max_total_score": 100.0,
  "question_results": [
    {
      "question_id": "q1",
      "score": 8.5,
      "max_score": 10.0,
      "confidence": 0.92,
      "feedback": "答案基本正确，但缺少关键步骤的说明。建议补充推导过程。",
      "visual_annotations": [
        {
          "type": "highlight",
          "coordinates": [100, 200, 300, 250],
          "label": "关键步骤缺失"
        }
      ],
      "agent_trace": {
        "iterations": 2,
        "reasoning_steps": [...]
      }
    }
  ],
  "overall_feedback": null
}
```

---

#### 1.4 分页查询提交列表

```http
GET /api/v1/submissions?page=1&page_size=20&status=COMPLETED
```

**查询参数**:
- `page` (int, default: 1): 页码
- `page_size` (int, default: 20): 每页数量
- `sort_by` (string, optional): 排序字段（created_at, updated_at, total_score）
- `sort_order` (string, default: "desc"): 排序方向（asc/desc）
- `status` (string, optional): 按状态过滤
- `exam_id` (string, optional): 按考试 ID 过滤
- `student_id` (string, optional): 按学生 ID 过滤

**响应 200**:
```json
{
  "items": [
    {
      "submission_id": "sub_abc123",
      "exam_id": "exam_001",
      "student_id": "stu_001",
      "status": "COMPLETED",
      "total_score": 85.5,
      "created_at": "2024-12-13T14:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

---

#### 1.5 字段选择查询

```http
GET /api/v1/submissions/{submission_id}/fields?fields=submission_id,status,total_score
```

**查询参数**:
- `fields` (string, required): 逗号分隔的字段列表

**响应 200**:
```json
{
  "submission_id": "sub_abc123",
  "status": "COMPLETED",
  "total_score": 85.5
}
```

---

### 2. 评分细则管理

#### 2.1 创建评分细则

```http
POST /api/v1/rubrics
Content-Type: application/json
```

**请求体**:
```json
{
  "exam_id": "exam_001",
  "question_id": "q1",
  "rubric_text": "本题考查学生对牛顿第二定律的理解和应用能力。",
  "max_score": 10.0,
  "scoring_points": [
    {
      "description": "正确写出牛顿第二定律公式 F=ma",
      "score": 3.0
    },
    {
      "description": "正确代入数值并计算",
      "score": 5.0
    },
    {
      "description": "结果正确且单位正确",
      "score": 2.0
    }
  ],
  "standard_answer": "根据牛顿第二定律 F=ma，代入 m=2kg, a=3m/s²，得 F=6N"
}
```

**响应 201**:
```json
{
  "rubric_id": "rub_xyz789",
  "exam_id": "exam_001",
  "question_id": "q1",
  "rubric_text": "本题考查学生对牛顿第二定律的理解和应用能力。",
  "max_score": 10.0,
  "scoring_points": [...],
  "standard_answer": "根据牛顿第二定律 F=ma...",
  "created_at": "2024-12-13T14:00:00Z",
  "updated_at": "2024-12-13T14:00:00Z"
}
```

---

#### 2.2 获取评分细则

```http
GET /api/v1/rubrics/{exam_id}/{question_id}
```

**路径参数**:
- `exam_id`: 考试 ID
- `question_id`: 题目 ID

**响应 200**: 同创建响应

---

#### 2.3 更新评分细则

```http
PUT /api/v1/rubrics/{rubric_id}
Content-Type: application/json
```

**请求体**:
```json
{
  "rubric_text": "更新后的评分细则描述",
  "max_score": 12.0,
  "scoring_points": [...]
}
```

**响应 200**: 返回更新后的评分细则

---

### 3. 人工审核

#### 3.1 发送审核信号

```http
POST /api/v1/reviews/{submission_id}/signal
Content-Type: application/json
```

**请求体（批准）**:
```json
{
  "submission_id": "sub_abc123",
  "action": "APPROVE"
}
```

**请求体（覆盖评分）**:
```json
{
  "submission_id": "sub_abc123",
  "action": "OVERRIDE",
  "question_id": "q1",
  "override_score": 9.0,
  "override_feedback": "学生答案有创新性，给予额外加分",
  "review_comment": "答案虽然与标准答案不同，但思路正确"
}
```

**请求体（拒绝）**:
```json
{
  "submission_id": "sub_abc123",
  "action": "REJECT",
  "review_comment": "试卷图像不清晰，无法批改"
}
```

**响应 200**:
```json
{
  "message": "审核已完成，使用人工覆盖评分",
  "submission_id": "sub_abc123",
  "action": "OVERRIDE",
  "override_score": 9.0
}
```

---

#### 3.2 获取待审核项

```http
GET /api/v1/reviews/{submission_id}/pending
```

**响应 200**:
```json
[
  {
    "submission_id": "sub_abc123",
    "exam_id": "exam_001",
    "student_id": "stu_001",
    "question_id": "q3",
    "ai_score": 7.5,
    "confidence": 0.68,
    "reason": "置信度低于阈值 0.75 (当前: 0.68)",
    "created_at": "2024-12-13T14:30:00Z"
  }
]
```

---

### 4. 批量提交

#### 4.1 批量提交试卷

```http
POST /batch/submit
Content-Type: multipart/form-data
```

**请求参数**:
```
exam_id: string (required) - 考试 ID
rubric_file: file (required) - 评分标准 PDF
answer_file: file (required) - 学生作答 PDF
api_key: string (required) - Gemini API Key
auto_identify: boolean (default: true) - 是否自动识别学生身份
```

**响应 200**:
```json
{
  "batch_id": "batch_xyz789",
  "status": "UPLOADED",
  "total_pages": 50,
  "estimated_completion_time": 1500
}
```

---

#### 4.2 同步批改（测试用）

```http
POST /batch/grade-sync
Content-Type: multipart/form-data
```

**请求参数**:
```
rubric_file: file (required) - 评分标准 PDF
answer_file: file (required) - 学生作答 PDF
api_key: string (required) - Gemini API Key
total_score: int (default: 105) - 总分
total_questions: int (default: 19) - 总题数
```

**响应 200**:
```json
{
  "status": "completed",
  "total_students": 3,
  "students": [
    {
      "name": "张三",
      "page_range": {"start": 1, "end": 5},
      "total_score": 92.5,
      "max_score": 105.0,
      "percentage": 88.1,
      "questions_graded": 19,
      "details": [
        {
          "question_id": "1",
          "score": 5.0,
          "max_score": 5.0,
          "scoring_points": [
            {
              "point": "正确写出公式",
              "score": 2.0,
              "explanation": "公式正确"
            }
          ],
          "used_alternative_solution": false,
          "confidence": 0.95
        }
      ]
    }
  ]
}
```

---

#### 4.3 优化批改（使用缓存）

```http
POST /batch/grade-cached
Content-Type: multipart/form-data
```

**请求参数**: 同 `/batch/grade-sync`

**响应 200**:
```json
{
  "status": "completed",
  "total_students": 3,
  "optimization": {
    "method": "context_caching",
    "cache_info": {
      "cache_name": "rubric_cache_abc123",
      "ttl": 3600,
      "created_at": "2024-12-13T14:00:00Z"
    },
    "token_savings": {
      "description": "使用 Context Caching 节省约 25% Token",
      "estimated_savings_per_student": "约 15,000-20,000 tokens",
      "cost_savings_per_student": "约 $0.04-0.05"
    }
  },
  "students": [...]
}
```

---

#### 4.4 查询批量状态

```http
GET /batch/status/{batch_id}
```

**响应 200**:
```json
{
  "batch_id": "batch_xyz789",
  "exam_id": "exam_001",
  "status": "processing",
  "total_students": 5,
  "completed_students": 2,
  "unidentified_pages": 0,
  "results": null
}
```

---

#### 4.5 获取批量结果

```http
GET /batch/results/{batch_id}
```

**响应 200**:
```json
{
  "batch_id": "batch_xyz789",
  "students": [...]
}
```

---

### 5. WebSocket 实时推送

#### 5.1 提交状态推送

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/submissions/sub_abc123');

// 接收消息
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('状态更新:', data);
};

// 消息格式
{
  "type": "status_update",
  "submission_id": "sub_abc123",
  "status": "GRADING",
  "progress": 45,
  "message": "正在批改第 3 题..."
}
```

---

#### 5.2 批量批改进度推送

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:8000/batch/ws/batch_xyz789');

// 接收消息
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'progress') {
    console.log(`进度: ${data.percentage}%`);
    console.log(`当前学生: ${data.student_name}`);
  } else if (data.type === 'completed') {
    console.log('批改完成!');
  }
};

// 发送取消请求
ws.send('cancel');
```

**消息类型**:

**进度更新**:
```json
{
  "type": "progress",
  "stage": "grading",
  "current_student": 2,
  "total_students": 5,
  "student_name": "张三",
  "percentage": 40
}
```

**完成通知**:
```json
{
  "type": "completed",
  "percentage": 100,
  "total_students": 5,
  "message": "批改完成"
}
```

**错误通知**:
```json
{
  "type": "error",
  "message": "批改失败: API 配额不足"
}
```

---

### 6. 管理接口

#### 6.1 获取慢查询记录

```http
GET /api/v1/admin/slow-queries?limit=100&min_duration_ms=500
```

**查询参数**:
- `limit` (int, default: 100): 返回记录数
- `min_duration_ms` (int, optional): 最小持续时间（毫秒）

**响应 200**:
```json
{
  "slow_queries": [
    {
      "query": "SELECT * FROM submissions WHERE ...",
      "duration_ms": 1250,
      "timestamp": "2024-12-13T14:30:00Z",
      "params": {...}
    }
  ],
  "count": 5
}
```

---

#### 6.2 获取 API 统计信息

```http
GET /api/v1/admin/stats
```

**响应 200**:
```json
{
  "total_queries": 12345,
  "slow_queries": 23,
  "active_websocket_connections": 15,
  "subscribed_submissions": ["sub_abc123", "sub_def456"],
  "cache_hit_rate": 0.85,
  "avg_response_time_ms": 125,
  "uptime_seconds": 86400
}
```

---

#### 6.3 健康检查

```http
GET /health
```

**响应 200**:
```json
{
  "status": "healthy",
  "service": "ai-grading-api",
  "version": "1.0.0"
}
```

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "error": "error_code",
  "message": "人类可读的错误描述",
  "details": {
    "field": "具体错误信息"
  }
}
```

### 常见错误码

| 状态码 | 错误码 | 描述 |
|--------|--------|------|
| 400 | `bad_request` | 请求参数错误 |
| 401 | `unauthorized` | 未授权 |
| 403 | `forbidden` | 禁止访问 |
| 404 | `not_found` | 资源不存在 |
| 409 | `conflict` | 资源冲突 |
| 429 | `rate_limit_exceeded` | 超过速率限制 |
| 500 | `internal_server_error` | 服务器内部错误 |
| 503 | `service_unavailable` | 服务不可用 |

---

## 速率限制

- **默认限制**: 100 请求/分钟
- **响应头**:
  - `X-RateLimit-Limit`: 限制数量
  - `X-RateLimit-Remaining`: 剩余请求数
  - `X-RateLimit-Reset`: 重置时间（Unix 时间戳）

**超限响应 429**:
```json
{
  "error": "rate_limit_exceeded",
  "message": "请求过于频繁，请稍后重试",
  "retry_after": 60
}
```

---

## 最佳实践

### 1. 使用字段选择减少数据传输

```http
# 不推荐：获取所有字段
GET /api/v1/submissions/sub_abc123

# 推荐：只获取需要的字段
GET /api/v1/submissions/sub_abc123/fields?fields=status,total_score
```

### 2. 使用 WebSocket 获取实时更新

```javascript
// 不推荐：轮询
setInterval(() => {
  fetch('/api/v1/submissions/sub_abc123')
    .then(res => res.json())
    .then(data => console.log(data));
}, 5000);

// 推荐：WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/submissions/sub_abc123');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('实时更新:', data);
};
```

### 3. 批量批改使用缓存优化

```http
# 不推荐：标准批改（每个学生都计费评分标准）
POST /batch/grade-sync

# 推荐：使用缓存（评分标准只计费一次）
POST /batch/grade-cached
```

### 4. 分页查询大量数据

```http
# 不推荐：一次获取所有数据
GET /api/v1/submissions?page_size=10000

# 推荐：分页获取
GET /api/v1/submissions?page=1&page_size=20
```

---

## 示例代码

### Python

```python
import requests

# 上传并提交批改
def submit_grading(exam_id: str, student_id: str, file_path: str):
    url = "http://localhost:8000/api/v1/submissions"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'exam_id': exam_id,
            'student_id': student_id
        }
        
        response = requests.post(url, files=files, data=data)
        return response.json()

# 获取批改结果
def get_results(submission_id: str):
    url = f"http://localhost:8000/api/v1/submissions/{submission_id}/results"
    response = requests.get(url)
    return response.json()

# 使用示例
result = submit_grading('exam_001', 'stu_001', 'paper.pdf')
print(f"提交 ID: {result['submission_id']}")

# 等待批改完成后获取结果
results = get_results(result['submission_id'])
print(f"总分: {results['total_score']}/{results['max_total_score']}")
```

### JavaScript

```javascript
// 上传并提交批改
async function submitGrading(examId, studentId, file) {
  const formData = new FormData();
  formData.append('exam_id', examId);
  formData.append('student_id', studentId);
  formData.append('file', file);
  
  const response = await fetch('http://localhost:8000/api/v1/submissions', {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
}

// WebSocket 实时监听
function watchSubmission(submissionId) {
  const ws = new WebSocket(`ws://localhost:8000/ws/submissions/${submissionId}`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('状态更新:', data);
    
    if (data.status === 'COMPLETED') {
      console.log('批改完成!');
      ws.close();
    }
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket 错误:', error);
  };
  
  return ws;
}

// 使用示例
const fileInput = document.querySelector('input[type="file"]');
const file = fileInput.files[0];

submitGrading('exam_001', 'stu_001', file)
  .then(result => {
    console.log('提交成功:', result.submission_id);
    watchSubmission(result.submission_id);
  });
```

---

## 更新日志

### v1.0.0 (2024-12-13)

- ✅ 初始版本发布
- ✅ 支持单个提交批改
- ✅ 支持批量提交批改
- ✅ 支持人工审核
- ✅ 支持 Context Caching 优化
- ✅ 支持 WebSocket 实时推送
- ✅ 支持分页查询和字段选择

---

## 支持

如有问题，请联系：

- 📧 Email: support@example.com
- 💬 Slack: #ai-grading-support
- 📖 文档: https://docs.example.com
