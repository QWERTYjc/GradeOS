# GradeOS Platform v2.0 - 快速参考指南

**最后更新**: 2025-12-27  
**版本**: v2.0

---

## 🚀 快速启动

### 启动所有服务

```bash
# 方式 1: 使用 PowerShell 脚本
cd GradeOS-Platform
.\start_dev.ps1

# 方式 2: 手动启动
# 终端 1 - 后端
cd GradeOS-Platform/backend
python -m uvicorn src.api.main:app --reload --port 8001

# 终端 2 - 前端
cd GradeOS-Platform/frontend
npm run dev
```

### 访问应用

| 应用 | URL | 用户名 | 密码 |
|------|-----|--------|------|
| 主应用 | http://localhost:3000 | teacher | 123456 |
| API 文档 | http://localhost:8001/docs | - | - |
| 健康检查 | http://localhost:8001/health | - | - |

---

## 📁 项目结构

```
GradeOS-Platform/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py                 # 主应用
│   │   │   ├── dependencies.py         # 依赖注入
│   │   │   └── routes/
│   │   │       └── batch_langgraph.py  # 批改 API
│   │   ├── orchestration/
│   │   │   └── langgraph_orchestrator.py  # LangGraph 编排器
│   │   ├── graphs/
│   │   │   └── batch_grading.py        # 批改工作流
│   │   └── services/
│   │       ├── gemini_reasoning.py     # Gemini 推理
│   │       └── rubric_parser.py        # 评分标准解析
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── console/
│   │   │   │   └── page.tsx            # 控制台页面
│   │   │   └── teacher/
│   │   │       └── dashboard/
│   │   │           └── page.tsx        # 教师仪表板
│   │   ├── components/
│   │   │   └── console/
│   │   │       └── ResultsView.tsx     # 结果显示
│   │   ├── services/
│   │   │   └── api.ts                  # API 客户端
│   │   ├── store/
│   │   │   └── consoleStore.ts         # 状态管理
│   │   └── types/
│   │       └── index.ts                # 类型定义
│   └── package.json
│
└── docs/
    ├── VIBE_CODING_GUIDE.md            # 代码指南
    └── README.md                        # 文档
```

---

## 🔌 API 端点

### 批改提交

```bash
POST /batch/submit

# 请求
curl -X POST http://localhost:8001/batch/submit \
  -F "exam_id=exam_001" \
  -F "files=@answer1.pdf" \
  -F "files=@answer2.pdf" \
  -F "rubrics=@rubric.pdf" \
  -F "api_key=your_gemini_key"

# 响应
{
  "batch_id": "uuid-123",
  "status": "UPLOADED",
  "total_pages": 50,
  "estimated_completion_time": 120
}
```

### 查询状态

```bash
GET /batch/status/{batch_id}

# 请求
curl http://localhost:8001/batch/status/uuid-123

# 响应
{
  "batch_id": "uuid-123",
  "exam_id": "exam_001",
  "status": "PROCESSING",
  "total_students": 30,
  "completed_students": 15,
  "unidentified_pages": 5
}
```

### 获取结果

```bash
GET /batch/results/{batch_id}

# 请求
curl http://localhost:8001/batch/results/uuid-123

# 响应
{
  "batch_id": "uuid-123",
  "students": [
    {
      "studentName": "张三",
      "score": 85,
      "maxScore": 100,
      "percentage": 85,
      "questionResults": [...]
    }
  ]
}
```

---

## 🔧 常见问题

### Q1: 后端无法启动

**症状**: `ModuleNotFoundError` 或 `ImportError`

**解决方案**:
```bash
# 检查 Python 版本
python --version  # 应该是 3.11+

# 重新安装依赖
pip install -r requirements.txt --force-reinstall

# 清除缓存
pip cache purge
```

### Q2: 前端编译失败

**症状**: `npm ERR!` 或编译错误

**解决方案**:
```bash
# 清除 node_modules
rm -r node_modules
npm install

# 清除 Next.js 缓存
rm -r .next
npm run dev
```

### Q3: 端口已被占用

**症状**: `EADDRINUSE: address already in use :::3000`

**解决方案**:
```powershell
# 查找占用端口的进程
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue

# 杀死进程
Stop-Process -Id <PID> -Force
```

### Q4: 数据库连接失败

**症状**: `connection timeout expired`

**解决方案**:
```bash
# 这是正常的 - 系统运行在离线模式
# 如果需要启用数据库，配置 .env 文件:
DATABASE_URL=postgresql://user:password@localhost:5432/gradeos
```

### Q5: API 返回 500 错误

**症状**: `Internal Server Error`

**解决方案**:
```bash
# 检查后端日志
# 查看 console 输出中的错误信息

# 常见原因:
# 1. Gemini API Key 无效
# 2. 文件格式不支持
# 3. 内存不足
```

---

## 📊 工作流状态

### 批改状态流转

