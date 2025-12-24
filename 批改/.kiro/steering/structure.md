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
│   ├── graphs/                 # LangGraph 工作流图
│   │   ├── state.py            # Graph 状态定义
│   │   ├── retry.py            # 重试策略
│   │   ├── exam_paper.py       # 试卷批改 Graph
│   │   ├── batch_grading.py    # 批量批改 Graph
│   │   ├── rule_upgrade.py     # 规则升级 Graph
│   │   └── nodes/              # Graph 节点实现
│   │       ├── segment.py      # 文档分割节点
│   │       ├── grade.py        # 批改节点
│   │       ├── persist.py      # 持久化节点
│   │       ├── notify.py       # 通知节点
│   │       └── review.py       # 人工审核节点
│   │
│   ├── orchestration/          # 编排器抽象层
│   │   ├── base.py             # 编排器接口
│   │   └── langgraph_orchestrator.py  # LangGraph 实现
│   │
│   ├── workers/                # Worker 入口
│   │   └── langgraph_worker.py # LangGraph Worker
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
2. **编排层**：LangGraph Orchestrator → LangGraph Worker → PostgreSQL Checkpointer
3. **认知计算层**：LangGraph Runtime → Gemini Models
4. **数据存储层**：PostgreSQL (JSONB + Checkpoint) + Redis (Cache)

## LangGraph Graphs

- `exam_paper`: 单份试卷批改流程（分割 → 批改 → 审核 → 持久化 → 通知）
- `batch_grading`: 批量试卷批改（边界检测 → 并行扇出 → 聚合 → 持久化）
- `rule_upgrade`: 规则自演化升级（挖掘 → 补丁 → 测试 → 部署）
