# 部署指南

本文档提供 AI 批改系统的快速部署指南。

## 部署选项

### 1. 本地开发（推荐用于开发和测试）

使用 Docker Compose 一键启动完整环境：

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 GEMINI_API_KEY

# 2. 启动所有服务
make dev

# 3. 访问服务
# - API: http://localhost:8000/docs
# - Temporal UI: http://localhost:8080
# - MinIO: http://localhost:9001
```

### 2. Kubernetes 生产部署

#### 前置条件

- Kubernetes 集群（>= 1.24）
- kubectl 已配置
- NGINX Ingress Controller
- KEDA（可选）
- Temporal 集群

#### 部署步骤

```bash
# 1. 构建镜像
make build REGISTRY=your-registry VERSION=v1.0.0

# 2. 推送镜像
make push REGISTRY=your-registry VERSION=v1.0.0

# 3. 配置密钥
# 编辑 k8s/secrets.yaml，替换所有 CHANGE_ME_IN_PRODUCTION

# 4. 部署
cd k8s && bash deploy.sh

# 或使用 make
make k8s-deploy
```

#### 验证部署

```bash
# 查看 Pod 状态
kubectl get pods -n grading-system

# 查看服务
kubectl get svc -n grading-system

# 查看日志
kubectl logs -n grading-system -l app=api-service -f
```

## 配置说明

### 必需的环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `GEMINI_API_KEY` | Gemini API 密钥 | `AIza...` |
| `DATABASE_URL` | PostgreSQL 连接字符串 | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis 连接字符串 | `redis://host:6379` |
| `TEMPORAL_HOST` | Temporal 服务地址 | `temporal:7233` |
| `S3_ENDPOINT` | S3/MinIO 端点 | `http://minio:9000` |
| `S3_ACCESS_KEY` | S3 访问密钥 | `minioadmin` |
| `S3_SECRET_KEY` | S3 密钥 | `minioadmin` |

### 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RATE_LIMIT_REQUESTS` | `100` | 每分钟请求限制 |
| `CACHE_TTL_DAYS` | `30` | 缓存过期时间（天） |
| `WORKER_CONCURRENCY` | `10` | Worker 并发数 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 扩缩容

### KEDA 自动扩缩容

系统使用 KEDA 根据 Temporal 队列深度自动扩缩容认知 Worker：

```yaml
# k8s/keda/cognitive-worker-scaledobject.yaml
minReplicaCount: 2
maxReplicaCount: 10
targetValue: "5"  # 每个 worker 5 个任务时扩容
```

### 手动扩缩容

```bash
# 扩容 API 服务
kubectl scale deployment api-service -n grading-system --replicas=5

# 扩容认知 Worker
kubectl scale deployment cognitive-worker -n grading-system --replicas=8
```

## 监控

### 健康检查

```bash
# API 健康检查
curl http://your-domain/health

# Kubernetes 健康检查
kubectl get pods -n grading-system
```

### Prometheus 监控

```bash
# 应用 ServiceMonitor
kubectl apply -f k8s/services/service-monitor.yaml

# 查看指标
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

### 关键指标

- `http_requests_total` - HTTP 请求总数
- `http_request_duration_seconds` - 请求延迟
- `temporal_task_queue_depth` - Temporal 队列深度
- `cache_hit_rate` - 缓存命中率

## 故障排查

### Pod 无法启动

```bash
# 查看 Pod 详情
kubectl describe pod <pod-name> -n grading-system

# 查看日志
kubectl logs <pod-name> -n grading-system
```

### 数据库连接失败

```bash
# 测试数据库连接
kubectl run -it --rm debug --image=postgres:16 --restart=Never -n grading-system -- \
  psql $DATABASE_URL
```

### Temporal 连接问题

```bash
# 检查 Temporal 服务
kubectl get svc -n temporal

# 测试连接
kubectl run -it --rm debug --image=temporalio/admin-tools --restart=Never -- \
  tctl --address temporal-frontend.temporal:7233 cluster health
```

## 备份和恢复

### 数据库备份

```bash
# 备份 PostgreSQL
kubectl exec -n grading-system postgres-0 -- \
  pg_dump -U grading_user grading_system > backup.sql

# 恢复
kubectl exec -i -n grading-system postgres-0 -- \
  psql -U grading_user grading_system < backup.sql
```

### 对象存储备份

```bash
# 使用 MinIO Client (mc)
mc mirror minio/grading-submissions /backup/submissions
```

## 安全最佳实践

1. **密钥管理**
   - 使用 External Secrets Operator
   - 不要在 Git 中存储明文密钥

2. **网络安全**
   - 启用 NetworkPolicy
   - 配置 TLS/SSL
   - 使用 IP 白名单

3. **访问控制**
   - 使用 RBAC
   - 最小权限原则
   - 定期轮换密钥

4. **监控和审计**
   - 启用审计日志
   - 配置告警规则
   - 定期安全扫描

## 性能优化

### API 服务

- 根据负载调整副本数（建议 3-20）
- 配置合适的资源限制
- 启用 HTTP/2

### Worker 服务

- 认知 Worker：根据 Gemini API 配额调整
- 编排 Worker：通常 2-3 个副本足够
- 配置合适的并发数

### 数据库

- 使用连接池
- 配置合适的索引
- 定期 VACUUM

### 缓存

- 调整 Redis 内存限制
- 配置合适的 TTL
- 监控缓存命中率

## 成本优化

1. **使用 KEDA 自动扩缩容**
   - 根据实际负载动态调整
   - 避免过度配置

2. **缓存优化**
   - 提高缓存命中率
   - 减少 Gemini API 调用

3. **资源限制**
   - 设置合理的 CPU/内存限制
   - 使用 Spot/Preemptible 实例

4. **对象存储**
   - 配置生命周期策略
   - 使用存储类分层

## 更新和回滚

### 滚动更新

```bash
# 更新镜像
kubectl set image deployment/api-service \
  api=your-registry/ai-grading-api:v1.1.0 \
  -n grading-system

# 查看更新状态
kubectl rollout status deployment/api-service -n grading-system
```

### 回滚

```bash
# 回滚到上一个版本
kubectl rollout undo deployment/api-service -n grading-system

# 回滚到特定版本
kubectl rollout undo deployment/api-service --to-revision=2 -n grading-system
```

## 支持

如有问题，请：

1. 查看日志：`kubectl logs -n grading-system -l app=api-service`
2. 检查事件：`kubectl get events -n grading-system`
3. 查看文档：[k8s/README.md](k8s/README.md)
4. 提交 Issue

## 相关文档

- [README.md](README.md) - 项目概述
- [k8s/README.md](k8s/README.md) - Kubernetes 详细指南
- [.kiro/specs/ai-grading-agent/](./kiro/specs/ai-grading-agent/) - 设计文档
