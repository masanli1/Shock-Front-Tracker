.PHONY: install test lint demo clean

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests

demo:
	python examples/synthetic_demo.py

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
