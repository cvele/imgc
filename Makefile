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
	PYI_HIDDEN_IMPORTS := \
		PIL._tkinter_finder \
		PIL._imaging \
		PIL.ImageQt \
		PIL.ImageFile \
		PIL._imagingft \
		watchdog.observers.inotify_buffer \
		watchdog.observers.winapi \
		imageio.plugins.freeimage \
		imageio.plugins.ffmpeg \
		imageio

.PHONY: help venv install run test lint format clean

help:
	@echo "Makefile targets for this project"
	@echo "  make venv       - create virtualenv at $(VENV)"
	@echo "  make install    - create venv and install requirements"
	@echo "  make run        - run watcher (use CLI flags to configure)"
	@echo "  make test       - run pytest"
	@echo "  make lint       - run quick syntax checks (py_compile)"
	@echo "  make build      - build a standalone binary using PyInstaller"
	@echo "  make package    - create a zip of the built binary (dist)"
	@echo "  make format     - run black formatter"
	@echo "  make clean      - remove build artifacts and venv"

venv:
	@echo Ensuring virtualenv at '$(VENV)'.
	@$(PYTHON) -m venv $(VENV)
	@echo "To activate in PowerShell: .\\$(VENV)\\Scripts\\Activate.ps1"
	@echo "To activate (POSIX): . $(VENV)/bin/activate"

install: venv
	@echo "Installing requirements into $(VENV)"
	$(PY) -m pip install --upgrade pip setuptools wheel
	$(PY) -m pip install -r requirements.txt

run:
	@echo "Running watcher (use --help for options)"
	$(PY) main.py

test: venv
	@echo "Ensuring pytest is installed in the virtualenv"
	@$(PY) -m pip install pytest
	$(PY) -m pytest -q

coverage: venv
	@echo "Running tests with coverage"
	@$(PY) -m pip install coverage pytest
	@$(PY) -m coverage run -m pytest
	@$(PY) -m coverage report -m
	@$(PY) -m coverage xml -o coverage.xml
	@$(PY) -m coverage html -d coverage_html

lint:
	@echo "Running quick syntax checks"
	$(PY) -m py_compile main.py imgc/*.py || true

format:
	@echo "Formatting with black (will install if missing)"
	$(PY) -m pip install black
	$(PY) -m black .


build: venv
	@echo "Building standalone binary with PyInstaller"
	$(PY) -m pip install --upgrade pyinstaller
	$(PY) -m PyInstaller --onefile --name $(BUILD_NAME) \
		--add-data "imgc$(DATASEP)imgc" \
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
