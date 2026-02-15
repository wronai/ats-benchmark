.PHONY: all build benchmark-all benchmark-code2logic benchmark-nfo benchmark-baseline results clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

all: build benchmark-all results ## Build, run all benchmarks, show results

build: ## Build all Docker images
	docker compose build

benchmark-all: benchmark-code2logic benchmark-nfo benchmark-baseline ## Run all benchmarks sequentially
	@echo ""
	@echo "All benchmarks completed."

benchmark-code2logic: ## Run code2logic benchmark
	@echo "=== Running code2logic benchmark ==="
	docker compose run --rm code2logic-bench

benchmark-nfo: ## Run nfo benchmark
	@echo "=== Running nfo benchmark ==="
	docker compose run --rm nfo-bench

benchmark-baseline: ## Run baseline (raw code) benchmark
	@echo "=== Running baseline benchmark ==="
	docker compose run --rm baseline-bench

results: ## Analyze and compare results
	@echo "=== Benchmark Results ==="
	python3 analyze_results.py

clean: ## Remove results and Docker images
	rm -f benchmarks/*/results.json
	rm -f benchmarks/*/runtime_logs.jsonl
	rm -f benchmark_summary.json
	docker compose down --rmi local --volumes 2>/dev/null || true

env-check: ## Verify .env is configured
	@test -f .env || (echo "ERROR: .env file not found. Copy .env.example to .env and set OPENROUTER_API_KEY" && exit 1)
	@grep -q "OPENROUTER_API_KEY=sk-or" .env || echo "WARNING: OPENROUTER_API_KEY may not be set in .env"
	@echo ".env OK"

local-code2logic: ## Run code2logic benchmark locally (no Docker)
	cd $(CURDIR) && python -m benchmarks.code2logic.benchmark

local-nfo: ## Run nfo benchmark locally (no Docker)
	cd $(CURDIR) && python -m benchmarks.nfo.benchmark

local-baseline: ## Run baseline benchmark locally (no Docker)
	cd $(CURDIR) && python -m benchmarks.baseline.benchmark

local-all: local-code2logic local-nfo local-baseline results ## Run all benchmarks locally
