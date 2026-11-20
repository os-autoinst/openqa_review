UV_AVAILABLE := $(shell uv --version >/dev/null 2>&1 && echo 1)
ifeq ($(UV_AVAILABLE),1)
PYTHON_RUN ?= uv run --locked
else
$(warning uv not found or not callable; falling back to distribution-installed packages, versions may differ from uv.lock)
PYTHON_RUN ?=
endif

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: check-ruff
check-ruff: ## Run ruff linting and formatting checks
	$(PYTHON_RUN) ruff check .
	$(PYTHON_RUN) ruff format --check .

.PHONY: check-ty
check-ty: ## Run ty type checks
	$(PYTHON_RUN) ty check

.PHONY: tidy
tidy: ## Format code and fix linting issues
	$(PYTHON_RUN) ruff format .
	$(PYTHON_RUN) ruff check --fix .

.PHONY: check-tool-versions
check-tool-versions: ## Warn if the ty on PATH differs from the locked version
	@locked=$$(uv export --locked --only-dev --no-hashes 2>/dev/null | sed -n 's/^ty==//p'); \
	local=$$(ty --version 2>/dev/null | awk '{print $$2}'); \
	if [ -n "$$locked" ] && [ "$$locked" != "$$local" ]; then \
		echo "Warning: ty $$local on PATH but uv.lock pins ty $$locked; results may differ from CI"; \
	fi
