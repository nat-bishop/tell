.DEFAULT_GOAL := help
SHELL := /bin/bash

# Load .env if it exists — set -a exports all sourced vars to subprocesses
ifneq (,$(wildcard .env))
  ENV_PREFIX := set -a && . ./.env && set +a &&
endif

# ── Auto-install sentinels ──────────────────────────────────────────

.installed-py: pyproject.toml uv.lock
	uv sync --dev
	@touch $@

frontend/node_modules/.installed: frontend/package.json
	cd frontend && npm install
	@touch $@

# ── Dev servers ─────────────────────────────────────────────────────

BACKEND_PORT ?= 8501
FRONTEND_PORT ?= 3500

# Kill anything on a given port.
# Uses taskkill /T to kill the entire process tree (prevents zombie children on Windows).
define kill-port
	@if [ -f .$(1).pid ]; then \
		taskkill //F //T //PID $$(cat .$(1).pid) 2>/dev/null; rm -f .$(1).pid; \
	fi; \
	if netstat -ano 2>/dev/null | grep -q ':$(2).*LISTEN'; then \
		powershell -Command "Get-NetTCPConnection -LocalPort $(2) -ErrorAction SilentlyContinue | ForEach-Object { taskkill /F /T /PID \$$_.OwningProcess 2>\$$null }" 2>/dev/null; \
		for i in 1 2 3 4 5; do \
			netstat -ano 2>/dev/null | grep -q ':$(2).*LISTEN' || break; \
			sleep 1; \
		done; \
	fi
endef

.PHONY: backend frontend dev

backend: .installed-py ## Start FastAPI backend
	$(call kill-port,backend,$(BACKEND_PORT))
	$(ENV_PREFIX) PYTHONUNBUFFERED=1 uv run uvicorn backend.main:app --reload --log-level $$(echo $${TELL_LOG_LEVEL:-INFO} | tr A-Z a-z) --port $(BACKEND_PORT)

frontend: frontend/node_modules/.installed ## Start Next.js dev server
	$(call kill-port,frontend,$(FRONTEND_PORT))
	$(ENV_PREFIX) cd frontend && PORT=$(FRONTEND_PORT) npm run dev

dev: .installed-py frontend/node_modules/.installed ## Start backend + frontend together
	$(call kill-port,backend,$(BACKEND_PORT))
	$(call kill-port,frontend,$(FRONTEND_PORT))
	@trap 'taskkill //F //T //PID $$(cat .backend.pid) 2>/dev/null; rm -f .backend.pid; kill 0 2>/dev/null' EXIT; \
	$(ENV_PREFIX) PYTHONUNBUFFERED=1 uv run uvicorn backend.main:app --reload --log-level $$(echo $${TELL_LOG_LEVEL:-INFO} | tr A-Z a-z) --port $(BACKEND_PORT) & \
	echo $$! > .backend.pid; \
	$(ENV_PREFIX) cd frontend && PORT=$(FRONTEND_PORT) npm run dev

# ── Test ────────────────────────────────────────────────────────────

.PHONY: test

test: .installed-py ## Run all tests
	uv run pytest tests/ -x -q

# ── Lint / Format ──────────────────────────────────────────────────

.PHONY: lint

lint: .installed-py ## Lint + format Python (ruff check --fix + ruff format)
	uv run ruff check --fix .
	uv run ruff format .

# ── Codegen ────────────────────────────────────────────────────

.PHONY: codegen

codegen: .installed-py frontend/node_modules/.installed ## Regenerate frontend types from backend OpenAPI spec
	uv run python scripts/export-openapi.py
	cd frontend && npm run codegen

# ── Stop ──────────────────────────────────────────────────────────

.PHONY: down

down: ## Kill dev servers
	$(call kill-port,backend,$(BACKEND_PORT))
	$(call kill-port,frontend,$(FRONTEND_PORT))
	@echo "Stopped"

# ── Clean ───────────────────────────────────────────────────────────

.PHONY: clean

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/.next frontend/node_modules/.cache
	rm -f .installed-py

# ── Help ────────────────────────────────────────────────────────────

.PHONY: help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
