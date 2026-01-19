# 快速参考卡�?

## 系统概览

**AI 批改系统** - 生产级纯视觉自动评估引擎

### 核心特�?
- 🎯 纯视觉优先（�?OCR�?
- 🤖 智能体推理（LangGraph�?
- 📊 多学生自动识�?
- 🔄 持久化执行（Temporal�?
- 👥 人工审核介入

## 快速开�?

### 1. 安装依赖
```bash
uv sync
```

### 2. 配置环境
```bash
cp .env.example .env
# 编辑 .env，设�?LLM_API_KEY
```

### 3. 启动服务
```bash
# 启动 API
uvicorn src.api.main:app --reload

# 启动 Worker（另一个终端）
python -m src.workers.cognitive_worker
```

### 4. 测试批改
```bash
# 同步批改（推荐用于测试）
python test_full_grading.py

# 或使�?API
curl -X POST "http://localhost:8000/batch/grade-sync" \
  -F "rubric_file=@批改标准.pdf" \
  -F "answer_file=@学生作答.pdf" \
  -F "api_key=YOUR_API_KEY"
```

## API 端点速查

### 批量提交
| 端点 | 方法 | 说明 |
|------|------|------|
| `/batch/grade-sync` | POST | 同步批改 |
| `/batch/submit` | POST | 异步批改 |
| `/batch/status/{batch_id}` | GET | 查询状�?|
| `/batch/results/{batch_id}` | GET | 获取结果 |
| `/batch/ws/{batch_id}` | WS | 实时推�?|

### 提交管理
| 端点 | 方法 | 说明 |
|------|------|------|
| `/submissions` | POST | 创建提交 |
| `/submissions/{id}` | GET | 获取提交 |
| `/submissions/{id}/status` | GET | 查询状�?|

### 评分细则
| 端点 | 方法 | 说明 |
|------|------|------|
| `/rubrics` | POST | 创建细则 |
| `/rubrics/{id}` | GET | 获取细则 |
| `/rubrics/{id}` | PUT | 更新细则 |

### 人工审核
| 端点 | 方法 | 说明 |
|------|------|------|
| `/reviews` | GET | 获取待审�?|
| `/reviews/{id}` | POST | 提交审核 |

## 文件结构

```
src/
├── api/                    # API �?
�?  ├── main.py            # 应用入口
�?  ├── routes/            # 路由
�?  �?  ├── batch.py       # 批量提交
�?  �?  ├── submissions.py # 提交管理
�?  �?  ├── rubrics.py     # 评分细则
�?  �?  └── reviews.py     # 人工审核
�?  └── middleware/        # 中间�?
�?
├── services/              # 业务逻辑
�?  ├── student_identification.py  # 学生识别
�?  ├── rubric_parser.py           # 标准解析
�?  ├── strict_grading.py          # 严格批改
�?  ├── layout_analysis.py         # 页面分割
�?  └── cache.py                   # 缓存管理
�?
├── agents/                # 智能�?
�?  ├── grading_agent.py   # 批改智能�?
�?  ├── supervisor.py      # 总控智能�?
�?  └── specialized/       # 专业智能�?
�?      ├── objective.py   # 选择�?
�?      ├── stepwise.py    # 计算�?
�?      ├── essay.py       # 作文�?
�?      └── lab_design.py  # 实验�?
�?
├── workflows/             # 工作�?
�?  ├── batch_grading.py   # 批量批改
�?  ├── exam_paper.py      # 试卷�?
�?  └── question_grading.py # 题目�?
�?
├── models/                # 数据模型
�?  ├── submission.py      # 提交模型
�?  ├── grading.py         # 批改结果
�?  ├── rubric.py          # 评分细则
�?  └── state.py           # 状态定�?
�?
└── utils/                 # 工具函数
    ├── coordinates.py     # 坐标转换
    ├── hashing.py         # 哈希计算
    └── database.py        # 数据库工�?
```

## 常用命令

### 开�?
```bash
make dev              # 启动开发环�?
make dev-logs         # 查看日志
make dev-stop         # 停止开发环�?
```

### 测试
```bash
make test             # 运行所有测�?
make test-unit        # 单元测试
make test-property    # 属性测�?
make test-coverage    # 覆盖率报�?
```

### 代码质量
```bash
make lint             # 代码检�?
make format           # 代码格式�?
make type-check       # 类型检�?
make quality          # 所有检�?
```

### 数据�?
```bash
make db-migrate       # 运行迁移
make db-rollback      # 回滚迁移
make db-revision      # 创建迁移
```

### Kubernetes
```bash
make k8s-deploy       # 部署�?K8s
make k8s-status       # 查看状�?
make k8s-logs-api     # API 日志
make k8s-logs-worker  # Worker 日志
```

## 关键概念

### 学生识别
系统采用两阶段策略：
1. **直接识别** - 从试卷上识别学生信息
2. **推理识别** - 通过题目顺序循环检测推断边�?

### 评分标准
支持两种格式�?
1. **标准格式** - 分离的答案键
2. **嵌入式格�?* - 答案在题目页面上

### 批改流程
```
PDF 转图�?�?解析标准 �?识别学生 �?逐个批改 �?返回结果
```

### 智能体类�?
- **ObjectiveAgent** - 选择�?判断�?
- **StepwiseAgent** - 计算�?
- **EssayAgent** - 作文�?
- **LabDesignAgent** - 实验设计�?
- **SupervisorAgent** - 动态派�?

## 性能指标

| 指标 | 数�?|
|------|------|
| 页面分割 | 3-5 �?|
| 单题批改 | 15-20 �?|
| 2 学生完整 | 2-3 分钟 |
| 30 学生完整 | 30-45 分钟 |
| 单学生成�?| $0.20-0.25 |

## 环境变量

### 必需
```bash
LLM_API_KEY=your_api_key
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://host:6379
```

### 可�?
```bash
TEMPORAL_HOST=localhost:7233
S3_ENDPOINT=http://minio:9000
LOG_LEVEL=INFO
```

## 故障排查

### 问题：API 无法连接
```bash
# 检�?API 是否运行
curl http://localhost:8000/health

# 查看日志
docker-compose logs api
```

### 问题：Gemini API 错误
```bash
# 检�?API Key
echo $LLM_API_KEY

# 测试 API 连接
python -c "from langchain_google_genai import ChatGoogleGenerativeAI; ..."
```

### 问题：数据库连接失败
```bash
# 检�?PostgreSQL
psql $DATABASE_URL

# 运行迁移
alembic upgrade head
```

### 问题：Redis 连接失败
```bash
# 检�?Redis
redis-cli ping

# 查看 Redis 日志
docker-compose logs redis
```

## 文档导航

| 文档 | 说明 |
|------|------|
| `README.md` | 项目概览 |
| `QUICKSTART.md` | 快速开�?|
| `BATCH_API_GUIDE.md` | API 详细指南 |
| `PROJECT_STATUS.md` | 项目状�?|
| `TOKEN_CONSUMPTION_ANALYSIS.md` | 成本分析 |
| `GRADING_TEST_REPORT.md` | 测试报告 |
| `.kiro/specs/` | 需求规�?|

## 联系方式

- 📧 Email: support@example.com
- 💬 Issues: GitHub Issues
- 📚 Docs: https://docs.example.com

## 许可�?

MIT

---

**最后更�?*: 2025-12-13  
**版本**: 1.0.0

