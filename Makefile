# Python implementation of blhost used to communicate with the NXP MCUBOOT/KBOOT bootloader.
# Copyright (C) 2020-2025  Kristian Sloth Lauszus.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Contact information
# -------------------
# Kristian Sloth Lauszus
# Web      :  https://www.lauszus.com
# e-mail   :  lauszus@gmail.com

# Run with "make -k static-checks" to run all static checks even if there are errors.
# This is the first target, so it is run if "make" is called without arguments.
static-checks: ruff-check mypy

# Determine the Python version from the ".python-version" file.
PYTHON_VERSION ?= $(shell cat .python-version)

# Path to the virtual environment directory.
# This name can not be changed, as uv expect it at this location
VENV := .venv

# Path to uv.
UV ?= $(shell which uv 2>/dev/null || echo "$(HOME)/.local/bin/uv")

# Target for installing uv.
$(UV):
	curl -LsSf https://astral.sh/uv/install.sh | sh
	if [ -f $(HOME)/.local/bin/env ]; then . $(HOME)/.local/bin/env; fi

# Install uv.
uv: $(UV)

# Target for building a virtual environment.
$(VENV)/.venv_done_$(PYTHON_VERSION): $(UV)
	uv sync --frozen --python $(PYTHON_VERSION) --python-preference only-managed
	@touch $(@)

# Make sure the venv is rebuild when we modify uv.lock.
$(VENV)/.venv_done_$(PYTHON_VERSION): uv.lock

# Create the virtual environment.
venv: $(VENV)/.venv_done_$(PYTHON_VERSION)

# Create a uv lock file.
# Note that we use the "--refresh" flag, as the package sources might change.
# Without this uv would just use the cached packages.
uv.lock: pyproject.toml
	uv lock --refresh --python $(PYTHON_VERSION) --python-preference only-managed
	@# uv does not touch the file if it is the same, so do it manually
	@touch $(@)
lock: uv.lock

# Upgrade all dependencies in the lock file.
lock-upgrade:
	uv lock --upgrade --refresh --python $(PYTHON_VERSION) --python-preference only-managed

# Cleanup the virtual environment.
clean:
	rm -rf $(VENV)
	rm -rf dist
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf .pytest_cache/
	@# Remove all __pycache__ directories and .pyc files.
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Done cleaning"

# Recursive wildcard.
rwildcard=$(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2) $(filter $(subst *,%,$2),$d))

# Build distribution.
dist/.build_done: $(UV) uv.lock $(call rwildcard,src/,*.py)
	uv build --python $(PYTHON_VERSION) --python-preference only-managed --no-sources
	@touch $(@)
build: dist/.build_done

mypy: venv
	@# mypy uses pip to install the types.
	uv pip install pip
	uv run mypy --install-types --non-interactive --exclude-gitignore .

ruff-format-check: $(UV)
	uvx --from 'ruff>=0.13.0' ruff format --check

ruff-format-fix: $(UV)
	uvx --from 'ruff>=0.13.0' ruff format

ruff-lint-check: $(UV)
	uvx --from 'ruff>=0.13.0' ruff check

ruff-lint-fix: $(UV)
	uvx --from 'ruff>=0.13.0' ruff check --fix

ruff-lint-fix-unsafe: $(UV)
	uvx --from 'ruff>=0.13.0' ruff check --fix --unsafe-fixes

# Combined rules for both formatting and linting.
ruff-check: ruff-format-check ruff-lint-check
ruff-fix: ruff-format-fix ruff-lint-fix
ruff-fix-unsafe: ruff-format-fix ruff-lint-fix-unsafe

# Use xdist to run the tests in parallel.
XDIST_ARGS ?= --numprocesses logical

# Use coverage.
COV_ARGS ?= --cov=src/pyblhost --cov-report=term-missing --cov-report=html:htmlcov

# Can be used to only run a specific test i.e. "-k test_name".
PYTEST_ARGS ?=

test: venv
	uv run --isolated pytest $(XDIST_ARGS) $(COV_ARGS) -vv tests/ $(PYTEST_ARGS)

# Targets for pyblhost
.PHONY: uv venv lock lock-upgrade clean build mypy ruff-format-check ruff-format-fix ruff-lint-check ruff-lint-fix ruff-lint-fix-unsafe ruff-check ruff-fix ruff-fix-unsafe test help

# Create a help message.
help:
	@echo "Available targets:"
	@echo "  venv            - Create virtual environment"
	@echo "  lock            - Update uv lock file"
	@echo "  lock-upgrade    - Upgrade all dependencies in the lock file"
	@echo "  static-checks   - Run ruff and mypy checks"
	@echo "  mypy            - Run mypy type checks"
	@echo "  ruff-check      - Run ruff formatting and linting checks"
	@echo "  ruff-fix        - Fix ruff formatting and linting issues"
	@echo "  ruff-fix-unsafe - Fix ruff formatting and linting issues including unsafe fixes"
	@echo "  test            - Run all tests"
	@echo "  clean           - Clean build artifacts"
	@echo "  build           - Build distribution"

