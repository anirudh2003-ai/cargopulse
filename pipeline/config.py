"""Central configuration for CargoPulse."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

DBT_PROJECT_DIR = PROJECT_ROOT / "dbt"
DBT_PROFILES_DIR = PROJECT_ROOT / "dbt" / "profiles"

DEFAULT_SILVER_AIS_PATH = (
    PROJECT_ROOT / "data" / "silver" / "ais_positions.parquet"
)

GOLD_DIR = PROJECT_ROOT / "data" / "gold"


@dataclass(frozen=True)
class Settings:
    database_url: str
    dbt_project_dir: Path
    dbt_profiles_dir: Path
    silver_ais_path: Path
    gold_dir: Path


def load_settings() -> Settings:
    """Load and validate CargoPulse configuration."""

    if ENV_PATH.exists():
        load_dotenv(
            dotenv_path=ENV_PATH,
            override=False,
        )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from the environment or .env"
        )

    return Settings(
        database_url=database_url,
        dbt_project_dir=DBT_PROJECT_DIR,
        dbt_profiles_dir=DBT_PROFILES_DIR,
        silver_ais_path=DEFAULT_SILVER_AIS_PATH,
        gold_dir=GOLD_DIR,
    )
