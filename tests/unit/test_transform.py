"""Unit tests for dbt pipeline configuration."""

from __future__ import annotations

import pytest

from pipeline.stages.transform import build_dbt_environment

pytestmark = pytest.mark.unit

def test_build_dbt_environment():
    environment = build_dbt_environment(
        "postgresql+psycopg2://"
        "test_user:test_password@db.example:5433/test_db"
    )

    assert environment["DBT_HOST"] == "db.example"
    assert environment["DBT_PORT"] == "5433"
    assert environment["DBT_USER"] == "test_user"
    assert environment["DBT_PASSWORD"] == "test_password"
    assert environment["DBT_DBNAME"] == "test_db"
