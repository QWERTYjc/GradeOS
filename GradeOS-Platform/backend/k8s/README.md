# Kubernetes 部署指南

本目录包含 AI 批改系统的 Kubernetes 部署清单。

## 目录结构

```
k8s/
├── namespace.yaml                    # 命名空间定义
├── configmap.yaml                    # 配置映射
├── secrets.yaml                      # 敏感信息（需修改）
├── kustomization.yaml                # Kustomize 配置
├── deployments/                      # 部署清单
│   ├── api-deployment.yaml           # API 服务
│   ├── orchestration-worker-deployment.yaml  # 编排 Worker
│   ├── cognitive-worker-deployment.yaml      # 认知 Worker
│   └── pod-disruption-budget.yaml    # Pod 中断预算
├── services/                         # 服务和网络
│   ├── ingress.yaml                  # Ingress 配置
│   ├── network-policy.yaml           # 网络策略
│   └── service-monitor.yaml          # Prometheus 监控
└── keda/                             # KEDA 自动扩缩容
    ├── cognitive-worker-scaledobject.yaml  # KEDA ScaledObject
    └── hpa-fallback.yaml             # HPA 备用方案
```

## 前置条件

1. **Kubernetes 集群**（版本 >= 1.24）
2. **kubectl** 已配置并连接到集群
3. **NGINX Ingress Controller**（或其他 Ingress 控制器）
4. **KEDA**（可选，用于基于队列深度的自动扩缩容）
5. **Prometheus Operator**（可选，用于监控）
6. **Temporal 集群**（需要单独部署）

## 快速开始

### 1. 修改配置

编辑 `secrets.yaml`，替换所有 `CHANGE_ME_IN_PRODUCTION` 占位符：

```bash
# 生产环境建议使用外部密钥管理系统
# 例如：AWS Secrets Manager, HashiCorp Vault, Sealed Secrets
```

编辑 `services/ingress.yaml`，替换域名：

```yaml
host: grading.example.com  # 替换为实际域名
```

### 2. 构建并推送 Docker 镜像

```bash
# 构建 API 镜像
docker build -f Dockerfile.api -t your-registry/ai-grading-api:latest .
docker push your-registry/ai-grading-api:latest

# 构建 Worker 镜像
docker build -f Dockerfile.worker -t your-registry/ai-grading-worker:latest .
docker push your-registry/ai-grading-worker:latest
```

### 3. 更新镜像引用

编辑 `kustomization.yaml`，更新镜像仓库地址：

```yaml
images:
  - name: your-registry/ai-grading-api
    newName: your-actual-registry/ai-grading-api
    newTag: v1.0.0
```

### 4. 部署到 Kubernetes

使用 kubectl 直接部署：

```bash
# 创建命名空间
kubectl apply -f namespace.yaml

# 部署所有资源
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f deployments/
kubectl apply -f services/
kubectl apply -f keda/
```

或使用 Kustomize：

```bash
# 预览生成的清单
kubectl kustomize k8s/

# 应用配置
kubectl apply -k k8s/
```

### 5. 验证部署

```bash
# 检查 Pod 状态
kubectl get pods -n grading-system

# 检查服务
kubectl get svc -n grading-system

# 检查 Ingress
kubectl get ingress -n grading-system

# 查看日志
kubectl logs -n grading-system -l app=api-service --tail=100 -f
kubectl logs -n grading-system -l app=cognitive-worker --tail=100 -f
```

### 6. 访问服务

```bash
# 获取 Ingress 地址
kubectl get ingress -n grading-system

# 或使用端口转发进行本地测试
kubectl port-forward -n grading-system svc/api-service 8000:80
```

## KEDA 自动扩缩容

### 安装 KEDA

```bash
# 使用 Helm 安装 KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
```

### 配置 Temporal Scaler

KEDA 需要 Temporal 的指标来进行扩缩容。确保：

1. Temporal 集群已部署并可访问
2. 配置了正确的 Temporal 地址和命名空间
3. 任务队列名称匹配（`vision-compute-queue`）

### 监控扩缩容

```bash
# 查看 ScaledObject 状态
kubectl get scaledobject -n grading-system

# 查看 HPA（由 KEDA 创建）
kubectl get hpa -n grading-system

# 查看扩缩容事件
kubectl describe scaledobject cognitive-worker-scaler -n grading-system
```

## 监控和日志

### Prometheus 监控

如果安装了 Prometheus Operator：

```bash
# 应用 ServiceMonitor
kubectl apply -f services/service-monitor.yaml

# 查看指标
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090
# 访问 http://localhost:9090
```

### 日志聚合

建议使用以下工具之一：

- **ELK Stack**（Elasticsearch, Logstash, Kibana）
- **Loki + Grafana**
- **CloudWatch Logs**（AWS）
- **Cloud Logging**（GCP）

## 生产环境最佳实践

### 1. 密钥管理

不要在 Git 中存储明文密钥。使用：

- **External Secrets Operator** + AWS Secrets Manager/Vault
- **Sealed Secrets**
- **SOPS**（Secrets OPerationS）

示例（External Secrets）：

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: grading-secrets
  namespace: grading-system
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: grading-secrets
  data:
  - secretKey: GEMINI_API_KEY
    remoteRef:
      key: prod/grading/gemini-api-key
```

### 2. 资源限制

根据实际负载调整资源请求和限制：

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "1000m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

### 3. 高可用性

- API 服务至少 3 个副本
- Worker 至少 2 个副本
- 配置 PodDisruptionBudget
- 使用多可用区部署

### 4. 网络安全

- 启用 NetworkPolicy
- 使用 TLS/SSL（配置 cert-manager）
- 限制 Ingress 访问（IP 白名单）

### 5. 备份和恢复

定期备份：

- PostgreSQL 数据库
- Redis 持久化数据
- S3/MinIO 对象存储

## 故障排查

### Pod 无法启动

```bash
# 查看 Pod 事件
kubectl describe pod <pod-name> -n grading-system

# 查看日志
kubectl logs <pod-name> -n grading-system

# 检查镜像拉取
kubectl get events -n grading-system --sort-by='.lastTimestamp'
```

### 数据库连接失败

```bash
# 测试数据库连接
kubectl run -it --rm debug --image=postgres:16 --restart=Never -n grading-system -- \
  psql postgresql://grading_user:password@postgres-service:5432/grading_system
```

### Temporal 连接问题

```bash
# 检查 Temporal 服务
kubectl get svc -n temporal

# 测试连接
kubectl run -it --rm debug --image=temporalio/admin-tools --restart=Never -n grading-system -- \
  tctl --address temporal-frontend.temporal:7233 cluster health
```

### KEDA 不扩容

```bash
# 检查 KEDA 日志
kubectl logs -n keda -l app=keda-operator

# 检查 ScaledObject
kubectl describe scaledobject cognitive-worker-scaler -n grading-system

# 检查指标
kubectl get --raw /apis/external.metrics.k8s.io/v1beta1
```

## 清理

```bash
# 删除所有资源
kubectl delete -k k8s/

# 或逐个删除
kubectl delete namespace grading-system
```

## 参考资料

- [Kubernetes 官方文档](https://kubernetes.io/docs/)
- [KEDA 文档](https://keda.sh/docs/)
- [Temporal Kubernetes 部署](https://docs.temporal.io/self-hosted-guide/kubernetes)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
