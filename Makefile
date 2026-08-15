UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.PHONY: setup test lint fmt order attack

setup:
	$(UV) sync

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

order:
	$(UV) run client --dry-run

attack:
	$(UV) run client --adversarial --dry-run
