"""Integration tests for CargoPulse pipeline validation."""

from __future__ import annotations

import pytest

from pipeline.stages.quality_gate import run_quality_gate
from pipeline.stages.validate_database import run_validate_database


@pytest.mark.integration
def test_database_validation_passes():
    results = run_validate_database()

    assert results["ais_positions"] > 0
    assert results["missing_locations"] == 0
    assert results["stuck_processing"] == 0


@pytest.mark.integration
def test_final_quality_gate_passes():
    results = run_quality_gate()

    assert results["call_analytics"] > 0
    assert results["daily_metrics"] > 0
    assert results["historical_baselines"] > 0
    assert results["risk_scores"] > 0
    assert results["risk_explanations"] > 0
    assert results["invalid_risk_scores"] == 0