```
UPLOADED
   ↓
PREPROCESSING
   ↓
RUBRIC_PARSING
   ↓
GRADING
   ↓
SEGMENTING
   ↓
REVIEWING
   ↓
COMPLETED
```

### 节点状态

| 状态 | 含义 | 下一步 |
|------|------|--------|
| pending | 等待执行 | 等待前置节点完成 |
| running | 正在执行 | 等待完成 |
| completed | 已完成 | 执行下一个节点 |
| failed | 执行失败 | 重试或人工处理 |

---

## 🔐 安全建议

### 1. API Key 管理

```bash
# 不要在代码中硬编码 API Key
# 使用环境变量
export GEMINI_API_KEY="your_key_here"

# 或在 .env 文件中
GEMINI_API_KEY=your_key_here
```

### 2. 文件上传安全

```python
# 验证文件类型
if not file.filename.endswith('.pdf'):
    raise ValueError("只支持 PDF 文件")

# 检查文件大小
if file.size > 100 * 1024 * 1024:  # 100MB
    raise ValueError("文件过大")

# 扫描恶意内容
# 使用专业的文件扫描服务
```

### 3. 数据隐私

```bash
# 启用 HTTPS
# 使用 SSL 证书

# 加密敏感数据
# 使用数据库加密

# 定期备份
# 实施灾难恢复计划
```

---

## 📈 性能优化

### 1. 前端优化

```typescript
// 使用 React.memo 避免不必要的重新渲染
export const ResultsView = React.memo(({ results }) => {
  // ...
});

// 使用 useCallback 缓存回调函数
const handleSubmit = useCallback(async (data) => {
  // ...
}, []);

// 使用 useMemo 缓存计算结果
const totalScore = useMemo(() => {
  return results.reduce((sum, r) => sum + r.score, 0);
}, [results]);
```

### 2. 后端优化

```python
# 使用连接池
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40
)

# 使用缓存
from functools import lru_cache

@lru_cache(maxsize=128)
def parse_rubric(rubric_text: str):
    # ...
    pass

# 使用异步处理
async def grade_batch_parallel(pages, rubric):
    # ...
    pass
```

### 3. 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_batch_id ON submissions(batch_id);
CREATE INDEX idx_exam_id ON submissions(exam_id);

-- 使用分区
PARTITION BY RANGE (YEAR(created_at))

-- 定期清理
DELETE FROM submissions WHERE created_at < DATE_SUB(NOW(), INTERVAL 90 DAY);
```

---

## 🧪 测试

### 单元测试

```bash
# 后端测试
cd backend
pytest tests/ -v

# 前端测试
cd frontend
npm test
```

### 集成测试

```bash
# 测试 API 端点
curl -X POST http://localhost:8001/batch/submit \
  -F "files=@test.pdf" \
  -F "rubrics=@rubric.pdf"

# 测试 WebSocket
wscat -c ws://localhost:8001/ws/batch_id
```

### 性能测试

```bash
# 使用 Apache Bench
ab -n 1000 -c 10 http://localhost:3000/

# 使用 wrk
wrk -t4 -c100 -d30s http://localhost:3000/
```

---

## 📚 文档链接

| 文档 | 位置 | 用途 |
|------|------|------|
| 完整报告 | `COMPLETION_REPORT_v2.md` | 项目完成情况 |
| 技术细节 | `TECHNICAL_IMPLEMENTATION_DETAILS.md` | 实现细节 |
| 快速开始 | `GradeOS-Platform/QUICK_START.md` | 快速启动 |
| 代码指南 | `GradeOS-Platform/docs/VIBE_CODING_GUIDE.md` | 代码规范 |
| API 文档 | http://localhost:8001/docs | API 参考 |

---

## 🆘 获取帮助

### 查看日志

```bash
# 后端日志
tail -f logs/app.log

# 前端日志
# 打开浏览器开发者工具 (F12)
# 查看 Console 标签
```

### 调试模式

```bash
# 启用调试日志
export DEBUG=*
npm run dev

# 或在 Python 中
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 联系支持

- 📧 Email: support@gradeos.com
- 💬 Discord: https://discord.gg/gradeos
- 🐛 Issues: https://github.com/gradeos/platform/issues

---

## 📋 检查清单

启动前检查:

- [ ] Python 3.11+ 已安装
- [ ] Node.js 18+ 已安装
- [ ] 依赖已安装 (`pip install -r requirements.txt`)
- [ ] npm 依赖已安装 (`npm install`)
- [ ] 环境变量已配置 (`.env` 文件)
- [ ] 端口 3000 和 8001 未被占用

启动后检查:

- [ ] 后端健康检查通过 (http://localhost:8001/health)
- [ ] 前端页面加载成功 (http://localhost:3000)
- [ ] 登录功能正常
- [ ] API 文档可访问 (http://localhost:8001/docs)
- [ ] 控制台页面就绪

---

**版本**: v2.0  
**最后更新**: 2025-12-27  
**状态**: ✅ 生产就绪
