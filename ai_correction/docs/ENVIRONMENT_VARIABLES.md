# 环境变量配置文档

## 概述

AI批改系统支持灵活的环境变量配置,适配本地开发、测试和生产部署等不同场景。

## 配置文件

系统支持以下配置文件(按优先级排序):

1. `.env.local` - 本地开发环境(不提交到git)
2. `.env.development` - 开发环境
3. `.env.test` - 测试环境
4. `.env.production` - 生产环境
5. `.env` - 默认配置(提供模板)

## 核心环境变量

### 数据库配置

#### DATABASE_URL
数据库连接字符串

**本地开发**:
```bash
DATABASE_URL=sqlite:///ai_correction.db
```

**生产环境 (PostgreSQL)**:
```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

**示例**:
- SQLite: `sqlite:///./ai_correction.db`
- PostgreSQL: `postgresql://postgres:password@localhost:5432/ai_correction`
- Railway: `postgresql://user:pass@railway.app:5432/railway`

### LLM配置

#### OPENAI_API_KEY
OpenAI API密钥 (必需)

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

#### OPENAI_API_BASE
OpenAI API基础URL (可选)

```bash
# 默认
OPENAI_API_BASE=https://api.openai.com/v1

# 自定义代理
OPENAI_API_BASE=https://your-proxy.com/v1
```

#### GEMINI_API_KEY
Google Gemini API密钥 (可选,用于多模态提取)

```bash
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxx
```

### 运行环境配置

#### ENVIRONMENT
运行环境标识

```bash
ENVIRONMENT=development  # development | test | production
```

影响:
- `development`: 使用MemorySaver, 详细日志
- `test`: 模拟外部API调用
- `production`: PostgresSaver, 优化日志

#### DEFAULT_MODE
默认批改模式

```bash
DEFAULT_MODE=professional  # efficient | professional
```

- `efficient`: 高效模式,节省66% token
- `professional`: 专业模式,详细反馈

### 批次处理配置

#### EFFICIENT_MODE_THRESHOLD
高效模式单批次token上限

```bash
EFFICIENT_MODE_THRESHOLD=6000
```

计算公式:
```
batch_size = EFFICIENT_MODE_THRESHOLD / (500 tokens/题)
```

#### PROFESSIONAL_MODE_THRESHOLD
专业模式单批次token上限

```bash
PROFESSIONAL_MODE_THRESHOLD=4000
```

计算公式:
```
batch_size = PROFESSIONAL_MODE_THRESHOLD / (1500 tokens/题)
```

#### MAX_PARALLEL_WORKERS
最大并行worker数量

```bash
MAX_PARALLEL_WORKERS=4
```

建议值:
- 本地开发: 2-4
- 生产环境: 4-8
- 大规模批改: 8-16

### 日志配置

#### LOG_LEVEL
日志级别

```bash
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR
```

#### LOG_FILE
日志文件路径

```bash
LOG_FILE=logs/ai_correction.log
```

### 班级系统集成配置

#### CLASS_SYSTEM_API_URL
班级系统API基础URL

```bash
CLASS_SYSTEM_API_URL=https://class-system.example.com/api
```

#### CLASS_SYSTEM_API_KEY
班级系统API密钥

```bash
CLASS_SYSTEM_API_KEY=your-class-system-api-key
```

#### PUSH_ENABLED
是否启用班级系统推送

```bash
PUSH_ENABLED=false  # 本地开发关闭
PUSH_ENABLED=true   # 生产环境启用
```

### 性能配置

#### MAX_RETRIES
API调用最大重试次数

```bash
MAX_RETRIES=3
```

#### REQUEST_TIMEOUT
请求超时时间(秒)

```bash
REQUEST_TIMEOUT=30
```

#### CHECKPOINT_INTERVAL
Checkpoint保存间隔(秒)

```bash
CHECKPOINT_INTERVAL=60
```

## 环境配置示例

### 本地开发环境 (.env.local)

```bash
# 数据库
DATABASE_URL=sqlite:///ai_correction.db

# LLM
OPENAI_API_KEY=sk-your-key-here
OPENAI_API_BASE=https://api.openai.com/v1

# 运行环境
ENVIRONMENT=development
DEFAULT_MODE=professional

# 批次处理
EFFICIENT_MODE_THRESHOLD=6000
PROFESSIONAL_MODE_THRESHOLD=4000
MAX_PARALLEL_WORKERS=4

# 日志
LOG_LEVEL=INFO
LOG_FILE=logs/ai_correction.log

# 其他
MAX_RETRIES=3
REQUEST_TIMEOUT=30
PUSH_ENABLED=false
```

