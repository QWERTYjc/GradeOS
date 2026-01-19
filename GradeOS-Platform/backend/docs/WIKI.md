# AI 批改系统 Wiki

> 生产级纯视觉（Vision-Native）自动评估引擎，专为教育技术（EdTech）领域设�?

**最后更�?*: 2025-12-19  
**版本**: 3.0.0

---

## 目录

1. [项目概述](#项目概述)
2. [系统架构](#系统架构)
3. [后端模块](#后端模块)
4. [前端模块](#前端模块)
5. [API 接口](#api-接口)
6. [部署架构](#部署架构)
7. [开发指南](#开发指�?
8. [项目状态](#项目状�?

---

## 项目概述

### 核心价值主�?

AI 批改系统是一�?*完全摒弃 OCR** 的纯视觉批改引擎，直接利用多模态大模型（VLM）对试卷图像进行端到端语义理解�?

| 能力 | 描述 | 状�?|
|------|------|------|
| 🎯 纯视觉批�?| 直接理解图像，无 OCR 误差传播 | �?|
| 🧠 动态派生智能体 | SupervisorAgent 根据题型调度专业智能�?| �?|
| �?持久化执�?| Temporal 工作流保证长周期任务可靠�?| �?|
| 👥 人机协作 | 低置信度结果人工审核介入 | �?|
| 📊 批量处理 | 多学生合卷自动识别与分割 | �?|
| 💰 成本优化 | Context Caching 节省�?25% Token | �?|

### 设计目标

- **日均处理能力**: 千万级请�?
- **单题批改延迟**: < 30 秒（实测 15-20 秒）
- **评分准确�?*: 与人工标�?Pearson 相关系数 > 0.9

---

## 系统架构

### 四层架构设计

```
┌─────────────────────────────────────────────────────────────────�?
�?                       接入�?(Ingestion)                        �?
�? ┌─────────────�?   ┌─────────────�?   ┌───────────────────�?   �?
�? �?FastAPI 网关 �?   �?WebSocket   �?   �?S3/MinIO 对象存储  �?   �?
�? �? /api/v1/*  �?   �? 实时推�?   �?   �?  试卷图像存储    �?   �?
�? └─────────────�?   └─────────────�?   └───────────────────�?   �?
└─────────────────────────────────────────────────────────────────�?
                               �?
                               �?
┌─────────────────────────────────────────────────────────────────�?
�?                       编排�?(Orchestration)                    �?
�? ┌─────────────────────────────────────────────────────────�?   �?
�? �?                   Temporal 集群                         �?   �?
�? �? ┌──────────────�? ┌──────────────�? ┌──────────────�?  �?   �?
�? �? �? 编排 Worker  �? �? 认知 Worker  �? �?KEDA 扩缩�? �?  �?   �?
�? �? �?default-queue�? �?vision-queue �? �?             �?  �?   �?
�? �? └──────────────�? └──────────────�? └──────────────�?  �?   �?
�? └─────────────────────────────────────────────────────────�?   �?
└─────────────────────────────────────────────────────────────────�?
                               �?
                               �?
┌─────────────────────────────────────────────────────────────────�?
�?                    认知计算�?(Cognitive)                       �?
�? ┌─────────────────────────────────────────────────────────�?   �?
�? �?                 LangGraph 运行�?                       �?   �?
�? �? ┌──────────────────────────────────────────────────�?  �?   �?
�? �? �?             SupervisorAgent (总控)               �?  �?   �?
�? �? �? ┌────────────┬────────────┬────────────────�?   �?  �?   �?
�? �? �? �?Objective  �?Stepwise   �?Essay/LabDesign�?   �?  �?   �?
�? �? �? �?Agent      �?Agent      �?Agent          �?   �?  �?   �?
�? �? �? └────────────┴────────────┴────────────────�?   �?  �?   �?
�? �? └──────────────────────────────────────────────────�?  �?   �?
�? �? ┌──────────────────────────────────────────────────�?  �?   �?
�? �? �?             Gemini 3.0 Flash                    �?  �?   �?
�? �? �?       (布局分析 + 深度推理 + 评分)              �?  �?   �?
�? �? └──────────────────────────────────────────────────�?  �?   �?
�? └─────────────────────────────────────────────────────────�?   �?
└─────────────────────────────────────────────────────────────────�?
                               �?
                               �?
┌─────────────────────────────────────────────────────────────────�?
�?                     数据存储�?(Persistence)                    �?
�? ┌─────────────────────────�? ┌─────────────────────────────�?  �?
�? �?PostgreSQL (JSONB)      �? �?Redis 集群                   �?  �?
�? �?�?批改结果              �? �?�?语义缓存 (Write-Through)   �?  �?
�? �?�?LangGraph 检查点      �? �?�?分布式锁                   �?  �?
�? �?�?评分细则              �? �?�?API 限流（令牌桶�?        �?  �?
�? �?�?追踪日志              �? �?�?Pub/Sub 事件通知           �?  �?
�? └─────────────────────────�? └─────────────────────────────�?  �?
└─────────────────────────────────────────────────────────────────�?
```

### 批改工作流时�?

```
用户上传 PDF (批改标准 + 学生作答)
    �?
    �?
┌─────────────────�?
�?PDF �?图像转换   �?(150-300 DPI)
�?保存到对象存�?  �?
└────────┬────────�?
         �?
         �?
┌─────────────────�?
�?Temporal 工作�? �?run_real_grading_workflow
�?启动             �?
└────────┬────────�?
         �?
         �?
┌─────────────────�?
�?1. Intake       �?接收文件
└────────┬────────�?
         �?
         �?
┌─────────────────�?
�?2. Preprocess   �?PDF 预处�?
└────────┬────────�?
         �?
         �?
┌─────────────────�?
�?3. Parse        �?RubricParserService
�?   评分标准解析  �?提取评分点和总分
└────────┬────────�?
         �?
         �?
┌─────────────────�?
�?4. Identify     �?StudentIdentificationService
�?   学生识别      �?识别学生边界
└────────┬────────�?
         �?
         �?(扇出)
┌─────────────────�?
�?5. Grade        �?StrictGradingService
�?   逐题批改      �?并行批改每个学生
�?┌─────────────�?�?
�?�?缓存检�?   �?�?
�?�?    �?     �?�?
�?�?题型分析    �?�?SupervisorAgent
�?�?    �?     �?�?
�?�?智能体派�? �?�?ObjectiveAgent/StepwiseAgent/...
�?�?    �?     �?�?
�?�?多步推理    �?�?视觉提取 �?评分映射 �?自我反�?
�?�?    �?     �?�?
�?�?结果缓存    �?�?
�?└─────────────�?�?
└────────┬────────�?
         �?
         �?(扇入)
┌─────────────────�?
�?6. Review       �?结果聚合
�?   置信度检�?   �?
└────────┬────────�?
         �?
    ┌────┴────�?
    �?        �?
    �?        �?
┌───────�?┌───────────�?
�?Export�?�?人工审核   �?(置信�?< 0.75)
�?完成  �?�?          �?
└───────�?└───────────�?
```

---

## 后端模块

### 目录结构

```
src/
├── api/                    # FastAPI 应用�?
�?  ├── main.py             # 应用入口 (lifespan/CORS/异常处理)
�?  ├── routes/
�?  �?  ├── batch.py        # 批量提交 (1122行，核心批改逻辑)
�?  �?  ├── submissions.py  # 提交管理
�?  �?  ├── rubrics.py      # 评分细则
�?  �?  └── reviews.py      # 人工审核
�?  └── middleware/         # 限流中间�?
�?
├── agents/                 # LangGraph 智能体层
�?  ├── supervisor.py       # SupervisorAgent 总控调度
�?  ├── pool.py             # AgentPool 智能体池
�?  ├── base.py             # BaseGradingAgent 基类
�?  ├── grading_agent.py    # 通用批改智能�?
�?  ├── nodes/              # LangGraph 节点
�?  �?  ├── vision_extraction.py
�?  �?  ├── rubric_mapping.py
�?  �?  ├── critique.py
�?  �?  └── finalization.py
�?  └── specialized/        # 专业智能�?
�?      ├── objective.py    # 选择�?判断�?
�?      ├── stepwise.py     # 计算�?
�?      ├── essay.py        # 作文/简�?
�?      └── lab_design.py   # 实验设计
�?
├── services/               # 业务服务�?(21个服�?
�?  ├── rubric_parser.py    # 评分标准解析
�?  ├── student_identification.py  # 学生识别
�?  ├── strict_grading.py   # 严格批改服务
�?  ├── cache.py            # 语义缓存
�?  ├── cached_grading.py   # 缓存批改
�?  ├── cache_warmup.py     # 缓存预热
�?  ├── multi_layer_cache.py  # 多层缓存
�?  ├── rate_limiter.py     # 限流�?
�?  ├── distributed_transaction.py  # 分布式事�?
�?  ├── tracing.py          # 追踪服务
�?  ├── enhanced_api.py     # 增强API服务
�?  ├── llm_reasoning.py # Gemini推理
�?  ├── layout_analysis.py  # 布局分析
�?  ├── rubric.py           # 评分细则管理
�?  ├── submission.py       # 提交管理
�?  └── storage.py          # 存储服务
�?
├── workflows/              # Temporal 工作流层
�?  ├── enhanced_workflow.py  # 增强工作流混�?(1523�?
�?  �?  # EnhancedWorkflowMixin: 进度查询/事件接收/分布式锁
�?  ├── batch_grading.py    # 批量批改工作�?
�?  ├── exam_paper.py       # 试卷处理工作�?
�?  └── question_grading.py # 题目批改工作�?
�?
├── activities/             # Temporal Activities
├── workers/                # Worker 入口
�?  ├── orchestration_worker.py  # 编排 Worker
�?  └── cognitive_worker.py      # 认知计算 Worker
�?
├── models/                 # Pydantic 数据模型
�?  ├── state.py            # GradingState/ContextPack
�?  ├── enums.py            # QuestionType 枚举
�?  └── ...
�?
├── repositories/           # 数据访问�?
└── utils/                  # 工具函数
    └── pool_manager.py     # 统一连接池管�?
```

### 核心组件详解

#### 1. SupervisorAgent (总控调度)

负责分析题型并动态派生合适的批改智能体：

- **核心模型**: Gemini 3.0 Flash (Vision-Native)
- **置信度阈�?*: 0.75 (低于此值触发二次评�?

**题型映射**�?
| QuestionType | Agent | 用�?|
|--------------|-------|------|
| OBJECTIVE | ObjectiveAgent | 选择�?判断�?|
| STEPWISE | StepwiseAgent | 计算�?|
| ESSAY | EssayAgent | 作文/简�?|
| LAB_DESIGN | LabDesignAgent | 实验设计 |

#### 2. LayoutAnalysisService (布局分析)

- **模型**: Gemini 3.0 Flash
- **输入**: 试卷图像 (Base64)
- **输出**: 结构化题目边界框 (BoundingBox)

---

## 前端模块

### 技术栈

- **框架**: Next.js 16 (App Router)
- **UI �?*: React 19
- **3D 渲染**: Three.js + React Three Fiber (R3F)
- **工作流可视化**: ReactFlow
- **状态管�?*: Zustand
- **样式**: Tailwind CSS 4

### 目录结构

```
frontend/
├── src/
�?  ├── app/                # 页面路由
�?  �?  ├── page.tsx        # Landing Page (Antigravity 视觉)
�?  �?  └── console/        # 批改控制�?
�?  �?      └── page.tsx    # 控制台主�?(WorkflowGraph + Results)
�?  ├── components/         # UI 组件
�?  �?  ├── WorkflowGraph/  # ReactFlow 工作流可视化
�?  �?  ├── NodeInspector/  # 节点详情侧边�?
�?  �?  ├── ResultsView/    # 批改结果展示
�?  �?  └── Background/     # Three.js 粒子背景
�?  ├── store/              # Zustand 状态存�?
�?  └── hooks/              # 自定�?Hooks (WebSocket �?
```

---

## API 接口

### 核心端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/batch/submit` | POST | 批量提交 PDF (评分标准 + 学生作答) |
| `/batch/grade-cached` | POST | 优化的批量批�?(Context Caching) |
| `/batch/ws/{batch_id}` | WS | 实时进度推�?|
| `/api/v1/submissions` | GET | 获取提交列表 |
| `/api/v1/reviews/{id}` | POST | 提交人工审核结果 |

---

## 部署架构

### 容器�?

- **Docker Compose**: 用于本地开发和测试
- **Kubernetes**: 生产环境部署，包�?HPA 配置

### 自动扩缩�?(KEDA)

基于 Temporal 任务队列堆积情况，自动扩缩容 `Cognitive Worker`�?

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: cognitive-worker-scaler
spec:
  scaleTargetRef:
    name: cognitive-worker
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: temporal_task_queue_backlog
      threshold: '10'
```

---

## 开发指�?

### 环境设置

1. **依赖安装**:
   ```bash
   uv sync
   cd frontend && npm install
   ```

2. **环境变量**:
   复制 `.env.example` �?`.env` 并配置：
   - `LLM_API_KEY`
   - `DATABASE_URL`
   - `REDIS_URL`
   - `TEMPORAL_ADDRESS`

### 启动服务

1. **启动基础设施**: `docker-compose up -d postgres redis temporal`
2. **启动后端 API**: `uvicorn src.api.main:app --reload --port 8001`
3. **启动 Workers**: 
   - `python -m src.workers.orchestration_worker`
   - `python -m src.workers.cognitive_worker`
4. **启动前端**: `cd frontend && npm run dev`

---

## 项目状�?

### 模块完成�?

- [x] 核心批改引擎 (100%)
- [x] 动态智能体调度 (100%)
- [x] 批量处理与分�?(100%)
- [x] Context Caching 优化 (100%)
- [x] Temporal 工作流编�?(100%)
- [ ] 前端控制台可视化 (80% - 正在完善结果展示)
- [ ] 自动化测试覆盖率 (75%)

### 技术债务

- [ ] 优化 PDF 转换速度（考虑使用多进程）
- [ ] 增加更多学科的专业智能体（如物理实验、化学方程式�?
- [ ] 完善多轮对话修正逻辑
