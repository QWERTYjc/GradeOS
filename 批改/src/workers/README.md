# Temporal Workers

本目录包含 AI 批改系统的 Temporal Worker 入口点。

## Worker 类型

### 1. 编排 Worker (Orchestration Worker)

**文件**: `orchestration_worker.py`

**职责**:
- 运行工作流（Workflows）
- 管理试卷批改的整体流程编排
- 处理工作流间的协调和状态管理

**注册的工作流**:
- `ExamPaperWorkflow`: 试卷级父工作流
- `QuestionGradingChildWorkflow`: 题目级子工作流

**任务队列**: `default-queue`

**启动命令**:
```bash
python -m src.workers.orchestration_worker
```

**环境变量**:
- `TEMPORAL_HOST`: Temporal 服务器地址（默认: `localhost:7233`）
- `TEMPORAL_NAMESPACE`: Temporal 命名空间（默认: `default`）

### 2. 认知 Worker (Cognitive Worker)

**文件**: `cognitive_worker.py`

**职责**:
- 运行 Activities（活动任务）
- 执行认知计算任务（文档分割、题目批改等）
- 调用 AI 模型和数据库操作

**注册的 Activities**:
- `segment_document_activity`: 文档分割
- `grade_question_activity`: 题目批改
- `notify_teacher_activity`: 教师通知
- `persist_results_activity`: 结果持久化

**任务队列**: `vision-compute-queue`

**启动命令**:
```bash
python -m src.workers.cognitive_worker
```

**环境变量**:
- `TEMPORAL_HOST`: Temporal 服务器地址（默认: `localhost:7233`）
- `TEMPORAL_NAMESPACE`: Temporal 命名空间（默认: `default`）
- `MAX_CONCURRENT_ACTIVITIES`: 最大并发 Activity 数量（默认: `10`）
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: 数据库连接配置

## 架构说明

### 任务队列分离

系统采用两个独立的任务队列：

1. **default-queue**: 轻量级编排任务
   - 工作流状态管理
   - 子工作流协调
   - 结果聚合

2. **vision-compute-queue**: 重计算任务
   - Gemini API 调用
   - LangGraph 智能体推理
   - 数据库读写操作

这种分离设计的优势：
- 编排逻辑和计算逻辑解耦
- 可以独立扩展认知 Worker 以应对高负载
- 避免重计算任务阻塞工作流编排

### 并发控制

认知 Worker 通过 `max_concurrent_activities` 参数控制并发：
- 默认值: 10
- 建议根据以下因素调整：
  - 可用 CPU 核心数
  - 内存容量
  - Gemini API 速率限制
  - 数据库连接池大小

### 依赖注入

认知 Worker 在启动时初始化所有服务依赖：
- `LayoutAnalysisService`: 布局分析服务
- `CacheService`: 缓存服务
- `GradingAgent`: 批改智能体
- `GradingResultRepository`: 批改结果仓储
- `SubmissionRepository`: 提交仓储

这些依赖通过 Activity 包装器注入到各个 Activity 中。

## 部署建议

### 开发环境

```bash
# 终端 1: 启动编排 Worker
python -m src.workers.orchestration_worker

# 终端 2: 启动认知 Worker
python -m src.workers.cognitive_worker
```

### 生产环境

使用 Kubernetes 部署，配置示例：

```yaml
# 编排 Worker Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestration-worker
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: worker
        image: ai-grading:latest
        command: ["python", "-m", "src.workers.orchestration_worker"]
        env:
        - name: TEMPORAL_HOST
          value: "temporal-frontend:7233"
        - name: TEMPORAL_NAMESPACE
          value: "production"

---
# 认知 Worker Deployment (with KEDA autoscaling)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cognitive-worker
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: worker
        image: ai-grading:latest
        command: ["python", "-m", "src.workers.cognitive_worker"]
        env:
        - name: TEMPORAL_HOST
          value: "temporal-frontend:7233"
        - name: TEMPORAL_NAMESPACE
          value: "production"
        - name: MAX_CONCURRENT_ACTIVITIES
          value: "10"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

### KEDA 自动扩缩容

认知 Worker 可以配置 KEDA 根据 Temporal 队列深度自动扩缩容：

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: cognitive-worker-scaler
spec:
  scaleTargetRef:
    name: cognitive-worker
  minReplicaCount: 2
  maxReplicaCount: 10
  triggers:
  - type: temporal
    metadata:
      address: temporal-frontend:7233
      namespace: production
      taskQueue: vision-compute-queue
      targetValue: "5"  # 每个 worker 待处理任务 > 5 时扩容
```

## 监控和日志

### 日志级别

Workers 使用 Python logging 模块，默认级别为 INFO。

可以通过环境变量调整：
```bash
export LOG_LEVEL=DEBUG
python -m src.workers.cognitive_worker
```

### 关键日志

- Worker 启动/停止
- 工作流/Activity 执行开始/完成
- 错误和异常
- 服务依赖初始化

### 监控指标

建议监控以下指标：
- Worker 进程健康状态
- 任务队列深度
- Activity 执行延迟
- 错误率
- 资源使用（CPU、内存）

## 故障排查

### Worker 无法连接到 Temporal

**症状**: 启动时报错 "Failed to connect to Temporal"

**解决方案**:
1. 检查 `TEMPORAL_HOST` 环境变量
2. 确认 Temporal 服务器正在运行
3. 检查网络连接和防火墙规则

### Activity 执行超时

**症状**: Activity 任务超时失败

**解决方案**:
1. 检查 Gemini API 响应时间
2. 增加 Activity 的 `start_to_close_timeout`
3. 检查数据库连接池是否耗尽

### 内存不足

**症状**: Worker 进程被 OOM Killer 终止

**解决方案**:
1. 减少 `MAX_CONCURRENT_ACTIVITIES`
2. 增加容器内存限制
3. 检查是否有内存泄漏

## 验证需求

- ✅ 需求 4.1: Temporal 工作流编排
  - 编排 Worker 注册 ExamPaperWorkflow 和 QuestionGradingChildWorkflow
  - 认知 Worker 注册所有 Activities
  - 连接到正确的任务队列
  - 配置并发限制
