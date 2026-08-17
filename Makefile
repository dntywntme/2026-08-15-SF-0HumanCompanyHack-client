UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.PHONY: setup test lint fmt order attack settle pay

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

# The whole loop: read Broker's published deliverable, judge it, and pay only if
# it passes. --dry-run reaches the network to read and judge, but settles nothing.
settle:
	$(UV) run client --settle --dry-run

# Settle a fixed amount without judging first. The manual lane.
pay:
	$(UV) run client --pay 1.00 --order-id wo-1
