# Makefile for sqlalchemy-rds-iam

.PHONY: help install install-dev install-test test test-unit test-integration test-all lint format type-check coverage clean build publish-test publish

# Python interpreter to use
PYTHON := python3
PIP := $(PYTHON) -m pip

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install the package in production mode
	$(PIP) install .

install-dev:  ## Install with all development dependencies
	$(PIP) install -e ".[dev,docs]"
	pre-commit install

install-test:  ## Install only test dependencies
	$(PIP) install -e ".[dev]"

install-docs:  ## Install only documentation dependencies
	$(PIP) install -e ".[docs]"

install-editable:  ## Install package in editable mode (no extras)
	$(PIP) install -e .

upgrade-pip:  ## Upgrade pip, setuptools, and wheel
	$(PIP) install --upgrade pip setuptools wheel

deps-update:  ## Update all dependencies to latest versions
	$(PIP) install --upgrade -e ".[dev,docs]"

deps-list:  ## List all installed dependencies
	$(PIP) list

deps-tree:  ## Show dependency tree (requires pipdeptree)
	@command -v pipdeptree >/dev/null 2>&1 || (echo "Installing pipdeptree..." && $(PIP) install pipdeptree)
	pipdeptree

deps-outdated:  ## Show outdated dependencies
	$(PIP) list --outdated

test:  ## Run unit tests
	pytest tests/ -v -m "not integration"

test-unit:  ## Run only unit tests
	pytest tests/ -v -m "unit or not integration"

test-integration:  ## Run integration tests
	pytest tests/ -v -m "integration"

test-all:  ## Run all tests
	pytest tests/ -v

test-watch:  ## Run tests in watch mode (requires pytest-watch)
	@command -v ptw >/dev/null 2>&1 || (echo "Installing pytest-watch..." && $(PIP) install pytest-watch)
	ptw tests/ -- -v

test-failed:  ## Re-run only failed tests
	pytest tests/ -v --lf

test-specific:  ## Run specific test file (use TEST=path/to/test.py)
	pytest $(TEST) -v

lint:  ## Run linting checks
	black --check src/ tests/
	flake8 src/ tests/
	isort --check-only src/ tests/

lint-fix:  ## Auto-fix linting issues
	black src/ tests/
	isort src/ tests/

format:  ## Format code (alias for lint-fix)
	$(MAKE) lint-fix

type-check:  ## Run type checking
	mypy src/

security-check:  ## Check for security vulnerabilities
	@command -v bandit >/dev/null 2>&1 || (echo "Installing bandit..." && $(PIP) install bandit)
	bandit -r src/

coverage:  ## Run tests with coverage report
	pytest tests/ --cov=sqlalchemy_rds_iam --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

coverage-open:  ## Open coverage report in browser
	@if [ -d "htmlcov" ]; then \
		python -m webbrowser htmlcov/index.html; \
	else \
		echo "No coverage report found. Run 'make coverage' first."; \
	fi

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf src/*.egg-info
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .tox/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

clean-all: clean  ## Clean everything including virtual environments
	rm -rf venv/
	rm -rf .venv/
	rm -rf env/

build: clean  ## Build distribution packages
	$(PIP) install --upgrade build
	$(PYTHON) -m build

build-check:  ## Check if package builds correctly
	$(PIP) install --upgrade build twine
	$(PYTHON) -m build
	twine check dist/*

publish-test: build-check  ## Publish to TestPyPI
	twine upload --repository testpypi dist/*

publish: build-check  ## Publish to PyPI
	@echo "WARNING: About to publish to PyPI. Press Ctrl+C to cancel, or Enter to continue."
	@read -r
	twine upload dist/*

docs:  ## Build documentation
	cd docs && make html
	@echo "Documentation built in docs/_build/html/"

docs-serve:  ## Serve documentation locally
	@command -v sphinx-autobuild >/dev/null 2>&1 || (echo "Installing sphinx-autobuild..." && $(PIP) install sphinx-autobuild)
	cd docs && make livehtml

docs-clean:  ## Clean documentation build
	cd docs && make clean

tox:  ## Run tests across multiple Python versions
	@command -v tox >/dev/null 2>&1 || (echo "Installing tox..." && $(PIP) install tox)
	tox

tox-parallel:  ## Run tox in parallel
	@command -v tox >/dev/null 2>&1 || (echo "Installing tox..." && $(PIP) install tox)
	tox -p

pre-commit:  ## Run pre-commit hooks
	pre-commit run --all-files

pre-commit-update:  ## Update pre-commit hooks
	pre-commit autoupdate

setup-dev: upgrade-pip install-dev  ## Complete development environment setup
	@echo "Development environment setup complete!"

setup-ci:  ## Setup CI environment
	$(PIP) install tox tox-gh-actions

venv:  ## Create a virtual environment
	$(PYTHON) -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  # On Unix/macOS"
	@echo "  venv\\Scripts\\activate   # On Windows"

venv-clean:  ## Remove virtual environment
	rm -rf venv/

# Development workflow commands
check: lint type-check security-check  ## Run all checks

dev-test: format check test  ## Run full development test suite

release-check: clean build-check  ## Check release readiness
	@echo "Release check passed! Ready to publish."

# Installation helpers for different environments
install-mysql:  ## Install with MySQL driver
	$(PIP) install -e ".[mysql]"

install-postgres:  ## Install with PostgreSQL driver
	$(PIP) install -e ".[postgres]"

install-all-drivers:  ## Install with all database drivers
	$(PIP) install -e ".[mysql,postgres]"

# Debug helpers
debug-imports:  ## Check if package imports correctly
	$(PYTHON) -c "from sqlalchemy_rds_iam import RDSIAMAuthPlugin, create_rds_iam_engine; print('✓ Imports working correctly')"

debug-version:  ## Show package version
	$(PYTHON) -c "from sqlalchemy_rds_iam import __version__; print(f'Version: {__version__}')"

debug-entry-points:  ## Show installed entry points
	$(PYTHON) -c "from importlib.metadata import entry_points; print([ep for ep in entry_points() if 'sqlalchemy' in ep.group])"

# Help for common issues
doctor:  ## Diagnose common issues
	@echo "=== Python Version ==="
	$(PYTHON) --version
	@echo "\n=== Pip Version ==="
	$(PIP) --version
	@echo "\n=== Package Installation ==="
	@$(PIP) show sqlalchemy-rds-iam || echo "Package not installed"
	@echo "\n=== Key Dependencies ==="
	@$(PIP) show sqlalchemy boto3 || echo "Missing dependencies"
	@echo "\n=== Entry Points ==="
	@$(MAKE) debug-entry-points 2>/dev/null || echo "Could not check entry points"
