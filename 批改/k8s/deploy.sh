#!/bin/bash

# AI 批改系统 Kubernetes 部署脚本
set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
NAMESPACE="grading-system"
REGISTRY="${DOCKER_REGISTRY:-your-registry}"
VERSION="${VERSION:-latest}"

echo -e "${GREEN}=== AI 批改系统 Kubernetes 部署 ===${NC}"

# 检查前置条件
echo -e "\n${YELLOW}检查前置条件...${NC}"

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}错误: kubectl 未安装${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: docker 未安装${NC}"
    exit 1
fi

# 检查 kubectl 连接
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}错误: 无法连接到 Kubernetes 集群${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 前置条件检查通过${NC}"

# 构建 Docker 镜像
echo -e "\n${YELLOW}构建 Docker 镜像...${NC}"

read -p "是否构建并推送 Docker 镜像? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 构建 API 镜像
    echo "构建 API 镜像..."
    docker build -f ../Dockerfile.api -t ${REGISTRY}/ai-grading-api:${VERSION} ..
    docker push ${REGISTRY}/ai-grading-api:${VERSION}
    
    # 构建 Worker 镜像
    echo "构建 Worker 镜像..."
    docker build -f ../Dockerfile.worker -t ${REGISTRY}/ai-grading-worker:${VERSION} ..
    docker push ${REGISTRY}/ai-grading-worker:${VERSION}
    
    echo -e "${GREEN}✓ 镜像构建完成${NC}"
fi

# 更新 Kustomization
echo -e "\n${YELLOW}更新镜像引用...${NC}"
cd "$(dirname "$0")"

# 使用 kustomize 更新镜像
if command -v kustomize &> /dev/null; then
    kustomize edit set image \
        your-registry/ai-grading-api=${REGISTRY}/ai-grading-api:${VERSION} \
        your-registry/ai-grading-worker=${REGISTRY}/ai-grading-worker:${VERSION}
    echo -e "${GREEN}✓ 镜像引用已更新${NC}"
else
    echo -e "${YELLOW}警告: kustomize 未安装，跳过镜像更新${NC}"
fi

# 检查密钥配置
echo -e "\n${YELLOW}检查配置...${NC}"
if grep -q "CHANGE_ME_IN_PRODUCTION" secrets.yaml; then
    echo -e "${RED}警告: secrets.yaml 包含占位符，请先配置实际密钥！${NC}"
    read -p "是否继续部署? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 创建命名空间
echo -e "\n${YELLOW}创建命名空间...${NC}"
kubectl apply -f namespace.yaml
echo -e "${GREEN}✓ 命名空间已创建${NC}"

# 部署配置
echo -e "\n${YELLOW}部署配置...${NC}"
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
echo -e "${GREEN}✓ 配置已部署${NC}"

# 部署应用
echo -e "\n${YELLOW}部署应用...${NC}"
kubectl apply -f deployments/
kubectl apply -f services/
echo -e "${GREEN}✓ 应用已部署${NC}"

# 部署 KEDA（可选）
read -p "是否部署 KEDA 自动扩缩容? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if kubectl get namespace keda &> /dev/null; then
        kubectl apply -f keda/cognitive-worker-scaledobject.yaml
        echo -e "${GREEN}✓ KEDA ScaledObject 已部署${NC}"
    else
        echo -e "${YELLOW}警告: KEDA 未安装，跳过 ScaledObject 部署${NC}"
        echo "请先安装 KEDA: helm install keda kedacore/keda --namespace keda --create-namespace"
    fi
else
    echo "使用 HPA 备用方案..."
    kubectl apply -f keda/hpa-fallback.yaml
    echo -e "${GREEN}✓ HPA 已部署${NC}"
fi

# 等待 Pod 就绪
echo -e "\n${YELLOW}等待 Pod 就绪...${NC}"
kubectl wait --for=condition=ready pod -l app=api-service -n ${NAMESPACE} --timeout=300s || true
kubectl wait --for=condition=ready pod -l app=orchestration-worker -n ${NAMESPACE} --timeout=300s || true
kubectl wait --for=condition=ready pod -l app=cognitive-worker -n ${NAMESPACE} --timeout=300s || true

# 显示部署状态
echo -e "\n${GREEN}=== 部署状态 ===${NC}"
kubectl get pods -n ${NAMESPACE}
echo ""
kubectl get svc -n ${NAMESPACE}
echo ""
kubectl get ingress -n ${NAMESPACE}

# 显示访问信息
echo -e "\n${GREEN}=== 访问信息 ===${NC}"
INGRESS_IP=$(kubectl get ingress -n ${NAMESPACE} -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
echo "Ingress IP: ${INGRESS_IP}"
echo ""
echo "API 端点: http://${INGRESS_IP}/api/v1"
echo "健康检查: http://${INGRESS_IP}/health"
echo ""
echo "或使用端口转发进行本地测试:"
echo "  kubectl port-forward -n ${NAMESPACE} svc/api-service 8000:80"

# 显示日志命令
echo -e "\n${GREEN}=== 有用的命令 ===${NC}"
echo "查看 API 日志:"
echo "  kubectl logs -n ${NAMESPACE} -l app=api-service --tail=100 -f"
echo ""
echo "查看 Worker 日志:"
echo "  kubectl logs -n ${NAMESPACE} -l app=cognitive-worker --tail=100 -f"
echo ""
echo "查看所有资源:"
echo "  kubectl get all -n ${NAMESPACE}"
echo ""
echo "删除部署:"
echo "  kubectl delete namespace ${NAMESPACE}"

echo -e "\n${GREEN}✓ 部署完成！${NC}"
