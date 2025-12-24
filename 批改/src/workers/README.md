# LangGraph Worker

后台执行 LangGraph Graph 的 Worker 进程。

## 启动方式

```bash
python -m src.workers.langgraph_worker
```

## 环境变量

| 变量名 | 默认值 | 说明 |
|-------|-------|------|
| `WORKER_POLL_INTERVAL` | `1.0` | 轮询间隔（秒） |
| `WORKER_MAX_CONCURRENT` | `10` | 最大并发 run 数 |
| `DATABASE_URL` | - | PostgreSQL 连接字符串 |
| `REDIS_URL` | - | Redis 连接字符串 |

## 功能

- 轮询 `runs` 表中的 pending 任务
- 并发执行 LangGraph Graph
- 支持优雅关闭（SIGINT/SIGTERM）
- 支持崩溃恢复（从 checkpoint 恢复）
