.DEFAULT_GOAL := help

PYTHON     := python3
APP_MODULE := app.main:app
PORT       := 8001

GREEN  := \033[0;32m
YELLOW := \033[0;33m
RESET  := \033[0m

.PHONY: help
help:
	@echo ""
	@echo "  RAG Service v2"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""

.PHONY: install
install:  ## Install all dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	@echo "$(GREEN)✓ Done$(RESET)"

.PHONY: dev
dev:  ## Run with hot reload
	uvicorn $(APP_MODULE) --host 0.0.0.0 --port $(PORT) --reload

.PHONY: test
test:  ## Run tests with coverage
	pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=75 -v

.PHONY: test-unit
test-unit:  ## Run unit tests only
	pytest tests/ -v -m unit

.PHONY: lint
lint:  ## Run ruff linter
	ruff check app/ tests/
	@echo "$(GREEN)✓ Lint passed$(RESET)"

.PHONY: format
format:  ## Auto-format with black + isort
	black app/ tests/
	isort app/ tests/

.PHONY: format-check
format-check:  ## Check formatting (CI)
	black app/ tests/ --check --diff
	isort app/ tests/ --check-only --diff

.PHONY: check
check: format-check lint test  ## Run all checks before committing

.PHONY: migrate
migrate:  ## Run DB migrations
	alembic upgrade head
	@echo "$(GREEN)✓ Migrations applied$(RESET)"

.PHONY: migrate-create
migrate-create:  ## Create a migration: make migrate-create MSG="description"
	@[ "$(MSG)" ] || (echo "Usage: make migrate-create MSG='description'"; exit 1)
	alembic revision --autogenerate -m "$(MSG)"

.PHONY: docker-up
docker-up:  ## Start Docker stack
	docker compose up -d

.PHONY: docker-down
docker-down:  ## Stop Docker stack
	docker compose down

.PHONY: docker-logs
docker-logs:  ## Tail logs
	docker compose logs -f rag-service

.PHONY: clean
clean:  ## Remove generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true

.PHONY: health
health:  ## Check service health
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

.PHONY: env
env:  ## Create .env from .env.example
	@[ -f .env ] && echo ".env exists" || (cp .env.example .env && echo "$(GREEN)✓ .env created$(RESET)")
