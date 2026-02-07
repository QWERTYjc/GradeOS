.PHONY: help build push build-push dev dev-logs dev-stop dev-clean db-migrate db-rollback db-revision test test-unit test-property test-integration test-coverage lint format type-check quality install install-dev update clean docs monitor

REGISTRY ?= your-registry
VERSION ?= latest

help: ## Show available commands
	@echo "GradeOS Backend commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build Docker images
	docker build -f Dockerfile.api -t $(REGISTRY)/ai-grading-api:$(VERSION) .
	docker build -f Dockerfile.worker -t $(REGISTRY)/ai-grading-worker:$(VERSION) .

push: ## Push Docker images
	docker push $(REGISTRY)/ai-grading-api:$(VERSION)
	docker push $(REGISTRY)/ai-grading-worker:$(VERSION)

build-push: build push ## Build and push Docker images

dev: ## Start local development environment
	docker-compose up -d

dev-logs: ## Tail local development logs
	docker-compose logs -f

dev-stop: ## Stop local development environment
	docker-compose down

dev-clean: ## Stop local environment and remove volumes
	docker-compose down -v

db-migrate: ## Run database migrations
	uv run alembic upgrade head

db-rollback: ## Rollback one migration
	uv run alembic downgrade -1

db-revision: ## Create a new migration (set DESC=<message>)
	uv run alembic revision --autogenerate -m "$(DESC)"

test: ## Run all tests
	uv run pytest tests/ -v

test-unit: ## Run unit tests
	uv run pytest tests/unit/ -v

test-property: ## Run property tests
	uv run pytest tests/property/ -v --hypothesis-show-statistics

test-integration: ## Run integration tests
	uv run pytest tests/integration/ -v

test-coverage: ## Run tests with coverage
	uv run pytest tests/ --cov=src --cov-report=html --cov-report=term

lint: ## Run lint checks
	uv run ruff check src/ tests/

format: ## Format code
	uv run black src/ tests/

type-check: ## Run type checks
	uv run mypy src/

quality: lint format type-check ## Run all code quality checks

install: ## Install dependencies
	uv sync

install-dev: ## Install dependencies with extras
	uv sync --all-extras

update: ## Update lockfile dependencies
	uv lock --upgrade

clean: ## Clean temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/

docs: ## Placeholder docs target
	@echo "Docs generation is not configured."

monitor: ## Print useful local URLs
	@echo "MinIO Console: http://localhost:9001"
	@echo "API Docs: http://localhost:8000/docs"
