# Project Structure

```
.
├── src/
│   ├── api/                    # FastAPI 应用
│   │   ├── main.py             # 应用入口
│   │   ├── routes/             # API 路由
│   │   │   ├── submissions.py  # 提交相关接口
│   │   │   ├── rubrics.py      # 评分细则接口
│   │   │   └── reviews.py      # 人工审核接口
│   │   └── middleware/         # 中间件（限流等）
│   │
│   ├── models/                 # Pydantic 数据模型
│   │   ├── submission.py       # 提交相关模型
│   │   ├── grading.py          # 批改结果模型
│   │   ├── rubric.py           # 评分细则模型
│   │   └── state.py            # LangGraph 状态定义
│   │
│   ├── services/               # 业务服务层
│   │   ├── submission.py       # 提交处理服务
│   │   ├── layout_analysis.py  # 页面分割服务
│   │   ├── cache.py            # 语义缓存服务
│   │   ├── rate_limiter.py     # 限流服务
│   │   └── rubric.py           # 评分细则服务
│   │
│   ├── agents/                 # LangGraph 智能体
│   │   ├── grading_agent.py    # 批改智能体图定义
│   │   └── nodes/              # 图节点实现
│   │       ├── vision.py       # 视觉提取节点
│   │       ├── scoring.py      # 评分映射节点
│   │       ├── critique.py     # 自我反思节点
│   │       └── finalize.py     # 最终化节点
│   │
│   ├── workflows/              # Temporal 工作流
│   │   ├── exam_paper.py       # 试卷级父工作流
│   │   └── question_grading.py # 题目级子工作流
│   │
│   ├── activities/             # Temporal Activities
│   │   ├── segment.py          # 文档分割 Activity
│   │   ├── grade.py            # 批改 Activity
│   │   ├── notify.py           # 通知 Activity
│   │   └── persist.py          # 持久化 Activity
│   │
│   ├── workers/                # Temporal Worker 入口
│   │   ├── orchestration_worker.py
│   │   └── cognitive_worker.py
│   │
│   ├── repositories/           # 数据访问层
│   │   ├── submission.py
│   │   ├── grading_result.py
│   │   └── rubric.py
│   │
│   └── utils/                  # 工具函数
│       ├── coordinates.py      # 坐标转换
│       ├── hashing.py          # 哈希计算
│       └── pdf.py              # PDF 处理
│
├── tests/                      # 测试目录
│   ├── unit/                   # 单元测试
│   ├── property/               # 属性测试（Hypothesis）
│   └── integration/            # 集成测试
│
├── alembic/                    # 数据库迁移
│   └── versions/
│
├── k8s/                        # Kubernetes 配置
│   ├── deployments/
│   ├── services/
│   └── keda/
│
└── .kiro/
    ├── specs/                  # 功能规格文档
    └── steering/               # AI 引导规则
```

## 架构分层

1. **接入层**：API Gateway → Submission Service → Object Storage
2. **编排层**：Temporal Cluster → Orchestration Worker → Task Queues
3. **认知计算层**：Cognitive Worker Pool → LangGraph Runtime → Gemini Models
4. **数据存储层**：PostgreSQL (JSONB) + Redis (Cache)

## Task Queue 分离

- `default-queue`：轻量级任务（通知、状态更新）
- `vision-compute-queue`：重计算任务（Gemini API 调用、LangGraph 推理）
