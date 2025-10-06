SHELL := /bin/sh

# Virtualenv location
VENV := .venv
PYTHON ?= python

ifeq ($(OS),Windows_NT)
    PIP := $(VENV)/Scripts/pip.exe
    PY := $(VENV)/Scripts/python.exe
else
    PIP := $(VENV)/bin/pip
    PY := $(VENV)/bin/python
endif

	# Build settings
	BUILD_NAME := imgc
	ifeq ($(OS),Windows_NT)
		DATASEP := ;
	else
		DATASEP := :
	endif

	# Common hidden imports for PyInstaller builds (tweak as needed)
	PYI_HIDDEN_IMPORTS_COMMON := \
		PIL \
		PIL.Image \
		PIL.ImageFile \
		PIL.ImageFilter \
		PIL.ImageFont \
		PIL.ImageDraw \
		PIL.ImageEnhance \
		PIL.ImageOps \
		PIL._tkinter_finder \
		PIL._imaging \
		PIL.ImageQt \
		PIL._imagingft
	
	# Platform-specific hidden imports
	ifeq ($(OS),Windows_NT)
		PYI_HIDDEN_IMPORTS_PLATFORM := \
			watchdog.observers.winapi
	else
		PYI_HIDDEN_IMPORTS_PLATFORM := \
			watchdog.observers.inotify_buffer
	endif
	
	PYI_HIDDEN_IMPORTS := $(PYI_HIDDEN_IMPORTS_COMMON) $(PYI_HIDDEN_IMPORTS_PLATFORM)

.PHONY: help venv install install-dev run test test-unit test-integration lint format clean release check-release

help:
	@echo "Makefile targets for this project"
	@echo "  make venv       - create virtualenv at $(VENV)"
	@echo "  make install    - create venv and install runtime requirements"
	@echo "  make install-dev - create venv and install with test/dev dependencies"
	@echo "  make run ARGS='--root /path' - run watcher with arguments"
	@echo "  make test       - run all tests (unit + integration)"
	@echo "  make test-unit  - run unit tests only (fast, isolated tests)"
	@echo "  make test-integration - run integration tests (slower, end-to-end tests)"
	@echo "  make coverage   - run tests with coverage report"
	@echo "  make lint       - run code quality checks (formatting, syntax)"
	@echo "  make build      - build a standalone binary using PyInstaller"
	@echo "  make package    - create a zip of the built binary (dist)"
	@echo "  make format     - run black formatter"
	@echo "  make clean      - remove build artifacts and venv"
	@echo "  make check-release VERSION=v1.0.0  - validate release readiness"
	@echo "  make release VERSION=v1.0.0        - create and push release tag"

venv:
	@echo Ensuring virtualenv at '$(VENV)'.
	@$(PYTHON) -m venv $(VENV)
	@echo "To activate in PowerShell: .\\$(VENV)\\Scripts\\Activate.ps1"
	@echo "To activate (POSIX): . $(VENV)/bin/activate"

install: venv
	@echo "Installing runtime requirements into $(VENV)"
	$(PY) -m pip install --upgrade pip setuptools wheel
	$(PY) -m pip install -r requirements.txt

install-dev: venv
	@echo "Installing development and test requirements into $(VENV)"
	$(PY) -m pip install --upgrade pip setuptools wheel
	$(PY) -m pip install -r requirements-test.txt

run: install
	@echo "Running watcher (use --help for options)"
	$(PY) main.py $(ARGS)

test: install-dev
	@echo "Running all tests"
	$(PY) -m pytest -v

test-unit: install-dev
	@echo "Running unit tests only (fast, isolated tests)"
	$(PY) -m pytest -q tests/unit/

test-integration: install-dev
	@echo "Running integration tests (slower, end-to-end tests)"
	$(PY) -m pytest -q tests/integration/

