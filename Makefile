.PHONY: help install test lint format clean check pre-commit

help: ## Zobrazit nápovědu
	@echo "TRV Regulator - Vývojové příkazy"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Nainstalovat dev závislosti
	pip install -r requirements-dev.txt
	pre-commit install

test: ## Spustit unit testy
	pytest tests/ -v

test-cov: ## Spustit testy s coverage
	pytest tests/ --cov=custom_components/trv_regulator --cov-report=html --cov-report=term

lint: ## Spustit linting (ruff)
	ruff check custom_components/

lint-fix: ## Opravit linting problémy automaticky
	ruff check custom_components/ --fix

format: ## Formátovat kód (black)
	black custom_components/ tests/

format-check: ## Kontrola formátování
	black --check custom_components/ tests/

type-check: ## Type checking (mypy)
	mypy custom_components/trv_regulator/

check: lint format-check type-check test ## Spustit všechny checks (jako CI)

pre-commit: ## Spustit pre-commit hooks na všech souborech
	pre-commit run --all-files

clean: ## Vyčistit build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type f -name '*.pyo' -delete 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

dev-setup: install ## Kompletní setup pro development
	@echo "✅ Development environment ready!"
	@echo "Další kroky:"
	@echo "  - Spusťte 'make test' pro testy"
	@echo "  - Spusťte 'make check' pro kontrolu kódu"
	@echo "  - Přečtěte si docs/DEVELOPMENT.md"
