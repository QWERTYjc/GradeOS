# 批量提交 API 使用指南

## 概述

批量提交 API 支持上传包含多个学生作业的 PDF 文件，系统会自动识别学生边界并分别批改。

## API 端点

### 1. 同步批改（推荐用于测试）

**端点**: `POST /batch/grade-sync`

**功能**: 完整的批改流程（同步执行）

**请求参数**:
- `rubric_file` (File): 评分标准 PDF 文件
- `answer_file` (File): 学生作答 PDF 文件
- `api_key` (str): Gemini API Key
- `total_score` (int, 可选): 总分，默认 105
- `total_questions` (int, 可选): 总题数，默认 19

**请求示例**:
```bash
curl -X POST "http://localhost:8000/batch/grade-sync" \
  -F "rubric_file=@批改标准.pdf" \
  -F "answer_file=@学生作答.pdf" \
  -F "api_key=YOUR_API_KEY" \
  -F "total_score=105" \
  -F "total_questions=19"
```

**响应示例**:
```json
{
  "status": "completed",
  "total_students": 2,
  "students": [
    {
      "name": "学生A",
      "page_range": {
        "start": 1,
        "end": 26
      },
      "total_score": 85,
      "max_score": 105,
      "percentage": 81.0,
      "questions_graded": 19,
      "details": [
        {
          "question_id": "1",
          "score": 5,
          "max_score": 5,
          "scoring_points": [
            {
              "point": "正确写出算式",
              "score": 2,
              "explanation": "学生清晰地写出了完整的算式"
            },
            {
              "point": "计算结果正确",
              "score": 3,
              "explanation": "学生给出了正确的答案"
            }
          ],
          "used_alternative_solution": false,
          "confidence": 0.95
        }
        // ... 更多题目
      ]
    },
    {
      "name": "学生B",
      "page_range": {
        "start": 27,
        "end": 49
      },
      "total_score": 82,
      "max_score": 105,
      "percentage": 78.1,
      "questions_graded": 19,
      "details": [
        // ... 题目详情
      ]
    }
  ]
}
```

### 2. 异步批改（推荐用于生产）

**端点**: `POST /batch/submit`

**功能**: 提交批改任务（异步执行）

**请求参数**:
- `exam_id` (str): 考试 ID
- `rubric_file` (File): 评分标准 PDF 文件
- `answer_file` (File): 学生作答 PDF 文件
- `api_key` (str): Gemini API Key
- `auto_identify` (bool, 可选): 是否自动识别学生身份，默认 true

**请求示例**:
```bash
curl -X POST "http://localhost:8000/batch/submit" \
  -F "exam_id=exam_2025_001" \
  -F "rubric_file=@批改标准.pdf" \
  -F "answer_file=@学生作答.pdf" \
  -F "api_key=YOUR_API_KEY" \
  -F "auto_identify=true"
```

**响应示例**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "uploaded",
  "total_pages": 49,
  "estimated_completion_time": 1470
}
```

### 3. 查询批改状态

**端点**: `GET /batch/status/{batch_id}`

**功能**: 查询批改进度

**请求示例**:
```bash
curl "http://localhost:8000/batch/status/550e8400-e29b-41d4-a716-446655440000"
```

**响应示例**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "exam_id": "exam_2025_001",
  "status": "processing",
  "total_students": 2,
  "completed_students": 1,
  "unidentified_pages": 0
}
```

### 4. 获取批改结果

**端点**: `GET /batch/results/{batch_id}`

**功能**: 获取完整的批改结果

**请求示例**:
```bash
curl "http://localhost:8000/batch/results/550e8400-e29b-41d4-a716-446655440000"
```

**响应示例**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "students": [
    {
      "name": "学生A",
      "total_score": 85,
      "max_score": 105,
      "percentage": 81.0
    },
    {
      "name": "学生B",
      "total_score": 82,
      "max_score": 105,
      "percentage": 78.1
    }
  ]
}
```

### 5. WebSocket 实时推送

**端点**: `WS /batch/ws/{batch_id}`

**功能**: 实时接收批改进度更新

**连接示例**:
```javascript
const ws = new WebSocket('ws://localhost:8000/batch/ws/550e8400-e29b-41d4-a716-446655440000');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'progress') {
    console.log(`批改进度: ${message.percentage}%`);
    console.log(`当前学生: ${message.student_name}`);
  } else if (message.type === 'completed') {
    console.log('批改完成！');
  } else if (message.type === 'error') {
    console.error('批改出错:', message.error);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket 错误:', error);
};

