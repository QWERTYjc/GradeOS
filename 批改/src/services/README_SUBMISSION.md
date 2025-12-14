# 提交服务使用指南

## 概述

提交服务负责处理试卷文件的上传、验证、预处理和存储，并异步启动 Temporal 工作流进行批改。

## 功能特性

### 1. PDF 转图像（子任务 13.1）
- 使用 `pdf2image` 库将 PDF 转换为高分辨率图像
- 默认 DPI: 300（保证手写笔迹清晰）
- 支持多页 PDF 文档
- 每页转换为独立的 PNG 图像

### 2. 文件验证（子任务 13.2）
- **支持的图像格式**: JPEG, PNG, WEBP
- **文件大小限制**: 最大 50 MB
- **验证规则**:
  - 文件不能为空
  - 文件大小不能超过限制
  - 图像格式必须在支持列表中
- **错误消息**: 提供描述性错误消息，说明失败原因

### 3. 提交处理（子任务 13.3）
- 将图像保存到对象存储（当前使用本地文件系统，可迁移到 S3/MinIO）
- 在数据库中创建提交记录
- 异步启动 Temporal 工作流
- 立即返回 `submission_id`（不等待批改完成）

## 使用示例

### 基本使用

```python
from src.services.submission import SubmissionService
from src.services.storage import StorageService
from src.repositories.submission import SubmissionRepository
from src.utils.database import Database
from src.models.submission import SubmissionRequest
from src.models.enums import FileType

# 初始化依赖
db = Database(connection_string="postgresql://...")
repository = SubmissionRepository(db)
storage = StorageService(base_path="./storage")

# 创建提交服务
submission_service = SubmissionService(
    repository=repository,
    storage=storage,
    temporal_client=None  # 可选：传入 Temporal 客户端
)

# 提交图像文件
with open("exam.png", "rb") as f:
    image_data = f.read()

request = SubmissionRequest(
    exam_id="exam-001",
    student_id="student-001",
    file_type=FileType.IMAGE,
    file_data=image_data
)

response = await submission_service.submit(request)
print(f"提交成功: {response.submission_id}")
print(f"预计完成时间: {response.estimated_completion_time} 秒")
```

### 提交 PDF 文件

```python
# 提交 PDF 文件（自动转换为图像）
with open("exam.pdf", "rb") as f:
    pdf_data = f.read()

request = SubmissionRequest(
    exam_id="exam-001",
    student_id="student-001",
    file_type=FileType.PDF,
    file_data=pdf_data
)

response = await submission_service.submit(request)
```

### 查询提交状态

```python
# 查询提交状态
status = await submission_service.get_status(submission_id)

if status:
    print(f"状态: {status.status}")
    print(f"总分: {status.total_score}/{status.max_total_score}")
else:
    print("提交不存在")
```

## 工作流程

1. **接收请求** → 生成 `submission_id`
2. **文件验证** → 检查大小和格式
3. **文件预处理** → PDF 转图像（如需要）
4. **保存到存储** → 持久化图像文件
5. **创建记录** → 在数据库中创建提交记录
6. **启动工作流** → 异步启动 Temporal 批改工作流
7. **返回响应** → 立即返回 `submission_id` 和预计完成时间

## 错误处理

### 常见错误

| 错误类型 | 原因 | 解决方法 |
|---------|------|---------|
| `文件为空` | 上传的文件大小为 0 | 检查文件是否正确读取 |
| `文件大小超出限制` | 文件超过 50 MB | 压缩文件或分页上传 |
| `不支持的图像格式` | 图像格式不在支持列表中 | 转换为 JPEG/PNG/WEBP |
| `PDF 转换失败` | PDF 文件损坏或格式错误 | 检查 PDF 文件完整性 |

### 错误示例

```python
from src.services.submission import SubmissionServiceError

try:
    response = await submission_service.submit(request)
except SubmissionServiceError as e:
    print(f"提交失败: {str(e)}")
    # 根据错误消息采取相应措施
```

## 配置

### 存储配置

```python
# 使用自定义存储路径
storage = StorageService(base_path="/data/submissions")
```

### Temporal 集成

```python
from temporalio.client import Client

# 连接到 Temporal
temporal_client = await Client.connect("localhost:7233")

# 创建带 Temporal 集成的提交服务
submission_service = SubmissionService(
    repository=repository,
    storage=storage,
    temporal_client=temporal_client
)
```

## 性能考虑

- **PDF 转换**: 300 DPI 的转换可能需要几秒钟，取决于页数
- **文件存储**: 使用异步 I/O 避免阻塞
- **工作流启动**: 异步启动，不等待批改完成
- **预计完成时间**: 基于页数估算（每页约 4 道题，每题 30 秒）

## 未来改进

- [ ] 支持 S3/MinIO 对象存储
- [ ] 支持更多图像格式（TIFF, GIF）
- [ ] 实现文件压缩以节省存储空间
- [ ] 添加文件去重功能
- [ ] 支持断点续传
- [ ] 实现批量上传接口

## 相关文档

- [需求文档](.kiro/specs/ai-grading-agent/requirements.md) - 需求 1.1, 1.2, 1.3, 1.4, 1.5
- [设计文档](.kiro/specs/ai-grading-agent/design.md) - 提交服务接口设计
- [任务列表](.kiro/specs/ai-grading-agent/tasks.md) - 任务 13
