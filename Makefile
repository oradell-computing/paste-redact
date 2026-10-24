# Everything you need to check the tool. Run `make` for this list.

SHELL := bash
.DEFAULT_GOAL := help

PY := .venv/bin/python

# The Python the checks run on. CI runs the oldest and the newest supported versions.
PYTHON_VERSION ?= 3.14

# Pinned, run through uv without installing it, so CI and your machine agree.
# Override only to experiment, e.g. `make check RUFF=ruff`.
RUFF_VERSION := 0.16.10
RUFF := uvx ruff@$(RUFF_VERSION)

.PHONY: help install check

help: ## Show this list
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort

$(PY):
	uv venv --python $(PYTHON_VERSION) .venv

install: $(PY) ## Create the virtualenv (PYTHON_VERSION, default 3.14) and install the dev tools (pytest, mypy)
	uv pip install --python .venv -r requirements-dev.txt

check: ## Lint, format-check, type-check and test (offline)
	$(RUFF) check .
	$(RUFF) format --check .
	$(PY) -m mypy .
	$(PY) -m pytest -q
	@if git grep --untracked -nE '\b[0-9]{12}\b' -- . | grep -vE '111122223333|123456789012|444455556666'; then \
	  echo "Found what looks like an AWS account ID (above). Only AWS's documented examples are allowed."; exit 1; \
	else echo "No stray 12-digit account IDs found."; fi
