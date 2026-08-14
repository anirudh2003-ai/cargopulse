"""dbt transformation stage."""

from __future__ import annotations

import os
import shutil
import subprocess

from sqlalchemy.engine import make_url

from pipeline.config import PROJECT_ROOT, load_settings
from pipeline.logging_config import get_logger, log_event

logger = get_logger("cargopulse.transform")


def find_dbt_executable() -> str:
    """Find the CargoPulse dbt executable."""

    system_dbt = shutil.which("dbt")

    if system_dbt:
        return system_dbt

    project_dbt = (
        PROJECT_ROOT
        / ".venv-dbt"
        / "bin"
        / "dbt"
    )

    if project_dbt.exists():
        return str(project_dbt)

    raise FileNotFoundError(
        "dbt executable was not found"
    )


def build_dbt_environment(
    database_url: str,
) -> dict[str, str]:
    """Create dbt environment variables from DATABASE_URL."""

    url = make_url(database_url)

    environment = os.environ.copy()

    environment["DBT_HOST"] = (
        url.host or "localhost"
    )

    environment["DBT_PORT"] = str(
        url.port or 5432
    )

    environment["DBT_USER"] = (
        url.username or "cargopulse"
    )

    environment["DBT_PASSWORD"] = (
        url.password or ""
    )

    environment["DBT_DBNAME"] = (
        url.database or "cargopulse"
    )

    return environment


def run_transform() -> None:
    """Run the complete CargoPulse dbt DAG."""

    settings = load_settings()

    dbt_executable = find_dbt_executable()

    environment = build_dbt_environment(
        settings.database_url
    )

    command = [
        dbt_executable,
        "build",
        "--project-dir",
        str(settings.dbt_project_dir),
        "--profiles-dir",
        str(settings.dbt_profiles_dir),
    ]

    log_event(
        logger,
        "dbt_build_started",
    )

    subprocess.run(
        command,
        check=True,
        cwd=PROJECT_ROOT,
        env=environment,
    )

    log_event(
        logger,
        "dbt_build_complete",
        status="success",
    )
