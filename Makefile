.DEFAULT_GOAL := help
SHELL := /bin/bash

# Load .env if it exists — set -a exports all sourced vars to subprocesses
ifneq (,$(wildcard .env))
  ENV_PREFIX := set -a && source .env && set +a &&
endif

# ── Auto-install sentinels ──────────────────────────────────────────

.installed-py: pyproject.toml uv.lock
	uv sync --dev
	@touch $@

frontend/node_modules/.installed: frontend/package.json
	cd frontend && npm install
	@touch $@

# ── Dev servers ─────────────────────────────────────────────────────

BACKEND_PORT ?= 8001

define check-port
	@if netstat -ano 2>/dev/null | grep -q ':$(BACKEND_PORT).*LISTEN'; then \
		echo ""; \
		echo "  ERROR: Port $(BACKEND_PORT) is already in use."; \
		echo "  Another process is listening on that port. Find it with:"; \
		echo "    netstat -ano | grep :$(BACKEND_PORT)"; \
		echo "  Or use a different port:"; \
		echo "    make $@ BACKEND_PORT=8002"; \
		echo ""; \
		exit 1; \
	fi
endef

.PHONY: backend frontend dev

backend: .installed-py ## Start FastAPI backend
	$(check-port)
	$(ENV_PREFIX) uv run uvicorn backend.main:app --reload --log-level warning --port $(BACKEND_PORT)

frontend: frontend/node_modules/.installed ## Start Next.js dev server
	cd frontend && npm run dev

dev: .installed-py frontend/node_modules/.installed ## Start backend + frontend together
	$(check-port)
	@trap 'kill 0' EXIT; \
	$(ENV_PREFIX) uv run uvicorn backend.main:app --reload --log-level warning --port $(BACKEND_PORT) & \
	cd frontend && npm run dev

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
