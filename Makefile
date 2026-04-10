.PHONY: install test test-fast lint format typecheck demo clean all

install:
	pip install -e ".[dev]"

test:
	PYTHONPATH=src pytest tests/ -v

test-fast:
	PYTHONPATH=src pytest tests/ -q

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	PYTHONPATH=src mypy src/

demo:
	PYTHONPATH=src python -m flux.synthesis.demo

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov dist build
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

all: lint typecheck test
