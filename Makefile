# ats-benchmark Makefile
# Usage:
#   make setup TARGET=./test-broken-code
#   make setup TARGET=./test-broken-code PROBLEM="parser logów nie grupuje po trace_id"
#   make benchmark-all
#   make repair
#   make results

.PHONY: all setup build benchmark-all benchmark-code2logic benchmark-nfo benchmark-baseline \
        benchmark-callgraph benchmark-treesitter benchmark-astgrep benchmark-radon benchmark-bandit \
        repair repair-code2logic repair-nfo repair-baseline results clean help \
        local-all local-code2logic local-nfo local-baseline local-repair \
        local-callgraph local-treesitter local-astgrep local-radon local-bandit \
        check-llm

# Read TARGET_PROJECT from .env if not passed via CLI
-include .env
export

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup: ## Configure target project: make setup TARGET=/path/to/project [PROBLEM="description"]
	@if [ -z "$(TARGET)" ]; then \
		echo "ERROR: TARGET is required. Usage: make setup TARGET=/path/to/project"; \
		exit 1; \
	fi
	@if [ ! -d "$(TARGET)" ]; then \
		echo "ERROR: Directory not found: $(TARGET)"; \
		exit 1; \
	fi
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	@sed -i 's|^TARGET_PROJECT=.*|TARGET_PROJECT=$(TARGET)|' .env
	@if [ -n "$(PROBLEM)" ]; then \
		sed -i 's|^PROBLEM_DESCRIPTION=.*|PROBLEM_DESCRIPTION=$(PROBLEM)|' .env; \
	fi
	@echo ""
	@echo "=== Configuration saved to .env ==="
	@echo "  TARGET_PROJECT=$(TARGET)"
	@test -n "$(PROBLEM)" && echo "  PROBLEM_DESCRIPTION=$(PROBLEM)" || true
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env — set OPENROUTER_API_KEY=sk-or-v1-..."
	@echo "  2. make benchmark-all   # Compare compression tools"
	@echo "  3. make repair          # LLM fixes real problems"
	@echo "  4. make results         # Show comparison"

env-check: ## Verify .env is configured
	@test -f .env || (echo "ERROR: .env not found. Run: make setup TARGET=/path/to/project" && exit 1)
	@grep -q "OPENROUTER_API_KEY=sk-or-v" .env || echo "WARNING: OPENROUTER_API_KEY may not be set"
	@grep -Eq "^TARGET_PROJECT=.+" .env || echo "WARNING: TARGET_PROJECT not set. Run: make setup TARGET=./test-broken-code"
	@echo ".env OK"

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

all: benchmark-all results ## Build + benchmark + results

build: ## Build all Docker images
	docker compose build

# ---------------------------------------------------------------------------
# Benchmarks (analysis only — compare compression tools)
# ---------------------------------------------------------------------------

check-llm: ## Check LLM connection before benchmarks
	@echo "=== LLM connection check (docker) ==="
	docker compose run --rm baseline-bench python -c 'import sys; from benchmarks.common import check_llm_connection; result = check_llm_connection(); sys.exit(0 if result.get("success") else 1)'

benchmark-all: build check-llm benchmark-code2logic benchmark-nfo benchmark-baseline benchmark-callgraph benchmark-treesitter benchmark-astgrep benchmark-radon benchmark-bandit ## Build and run all benchmarks
	@echo ""
	@echo "All benchmarks completed. Run: make results"

benchmark-code2logic: ## Benchmark: code2logic compression
	@echo "=== code2logic benchmark ==="
	docker compose run --rm code2logic-bench

benchmark-nfo: ## Benchmark: nfo data-flow compression
	@echo "=== nfo benchmark ==="
	docker compose run --rm nfo-bench

benchmark-baseline: ## Benchmark: raw code (no compression)
	@echo "=== baseline benchmark ==="
	docker compose run --rm baseline-bench

benchmark-callgraph: ## Benchmark: callgraph compression
	@echo "=== callgraph benchmark ==="
	docker compose run --rm callgraph-bench

benchmark-treesitter: ## Benchmark: treesitter AST compression
	@echo "=== treesitter benchmark ==="
	docker compose run --rm treesitter-bench

benchmark-astgrep: ## Benchmark: astgrep structural compression
	@echo "=== astgrep benchmark ==="
	docker compose run --rm astgrep-bench

benchmark-radon: ## Benchmark: radon complexity compression
	@echo "=== radon benchmark ==="
	docker compose run --rm radon-bench

benchmark-bandit: ## Benchmark: bandit security compression
	@echo "=== bandit benchmark ==="
	docker compose run --rm bandit-bench

# ---------------------------------------------------------------------------
# Repair (LLM fixes real problems using each compression tool)
# ---------------------------------------------------------------------------

repair: ## Run LLM repair with all tools (code2logic, nfo, baseline)
	@echo "=== LLM Repair Pipeline ==="
	docker compose run --rm repair-bench --tool all

repair-code2logic: ## Repair using code2logic context
	docker compose run --rm repair-bench --tool code2logic

repair-nfo: ## Repair using nfo context
	docker compose run --rm repair-bench --tool nfo

repair-baseline: ## Repair using raw code context
	docker compose run --rm repair-bench --tool baseline

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

results: ## Show benchmark + repair comparison
	@echo "=== Results ==="
	python3 analyze_results.py

# ---------------------------------------------------------------------------
# Local (no Docker)
# ---------------------------------------------------------------------------

local-code2logic: ## Run code2logic benchmark locally
	python3 -m benchmarks.code2logic.benchmark

local-nfo: ## Run nfo benchmark locally
	python3 -m benchmarks.nfo.benchmark

local-baseline: ## Run baseline benchmark locally
	python3 -m benchmarks.baseline.benchmark

local-callgraph: ## Run callgraph benchmark locally
	python3 -m benchmarks.callgraph.benchmark

local-treesitter: ## Run treesitter benchmark locally
	python3 -m benchmarks.treesitter.benchmark

local-astgrep: ## Run astgrep benchmark locally
	python3 -m benchmarks.astgrep.benchmark

local-radon: ## Run radon benchmark locally
	python3 -m benchmarks.radon.benchmark

local-bandit: ## Run bandit benchmark locally
	python3 -m benchmarks.bandit.benchmark

local-repair: ## Run repair pipeline locally (all tools)
	python3 -m benchmarks.repair.repair_pipeline --tool all

local-repair-code2logic: ## Run repair locally with code2logic
	python3 -m benchmarks.repair.repair_pipeline --tool code2logic

local-all: local-code2logic local-nfo local-baseline local-callgraph local-treesitter local-astgrep local-radon local-bandit results ## Run all benchmarks locally

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove results and Docker images
	rm -f benchmarks/*/results.json
	rm -f benchmarks/*/repair_result.json
	rm -rf benchmarks/repair/*/fixes/
	rm -f benchmarks/*/runtime_logs.jsonl
	rm -f benchmark_summary.json
	docker compose down --rmi local --volumes 2>/dev/null || true
