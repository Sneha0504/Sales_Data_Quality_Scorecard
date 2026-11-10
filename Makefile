# Makefile for Sales_Data_Quality_Scorecard.
# All paths are relative to this directory, so the enclosing "Coding Projects"
# path (which contains a space) never appears in a recipe. Recipes quote paths
# defensively regardless.

BASE_PYTHON ?= python3.12
VENV := .venv
PY := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

RAW := data/raw/online_retail_II.xlsx
DB := data/warehouse.db

.PHONY: setup load rules curate reconcile test dashboard all clean

# Environment setup: create the virtualenv and install pinned requirements.
setup:
	"$(BASE_PYTHON)" -m venv "$(VENV)"
	"$(PY)" -m pip install --upgrade pip
	"$(PY)" -m pip install -r requirements.txt

# Load raw workbook into SQLite, then profile and draft the data-quality report.
# Rebuilt only when the loader or the raw data changes.
$(DB): src/load.py src/profile_data.py src/config_util.py config/config.yaml $(RAW)
	"$(PY)" src/load.py
	"$(PY)" src/profile_data.py

load: $(DB)

# Run the YAML rule catalog against the warehouse and log a summary.
rules: load
	"$(PY)" src/rule_engine.py

# Build the curated layer (depends on load + rules).
curate: load rules
	"$(PY)" src/curate.py

# Reconcile raw vs curated and verify the internal identity.
reconcile: curate
	"$(PY)" src/reconcile.py

# Full pipeline, then refresh the report so its rule-results section is filled.
all: reconcile
	"$(PY)" src/profile_data.py

# Unit B targets (scripts arrive later); wired here so the interface is stable.
test:
	"$(PYTEST)" -q

dashboard:
	"$(PY)" src/build_dashboard.py

# Remove the rebuildable warehouse database.
clean:
	rm -f "$(DB)"
