# ─────────────────────────────────────────────────────────────────────────────
# Chat Service v2 — Makefile
#
# Usage:
#   make install       Install all dependencies
#   make dev           Run the service in dev mode
#   make test          Run tests with coverage
#   make lint          Run all linters
#   make format        Auto-format code
#   make check         lint + test (run before every commit)
#   make clean         Remove generated files
#   make docker-up     Start Docker stack
#   make docker-down   Stop Docker stack
#   make migrate       Run DB migrations
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

# ── Variables ─────────────────────────────────────────────────────────────────
PYTHON       := python3
PIP          := pip3
APP_MODULE   := app.main:app
HOST         := 0.0.0.0
PORT         := 8000
COVERAGE_MIN := 80

# Colours for output
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
RESET  := \033[0m

# ── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:  ## Show this help
	@echo ""
	@echo "  Chat Service v2"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Dependencies ──────────────────────────────────────────────────────────────
.PHONY: install
install:  ## Install all dependencies (app + dev)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	@echo "$(GREEN)✓ Dependencies installed$(RESET)"

.PHONY: install-prod
install-prod:  ## Install production dependencies only
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# ── Development ───────────────────────────────────────────────────────────────
.PHONY: dev
dev:  ## Run with hot reload
	uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

.PHONY: run
run:  ## Run without hot reload (prod-like)
	uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --workers 2

# ── Testing ───────────────────────────────────────────────────────────────────
.PHONY: test
test:  ## Run all tests with coverage
	@echo "$(YELLOW)Running tests...$(RESET)"
	pytest tests/ \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=$(COVERAGE_MIN) \
		-v
	@echo "$(GREEN)✓ Tests passed (coverage ≥ $(COVERAGE_MIN)%)$(RESET)"

.PHONY: test-fast
test-fast:  ## Run tests without coverage (faster)
	pytest tests/ -v -x

.PHONY: test-unit
test-unit:  ## Run unit tests only
	pytest tests/ -v -m unit

.PHONY: test-integration
test-integration:  ## Run integration tests only
	pytest tests/ -v -m integration

.PHONY: test-watch
test-watch:  ## Run tests in watch mode (re-runs on file change)
	pytest-watch -- tests/ -v

.PHONY: coverage-report
coverage-report:  ## Open HTML coverage report in browser
	open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html

# ── Linting ───────────────────────────────────────────────────────────────────
.PHONY: lint
lint: lint-ruff lint-mypy  ## Run all linters

.PHONY: lint-ruff
lint-ruff:  ## Run ruff linter
	@echo "$(YELLOW)Running ruff...$(RESET)"
	ruff check app/ tests/
	@echo "$(GREEN)✓ ruff passed$(RESET)"

.PHONY: lint-mypy
lint-mypy:  ## Run mypy type checker
	@echo "$(YELLOW)Running mypy...$(RESET)"
	mypy app/ --ignore-missing-imports --no-error-summary
	@echo "$(GREEN)✓ mypy passed$(RESET)"

# ── Formatting ────────────────────────────────────────────────────────────────
.PHONY: format
format:  ## Auto-format code with black + isort
	@echo "$(YELLOW)Formatting with black...$(RESET)"
	black app/ tests/
	@echo "$(YELLOW)Sorting imports with isort...$(RESET)"
	isort app/ tests/
	@echo "$(GREEN)✓ Formatting done$(RESET)"

.PHONY: format-check
format-check:  ## Check formatting without changing files (for CI)
	black app/ tests/ --check --diff
	isort app/ tests/ --check-only --diff

# ── Combined checks ───────────────────────────────────────────────────────────
.PHONY: check
check: format-check lint test  ## Run all checks (use before committing)
	@echo ""
	@echo "$(GREEN)✓ All checks passed — ready to commit$(RESET)"

.PHONY: ci
ci: format-check lint test  ## Run CI pipeline checks
	@echo "$(GREEN)✓ CI passed$(RESET)"

# ── Database ──────────────────────────────────────────────────────────────────
.PHONY: migrate
migrate:  ## Run pending Alembic migrations
	alembic upgrade head
	@echo "$(GREEN)✓ Migrations applied$(RESET)"

.PHONY: migrate-create
migrate-create:  ## Create a new migration (MSG="description")
	@if [ -z "$(MSG)" ]; then echo "$(RED)Usage: make migrate-create MSG='your description'$(RESET)"; exit 1; fi
	alembic revision --autogenerate -m "$(MSG)"
	@echo "$(GREEN)✓ Migration created$(RESET)"

.PHONY: migrate-rollback
migrate-rollback:  ## Roll back one migration
	alembic downgrade -1
	@echo "$(YELLOW)⚠ Rolled back one migration$(RESET)"

.PHONY: migrate-history
migrate-history:  ## Show migration history
	alembic history --verbose

# ── Docker ────────────────────────────────────────────────────────────────────
.PHONY: docker-up
docker-up:  ## Start all services (DB + chat service)
	docker compose up -d
	@echo "$(GREEN)✓ Stack started — http://localhost:8000$(RESET)"

.PHONY: docker-down
docker-down:  ## Stop all services
	docker compose down
	@echo "$(YELLOW)Stack stopped$(RESET)"

.PHONY: docker-logs
docker-logs:  ## Tail service logs
	docker compose logs -f chat-service

.PHONY: docker-build
docker-build:  ## Rebuild Docker image
	docker compose build --no-cache chat-service

.PHONY: docker-restart
docker-restart: docker-down docker-up  ## Restart the stack

# ── Utilities ─────────────────────────────────────────────────────────────────
.PHONY: clean
clean:  ## Remove generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	find . -name "coverage.xml" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(RESET)"

.PHONY: env
env:  ## Create .env from .env.example
	@if [ -f .env ]; then \
		echo "$(YELLOW).env already exists — not overwriting$(RESET)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ .env created from .env.example — fill in your API keys$(RESET)"; \
	fi

.PHONY: health
health:  ## Check service health
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

.PHONY: docs
docs:  ## Open API docs in browser
	open http://localhost:$(PORT)/docs 2>/dev/null || xdg-open http://localhost:$(PORT)/docs