### 测试环境 (.env.test)

```bash
# 数据库
DATABASE_URL=sqlite:///test_ai_correction.db

# LLM (使用mock)
OPENAI_API_KEY=test-key
USE_MOCK_LLM=true

# 运行环境
ENVIRONMENT=test
DEFAULT_MODE=efficient

# 批次处理
EFFICIENT_MODE_THRESHOLD=6000
PROFESSIONAL_MODE_THRESHOLD=4000
MAX_PARALLEL_WORKERS=2

# 日志
LOG_LEVEL=DEBUG
LOG_FILE=logs/test.log

# 其他
MAX_RETRIES=1
REQUEST_TIMEOUT=10
PUSH_ENABLED=false
```

### 生产环境 (.env.production)

```bash
# 数据库
DATABASE_URL=postgresql://user:pass@railway.app:5432/railway

# LLM
OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_API_BASE=https://api.openai.com/v1

# 运行环境
ENVIRONMENT=production
DEFAULT_MODE=professional

# 批次处理
EFFICIENT_MODE_THRESHOLD=8000
PROFESSIONAL_MODE_THRESHOLD=5000
MAX_PARALLEL_WORKERS=8

# 日志
LOG_LEVEL=WARNING
LOG_FILE=/var/log/ai_correction.log

# 班级系统
CLASS_SYSTEM_API_URL=https://class.example.com/api
CLASS_SYSTEM_API_KEY=${CLASS_API_KEY}
PUSH_ENABLED=true

# 性能优化
MAX_RETRIES=5
REQUEST_TIMEOUT=60
CHECKPOINT_INTERVAL=120
```

## 配置验证

### 使用local_runner.py检查配置

```bash
python local_runner.py
```

会自动检查:
- ✅ 必需依赖包
- ✅ 环境变量是否设置
- ✅ API密钥是否有效
- ✅ 数据库连接是否正常

### 手动验证数据库连接

```python
from functions.database.models import check_database_connection

if check_database_connection():
    print("✅ 数据库连接正常")
else:
    print("❌ 数据库连接失败")
```

### 手动验证OpenAI API

```python
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

try:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "test"}],
        max_tokens=5
    )
    print("✅ OpenAI API连接正常")
except Exception as e:
    print(f"❌ OpenAI API连接失败: {e}")
```

## 常见问题

### Q1: 如何切换不同环境?

**方法1**: 使用不同的配置文件
```bash
# 复制对应环境配置
cp .env.production .env
```

**方法2**: 在代码中指定
```python
from dotenv import load_dotenv
load_dotenv('.env.production')
```

**方法3**: 设置ENVIRONMENT变量
```bash
export ENVIRONMENT=production
```

### Q2: 本地开发需要PostgreSQL吗?

**不需要**。本地开发使用SQLite即可:
```bash
DATABASE_URL=sqlite:///ai_correction.db
```

只有生产部署才需要PostgreSQL。

### Q3: 如何保护API密钥安全?

1. **不要提交到git**
   ```bash
   # 在.gitignore中添加
   .env.local
   .env.production
   ```

2. **使用环境变量**
   ```bash
   # 在Railway/Vercel中设置
   OPENAI_API_KEY=sk-xxx
   ```

3. **使用密钥管理服务**
   - AWS Secrets Manager
   - Azure Key Vault
   - GCP Secret Manager

### Q4: 批改速度慢怎么办?

优化配置:
```bash
# 增加并行worker数量
MAX_PARALLEL_WORKERS=8

# 使用高效模式
DEFAULT_MODE=efficient

# 增加批次大小
EFFICIENT_MODE_THRESHOLD=10000
```

### Q5: 如何启用调试日志?

```bash
LOG_LEVEL=DEBUG
```

查看详细日志:
```bash
tail -f logs/ai_correction.log
```

## 安全建议

1. **密钥管理**
   - 使用环境变量而非硬编码
   - 定期轮换API密钥
   - 生产环境使用密钥管理服务

2. **数据库安全**
   - 使用强密码
   - 限制数据库访问IP
   - 启用SSL连接

3. **日志安全**
   - 不要记录敏感信息
   - 定期清理旧日志
   - 限制日志文件访问权限

4. **网络安全**
   - 使用HTTPS
   - 启用防火墙
   - 配置CORS策略

## 参考资料

- [Streamlit Secrets Management](https://docs.streamlit.io/library/advanced-features/secrets-management)
- [Python-dotenv Documentation](https://pypi.org/project/python-dotenv/)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- [Vercel Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)