ws.onclose = () => {
  console.log('连接已关闭');
};
```

## 工作流程

### 同步批改流程

```
1. 用户上传评分标准 PDF 和学生作答 PDF
   ↓
2. 系统转换 PDF 为高分辨率图像（150 DPI）
   ↓
3. 解析评分标准
   - 提取每道题的分值
   - 识别得分点
   - 识别另类解法
   ↓
4. 识别学生边界
   - 尝试识别学生信息（姓名/学号）
   - 如果失败，通过题目顺序循环检测推断边界
   - 为无法识别的学生分配占位符名称
   ↓
5. 逐个批改学生
   - 对每个学生的所有页面进行批改
   - 严格按照评分标准逐点评分
   - 生成详细的评分说明
   ↓
6. 返回完整结果
   - 每个学生的总分和百分比
   - 每道题的详细评分
   - 每个得分点的说明
```

### 异步批改流程

```
1. 用户提交批改任务
   ↓
2. 系统返回 batch_id 和预计完成时间
   ↓
3. 用户可以：
   - 通过 WebSocket 实时接收进度更新
   - 定期查询 /batch/status/{batch_id} 获取状态
   - 批改完成后通过 /batch/results/{batch_id} 获取结果
```

## 学生识别策略

系统采用两阶段策略识别学生：

### 第一阶段：直接识别
- 尝试从试卷上识别学生信息（姓名、学号、班级）
- 如果成功，使用真实学生信息

### 第二阶段：推理识别
- 如果无法识别学生信息，系统会：
  1. 识别每页的题目编号
  2. 检测题目编号是否出现"循环"（例如：1→2→3→1）
  3. 当题目编号循环时，推断为新学生的开始
  4. 为无法识别的学生分配占位符名称（学生A、学生B 等）

**示例**:
```
页面 1-26: 题目 1,2,3,...,19 → 学生A
页面 27-49: 题目 1,2,3,...,19 → 学生B（题目循环，推断为新学生）
```

## 评分标准解析

系统支持两种评分标准格式：

### 格式 1：标准格式（分离的答案键）
- 评分标准和答案键在不同的 PDF 中
- 系统会分别解析两个文件

### 格式 2：嵌入式格式（答案在题目页面上）
- 答案显示在题目页面的特定位置
- 系统会自动识别并提取

## 批改标准

系统严格按照以下标准进行批改：

1. **逐点评分**: 每道题按照评分细则的各个得分点逐一评分
2. **另类解法识别**: 识别并正确处理另类解法（不计入总分）
3. **证据链**: 为每个得分点提供具体的证据和说明
4. **置信度**: 为每个评分提供置信度分数（0-1）

## 成本估算

基于实测数据：

| 项目 | 成本 |
|------|------|
| 单学生批改 | $0.20-0.25 |
| 30 学生总成本 | $6-7.50 |
| 优化后单学生成本（缓存） | $0.15-0.19 |

## 性能指标

| 指标 | 数值 |
|------|------|
| 页面分割延迟 | 3-5 秒 |
| 单题批改延迟 | 15-20 秒 |
| 2 学生完整批改 | 2-3 分钟 |
| 30 学生完整批改 | 30-45 分钟（并行处理） |

## 错误处理

### 常见错误

**错误 1: 无效的 API Key**
```json
{
  "detail": "Invalid API key"
}
```
解决方案: 检查 API Key 是否正确

**错误 2: 文件格式不支持**
```json
{
  "detail": "Unsupported file format"
}
```
解决方案: 确保上传的是 PDF 文件

**错误 3: 评分标准解析失败**
```json
{
  "detail": "Failed to parse rubric"
}
```
解决方案: 检查评分标准 PDF 是否清晰可读

## 最佳实践

### 1. 文件准备
- 确保 PDF 清晰可读（建议 150 DPI 以上）
- 评分标准应包含完整的题目和答案
- 学生作答应按顺序排列

### 2. 参数配置
- 准确设置 `total_score` 和 `total_questions`
- 使用有效的 `exam_id` 便于后续查询

### 3. 异步处理
- 对于大批量提交，使用异步 API
- 通过 WebSocket 实时监控进度
- 避免频繁轮询状态接口

### 4. 错误恢复
- 实现重试机制
- 记录 batch_id 便于后续查询
- 保存原始文件便于重新提交

## 示例代码

### Python 示例

```python
import requests
import json

