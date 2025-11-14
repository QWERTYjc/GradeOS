# AI批改系统 - 故障排除指南

## 常见问题

### 1. 依赖安装问题

#### 问题：pip install失败

**症状**：
```
ERROR: Could not find a version that satisfies the requirement...
```

**解决方案**：
```bash
# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或升级pip
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### 问题：LangGraph导入错误

**症状**：
```
ModuleNotFoundError: No module named 'langgraph'
```

**解决方案**：
```bash
pip install langgraph>=0.0.40 langchain>=0.1.0
```

### 2. 数据库问题

#### 问题：SQLite数据库损坏

**症状**：
```
sqlite3.DatabaseError: database disk image is malformed
```

**解决方案**：
```bash
# 删除并重建数据库
del ai_correction.db
python local_runner.py
```

#### 问题：PostgreSQL连接失败

**症状**：
```
psycopg2.OperationalError: could not connect to server
```

**解决方案**：
```bash
# 1. 检查连接字符串
echo $DATABASE_URL

# 2. 测试连接
python -c "from config.railway_postgres import get_railway_config; get_railway_config().test_connection()"

# 3. 检查防火墙和网络
```

### 3. LLM API问题

#### 问题：OpenAI API认证失败

**症状**：
```
openai.error.AuthenticationError: Invalid API Key
```

**解决方案**：
```bash
# 检查API Key
echo $OPENAI_API_KEY

# 更新.env.local文件
OPENAI_API_KEY=sk-your-actual-key
```

#### 问题：Token限制超出

**症状**：
```
openai.error.RateLimitError: Rate limit exceeded
```

**解决方案**：
```bash
# 1. 使用高效模式
mode=efficient

# 2. 调整批次阈值
EFFICIENT_MODE_THRESHOLD=8000  # 增大阈值

# 3. 增加重试次数
MAX_RETRIES=5
```

### 4. 工作流问题

#### 问题：Checkpoint保存失败

**症状**：
```
Error saving checkpoint: ...
```

**解决方案**：
```bash
# 1. 使用MemorySaver（开发环境）
ENVIRONMENT=development

# 2. 检查PostgreSQL权限
# 确保数据库用户有写权限
```

#### 问题：并行处理卡住

**症状**：
工作流长时间无响应

**解决方案**：
```bash
# 1. 减少并行worker数
MAX_PARALLEL_WORKERS=2

# 2. 检查日志
cat logs/ai_correction.log

# 3. 重启应用
```

### 5. 性能问题

#### 问题：处理速度慢

**症状**：
单题处理超过10秒

**解决方案**：
```bash
# 1. 使用高效模式
mode=efficient

# 2. 增加并行worker
MAX_PARALLEL_WORKERS=8

# 3. 检查网络延迟
# 使用国内API代理（如有）
```

#### 问题：内存占用高

**症状**：
系统内存不足

**解决方案**：
```bash
# 1. 减少批次大小
PROFESSIONAL_MODE_THRESHOLD=3000

# 2. 限制并行任务
MAX_PARALLEL_WORKERS=4

# 3. 清理旧日志
del /q logs\*.log
```

### 6. 学生匹配问题

#### 问题：学生信息匹配失败

**症状**：
无法匹配学生或误匹配

**解决方案**：
```bash
# 1. 降低相似度阈值
similarity_threshold=0.6  # 从0.75降低

# 2. 检查OCR质量
# 确保学生姓名和学号清晰

# 3. 手动创建学生记录
python -c "from functions.database.student_matcher import StudentMatcher; ..."
```

### 7. 提示词问题

#### 问题：评分结果不准确

**症状**：
评分明显偏离预期

**解决方案**：
```bash
# 1. 切换到专业模式
mode=professional

# 2. 优化评分标准
# 使评分标准更具体明确

# 3. 调整温度参数
# 在Agent中设置temperature=0.1
```

## 日志分析

### 查看日志

```bash
# 最新日志
tail -f logs/ai_correction.log

# 错误日志
grep ERROR logs/ai_correction.log

# 特定任务日志
grep "task_12345" logs/ai_correction.log
```

### 日志级别

```bash
# .env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

## 性能调优

### Token优化

```bash
# 高效模式设置
EFFICIENT_MODE_THRESHOLD=6000
mode=efficient

# 预期Token消耗：~500/题
```

### 并行优化

```bash
# 根据CPU核心数调整
# 推荐：核心数 * 2
MAX_PARALLEL_WORKERS=8
```

### 数据库优化

```bash
# PostgreSQL连接池
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# SQLite优化
# 使用WAL模式（自动）
```

## 错误代码

| 代码 | 含义 | 解决方案 |
|------|------|---------|
| E001 | API Key无效 | 检查OPENAI_API_KEY |
| E002 | 数据库连接失败 | 检查DATABASE_URL |
| E003 | 文件未找到 | 检查文件路径 |
| E004 | Token超限 | 使用高效模式 |
| E005 | 学生匹配失败 | 降低相似度阈值 |

## 联系支持

如果问题仍未解决：

1. 查看完整日志：`logs/ai_correction.log`
2. 检查系统状态：运行 `python local_runner.py`
3. 查看文档：[QUICKSTART.md](../QUICKSTART.md)
4. 提交Issue：包含错误日志和环境信息

## 预防措施

### 定期维护

```bash
# 1. 清理日志
find logs/ -name "*.log" -mtime +7 -delete

# 2. 数据库备份
cp ai_correction.db backups/

# 3. 更新依赖
pip install -r requirements.txt --upgrade
```

### 监控指标

- Token使用量
- API错误率
- 平均处理时间
- 数据库查询性能

### 最佳实践

1. 定期备份数据库
2. 监控API使用量
3. 及时更新依赖
4. 使用版本控制
5. 配置告警系统
