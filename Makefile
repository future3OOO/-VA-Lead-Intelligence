.PHONY: install lint typecheck test test-unit test-integration test-security benchmark contracts config-validate migration-check infra-check security-test dod-report handover workbook clean help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*##' Makefile | sort | awk 'BEGIN {FS = ":.*##"}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: $(VENV)/bin/python ## Create venv and install dependencies

$(VENV)/bin/python:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]"

lint: install ## Run ruff lint and format check
	$(PYTHON) -m ruff check src tests scripts
	$(PYTHON) -m ruff format --check src tests scripts

format: install ## Auto-format source files
	$(PYTHON) -m ruff format src tests scripts

typecheck: install ## Run mypy type checking
	$(PYTHON) -m mypy src scripts

test: install ## Run all tests
	$(PYTHON) -m pytest tests -q --junitxml=reports/junit.xml

test-unit: install ## Run unit tests
	$(PYTHON) -m pytest tests/unit -q

test-integration: install ## Run integration tests
	$(PYTHON) -m pytest tests/integration -q

test-security: install ## Run security tests
	$(PYTHON) -m pytest tests/security -q

contracts: install ## Export OpenAPI and JSON Schemas
	$(PYTHON) scripts/export_openapi.py --output contracts/openapi/lead-intelligence-v1.openapi.json
	$(PYTHON) scripts/export_json_schemas.py --output-dir contracts/jsonschema/

config-validate: install ## Validate taxonomy, scorecard and policy YAML
	$(PYTHON) scripts/validate_configs.py

migration-check: install ## Test Alembic upgrade paths and render ERD
	$(PYTHON) -m alembic upgrade head
	$(PYTHON) scripts/render_erd.py --output docs/erd/lead-intelligence.svg --from-metadata

benchmark: install ## Run frozen benchmark and produce report
	$(PYTHON) scripts/build_benchmark.py

infra-check: ## Format, validate, lint and scan Terraform
	cd infra/terraform && terraform fmt -check -recursive
	cd infra/terraform && terraform init -backend=false
	cd infra/terraform && terraform validate

dod-report: install ## Build requirement-to-test traceability report
	$(PYTHON) scripts/build_dod_report.py \
	  --requirements quality/definition-of-done.yaml \
	  --junit reports/junit.xml \
	  --output quality/traceability/production-v1.md

security-test: test-security

handover: install ## Regenerate, validate and bundle all release artifacts
	$(PYTHON) scripts/build_handover_bundle.py

workbook: install ## Build the four-sheet workbook from local CSV exports
	$(PYTHON) scripts/build_leads_workbook.py

clean: ## Remove build artifacts and venv
	rm -rf $(VENV) .mypy_cache .ruff_cache __pycache__ .pytest_cache
