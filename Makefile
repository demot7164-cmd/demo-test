# Makefile for DOCX Translation Workflow

.PHONY: help install dev-install start-worker clean

# Environment
UV ?= uv

help: ## Show this help message
	@echo "DOCX Translation Workflow - Makefile Commands"
	@echo "==============================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

install: ## Install production dependencies
	$(UV) sync --frozen

dev-install: ## Install development dependencies
	$(UV) sync --all-extras --dev

start-worker: ## Start the workflow worker
	$(UV) run python src/worker.py

clean: ## Clean build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
