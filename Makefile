UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

# .env.example says "copy to .env", and nothing read the result: no dotenv
# dependency, no --env-file, no target that sourced it. The counterparty repo
# hit the identical bug and fixed it; this is the port. Load it when it exists,
# stay out of the way when it does not -- CI passes real environment variables
# and has no .env to find.
ENV_FILE := $(wildcard .env)
UVRUN = $(UV) run $(if $(ENV_FILE),--env-file .env,)

.PHONY: setup test lint fmt order attack settle pay

setup:
	$(UV) sync

test:
	$(UVRUN) pytest

lint:
	$(UVRUN) ruff check .
	$(UVRUN) ruff format --check .

fmt:
	$(UVRUN) ruff format .
	$(UVRUN) ruff check --fix .

order:
	$(UVRUN) client --dry-run

attack:
	$(UVRUN) client --adversarial --dry-run

# The whole loop: read Broker's published deliverable, judge it, and pay only if
# it passes. --dry-run reaches the network to read and judge, but settles nothing.
settle:
	$(UVRUN) client --settle --dry-run

# Settle a fixed amount without judging first. The manual lane.
pay:
	$(UVRUN) client --pay 1.00 --order-id wo-1
