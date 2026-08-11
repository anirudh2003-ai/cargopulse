#!/usr/bin/env bash

# ============================================================
# CargoPulse project structure setup
# ============================================================
#
# SAFE:
# - Does NOT delete anything
# - Does NOT move anything
# - Does NOT overwrite existing files
# - Can be run multiple times
# ============================================================

set -e

echo "Setting up CargoPulse project structure..."


# ============================================================
# 1. AIRFLOW
# ============================================================

mkdir -p airflow/dags
mkdir -p airflow/plugins
mkdir -p airflow/logs


# ============================================================
# 2. FASTAPI BACKEND
# ============================================================

mkdir -p api/routes
mkdir -p api/schemas
mkdir -p api/services
mkdir -p api/db


# Create Python package files only if missing

[ -e api/__init__.py ] || touch api/__init__.py
[ -e api/routes/__init__.py ] || touch api/routes/__init__.py
[ -e api/schemas/__init__.py ] || touch api/schemas/__init__.py
[ -e api/services/__init__.py ] || touch api/services/__init__.py
[ -e api/db/__init__.py ] || touch api/db/__init__.py


# ============================================================
# 3. DBT
# ============================================================

mkdir -p dbt/models/staging
mkdir -p dbt/models/intermediate
mkdir -p dbt/models/analytics
mkdir -p dbt/models/risk
mkdir -p dbt/macros
mkdir -p dbt/seeds
mkdir -p dbt/snapshots
mkdir -p dbt/tests


# ============================================================
# 4. TEST STRUCTURE
# ============================================================

# Preserve existing tests/ directory and add categories.

mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/regression


[ -e tests/__init__.py ] || touch tests/__init__.py
[ -e tests/unit/__init__.py ] || touch tests/unit/__init__.py
[ -e tests/integration/__init__.py ] || touch tests/integration/__init__.py
[ -e tests/regression/__init__.py ] || touch tests/regression/__init__.py


# ============================================================
# 5. SCRIPTS
# ============================================================

mkdir -p scripts


# ============================================================
# 6. DOCKER
# ============================================================

mkdir -p docker


# ============================================================
# 7. CONFIGURATION
# ============================================================

mkdir -p config


# ============================================================
# 8. DOCUMENTATION
# ============================================================

mkdir -p docs
mkdir -p docs/architecture
mkdir -p docs/images


# ============================================================
# 9. DATA DIRECTORIES
#
# These preserve the bronze/silver/gold architecture.
# ============================================================

mkdir -p data/raw
mkdir -p data/bronze
mkdir -p data/silver
mkdir -p data/gold


# ============================================================
# 10. DASHBOARD SUBSTRUCTURE
#
# Your dashboard directory already exists.
# We only add useful internal structure.
# ============================================================

mkdir -p dashboard/pages
mkdir -p dashboard/components
mkdir -p dashboard/utils


# ============================================================
# 11. GITHUB ACTIONS
# ============================================================

mkdir -p .github/workflows


# ============================================================
# 12. OPTIONAL LOCAL LOG DIRECTORY
# ============================================================

mkdir -p logs


# ============================================================
# 13. PLACEHOLDER FILES
#
# Only created if they do not already exist.
# Existing files are NEVER overwritten.
# ============================================================

[ -e api/main.py ] || touch api/main.py

[ -e api/db/database.py ] || touch api/db/database.py

[ -e dashboard/app.py ] || touch dashboard/app.py

[ -e scripts/run_pipeline.sh ] || touch scripts/run_pipeline.sh

[ -e config/__init__.py ] || touch config/__init__.py

[ -e config/settings.py ] || touch config/settings.py


echo ""
echo "============================================"
echo "CargoPulse structure successfully prepared."
echo "No existing files or directories were deleted."
echo "No existing files were overwritten."
echo "============================================"
