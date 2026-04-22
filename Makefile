# direct-supply-meal — Makefile
# All targets assume you're in the repo root.

PYTHON ?= python3

.PHONY: install test lint run-dev seed-db seed-traces compile-wiki docker-up docker-down

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy app agents wiki

run-dev:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

seed-db:
	$(PYTHON) scripts/seed_db.py

seed-traces:
	$(PYTHON) scripts/seed_traces.py

compile-wiki:
	$(PYTHON) -m wiki.compiler

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

# Phase 2 Graduation:
#   - `compile-wiki` target retires when systemd timer takes over. Seam: add `wiki/compile_timer.py` unit.