# 配置
API_URL = "http://localhost:8000"
API_KEY = "YOUR_API_KEY"

# 同步批改
def grade_batch_sync():
    with open("批改标准.pdf", "rb") as rubric_file, \
         open("学生作答.pdf", "rb") as answer_file:
        
        files = {
            "rubric_file": rubric_file,
            "answer_file": answer_file
        }
        data = {
            "api_key": API_KEY,
            "total_score": 105,
            "total_questions": 19
        }
        
        response = requests.post(
            f"{API_URL}/batch/grade-sync",
            files=files,
            data=data
        )
        
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 输出汇总
        for student in result["students"]:
            print(f"\n{student['name']}: {student['total_score']}/{student['max_score']} "
                  f"({student['percentage']}%)")

# 异步批改
def grade_batch_async():
    with open("批改标准.pdf", "rb") as rubric_file, \
         open("学生作答.pdf", "rb") as answer_file:
        
        files = {
            "rubric_file": rubric_file,
            "answer_file": answer_file
        }
        data = {
            "exam_id": "exam_2025_001",
            "api_key": API_KEY,
            "auto_identify": True
        }
        
        response = requests.post(
            f"{API_URL}/batch/submit",
            files=files,
            data=data
        )
        
        result = response.json()
        batch_id = result["batch_id"]
        print(f"批次 ID: {batch_id}")
        print(f"预计完成时间: {result['estimated_completion_time']} 秒")
        
        return batch_id

# 查询状态
def check_status(batch_id):
    response = requests.get(f"{API_URL}/batch/status/{batch_id}")
    result = response.json()
    print(f"状态: {result['status']}")
    print(f"已完成: {result['completed_students']}/{result['total_students']}")

if __name__ == "__main__":
    # 同步批改
    grade_batch_sync()
    
    # 或异步批改
    # batch_id = grade_batch_async()
    # check_status(batch_id)
```

### JavaScript 示例

```javascript
// 同步批改
async function gradeBatchSync() {
  const formData = new FormData();
  formData.append("rubric_file", document.getElementById("rubricFile").files[0]);
  formData.append("answer_file", document.getElementById("answerFile").files[0]);
  formData.append("api_key", "YOUR_API_KEY");
  formData.append("total_score", 105);
  formData.append("total_questions", 19);
  
  const response = await fetch("http://localhost:8000/batch/grade-sync", {
    method: "POST",
    body: formData
  });
  
  const result = await response.json();
  console.log(result);
  
  // 显示结果
  result.students.forEach(student => {
    console.log(`${student.name}: ${student.total_score}/${student.max_score} (${student.percentage}%)`);
  });
}

// WebSocket 实时推送
function connectWebSocket(batchId) {
  const ws = new WebSocket(`ws://localhost:8000/batch/ws/${batchId}`);
  
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === "progress") {
      console.log(`进度: ${message.percentage}%`);
      console.log(`当前学生: ${message.student_name}`);
      updateProgressBar(message.percentage);
    } else if (message.type === "completed") {
      console.log("批改完成！");
      ws.close();
    }
  };
  
  ws.onerror = (error) => {
    console.error("WebSocket 错误:", error);
  };
}

function updateProgressBar(percentage) {
  const progressBar = document.getElementById("progressBar");
  progressBar.style.width = percentage + "%";
  progressBar.textContent = percentage + "%";
}
```

## 常见问题

**Q: 系统如何识别多个学生？**
A: 系统首先尝试从试卷上识别学生信息。如果无法识别，则通过检测题目编号的循环来推断学生边界。

**Q: 支持多少个学生？**
A: 理论上没有限制，但建议单个 PDF 不超过 100 个学生以保证性能。

**Q: 批改需要多长时间？**
A: 平均每个学生 2-3 分钟，具体取决于试卷页数和题目复杂度。

**Q: 可以取消正在进行的批改吗？**
A: 可以通过 WebSocket 发送 "cancel" 消息来请求取消。

**Q: 批改结果的准确性如何？**
A: 系统与人工标注的相关系数 > 0.9，置信度分数可用于识别需要人工审核的题目。