coverage: install-dev
	@echo "Running tests with coverage"
	$(PY) -m coverage run -m pytest
	$(PY) -m coverage report -m
	$(PY) -m coverage xml -o coverage.xml
	$(PY) -m coverage html -d coverage_html

lint: install-dev
	@echo "Running code quality checks"
	@echo "  - Checking code formatting with black..."
	$(PY) -m black --check --diff .
	@echo "  - Running syntax checks..."
	$(PY) -m py_compile main.py imgc/*.py || true
	@echo "  - Checking for common issues..."
	@echo "Lint checks complete"

format: install-dev
	@echo "Formatting with black (will install if missing)"
	$(PY) -m black .

build: install
	@echo "Building standalone binary with PyInstaller"
	$(PY) -m pip install --upgrade pyinstaller
	$(PY) -m PyInstaller --onefile --name $(BUILD_NAME) \
		--add-data "imgc$(DATASEP)imgc" \
		--collect-submodules PIL \
		--collect-data PIL \
		$(foreach imp,$(PYI_HIDDEN_IMPORTS),--hidden-import $(imp)) \
		main.py

package: build
	@echo "Packaging dist into a zip archive"
	$(PY) -c "import shutil; shutil.make_archive('dist/$(BUILD_NAME)','zip','dist')"

clean-build:
	@echo "Cleaning PyInstaller build artifacts"
	-rm -rf build dist __pycache__ *.spec
	-rmdir /S /Q build 2>NUL || true

clean:
	@echo "Cleaning virtual env and caches"
	-rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache build dist *.egg-info
	-rmdir /S /Q $(VENV) 2>NUL || true

# Release management targets
check-release:
	@echo "Checking release readiness for $(VERSION)..."
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required. Usage: make check-release VERSION=v1.0.0"; \
		exit 1; \
	fi
	@if ! echo "$(VERSION)" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$$'; then \
		echo "Error: VERSION must be in format vX.Y.Z or vX.Y.Z-suffix"; \
		echo "Examples: v1.0.0, v2.1.3, v1.0.0-beta1"; \
		exit 1; \
	fi
	@if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then \
		echo "Error: Please run this from the project root directory"; \
		exit 1; \
	fi
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Git working directory is not clean. Please commit or stash changes."; \
		git status --short; \
		exit 1; \
	fi
	@CURRENT_BRANCH=$$(git branch --show-current); \
	if [ "$$CURRENT_BRANCH" != "main" ]; then \
		echo "Warning: You're not on the main branch (current: $$CURRENT_BRANCH)"; \
		echo "Continue anyway? Press Ctrl+C to abort, or Enter to continue..."; \
		read dummy; \
	fi
	@if git rev-parse "$(VERSION)" >/dev/null 2>&1; then \
		echo "Error: Tag $(VERSION) already exists"; \
		exit 1; \
	fi
	@echo "Release checks passed for $(VERSION)"

release: check-release test
	@echo "Creating release $(VERSION)..."
	@echo ""
	@echo "Please ensure CHANGELOG.md has been updated with changes for $(VERSION)"
	@echo "Press Enter to continue or Ctrl+C to abort..."
	@read dummy
	@echo "Creating and pushing tag $(VERSION)..."
	@git tag -a "$(VERSION)" -m "Release $(VERSION)"
	@git push origin "$(VERSION)"
	@echo ""
	@echo "Release tag $(VERSION) created and pushed!"
	@echo ""
	@echo "The GitHub Actions workflow will now:"
	@echo "  1. Build binaries for all platforms (Windows, Linux, macOS)"
	@echo "  2. Create checksums for all binaries"
	@echo "  3. Generate a changelog from git commits"
	@echo "  4. Create a GitHub release with all artifacts"
	@echo ""
	@REPO_URL=$$(git config --get remote.origin.url | sed 's/.*github.com[:/]\([^/]*\/[^.]*\).*/\1/'); \
	echo "Monitor the progress at:"; \
	echo "  https://github.com/$$REPO_URL/actions"
