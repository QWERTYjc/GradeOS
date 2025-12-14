.PHONY: help build push deploy clean logs test

# 配置
REGISTRY ?= your-registry
VERSION ?= latest
NAMESPACE = grading-system

help: ## 显示帮助信息
	@echo "AI 批改系统 - 可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Docker 相关
build: ## 构建 Docker 镜像
	@echo "构建 API 镜像..."
	docker build -f Dockerfile.api -t $(REGISTRY)/ai-grading-api:$(VERSION) .
	@echo "构建 Worker 镜像..."
	docker build -f Dockerfile.worker -t $(REGISTRY)/ai-grading-worker:$(VERSION) .

push: ## 推送 Docker 镜像到仓库
	docker push $(REGISTRY)/ai-grading-api:$(VERSION)
	docker push $(REGISTRY)/ai-grading-worker:$(VERSION)

build-push: build push ## 构建并推送镜像

# 本地开发
dev: ## 启动本地开发环境（Docker Compose）
	docker-compose up -d

dev-logs: ## 查看本地开发环境日志
	docker-compose logs -f

dev-stop: ## 停止本地开发环境
	docker-compose down

dev-clean: ## 清理本地开发环境（包括数据卷）
	docker-compose down -v

# Kubernetes 部署
k8s-deploy: ## 部署到 Kubernetes
	cd k8s && bash deploy.sh

k8s-apply: ## 应用 Kubernetes 配置
	kubectl apply -k k8s/

k8s-delete: ## 删除 Kubernetes 部署
	kubectl delete namespace $(NAMESPACE)

k8s-status: ## 查看 Kubernetes 部署状态
	kubectl get all -n $(NAMESPACE)

k8s-logs-api: ## 查看 API 日志
	kubectl logs -n $(NAMESPACE) -l app=api-service --tail=100 -f

k8s-logs-worker: ## 查看 Worker 日志
	kubectl logs -n $(NAMESPACE) -l app=cognitive-worker --tail=100 -f

k8s-port-forward: ## 端口转发到本地
	kubectl port-forward -n $(NAMESPACE) svc/api-service 8000:80

# 数据库
db-migrate: ## 运行数据库迁移
	uv run alembic upgrade head

db-rollback: ## 回滚数据库迁移
	uv run alembic downgrade -1

db-revision: ## 创建新的数据库迁移
	@read -p "迁移描述: " desc; \
	uv run alembic revision --autogenerate -m "$$desc"

# 测试
test: ## 运行所有测试
	uv run pytest tests/ -v

test-unit: ## 运行单元测试
	uv run pytest tests/unit/ -v

test-property: ## 运行属性测试
	uv run pytest tests/property/ -v --hypothesis-show-statistics

test-integration: ## 运行集成测试
	uv run pytest tests/integration/ -v

test-coverage: ## 运行测试并生成覆盖率报告
	uv run pytest tests/ --cov=src --cov-report=html --cov-report=term

# 代码质量
lint: ## 运行代码检查
	uv run ruff check src/ tests/

format: ## 格式化代码
	uv run black src/ tests/

type-check: ## 运行类型检查
	uv run mypy src/

quality: lint format type-check ## 运行所有代码质量检查

# 依赖管理
install: ## 安装依赖
	uv sync

install-dev: ## 安装开发依赖
	uv sync --all-extras

update: ## 更新依赖
	uv lock --upgrade

# 清理
clean: ## 清理临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/

# 文档
docs: ## 生成文档
	@echo "文档生成功能待实现"

# 监控
monitor: ## 打开监控面板
	@echo "Temporal UI: http://localhost:8080"
	@echo "MinIO Console: http://localhost:9001"
	@echo "API Docs: http://localhost:8000/docs"
