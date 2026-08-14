"""Port-call detection stage."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from pipeline.config import PROJECT_ROOT, load_settings
from pipeline.logging_config import get_logger, log_event

logger = get_logger("cargopulse.detect_calls")

DETECT_PORT_CALLS_SQL = (
    PROJECT_ROOT
    / "processing"
    / "detect_port_calls.sql"
)


def run_detect_calls() -> int:
    """Rebuild detected terminal calls from loaded AIS data."""

    settings = load_settings()

    if not DETECT_PORT_CALLS_SQL.exists():
        raise FileNotFoundError(
            f"Port-call SQL not found: "
            f"{DETECT_PORT_CALLS_SQL}"
        )

    sql = DETECT_PORT_CALLS_SQL.read_text(
        encoding="utf-8"
    ).strip()

    if not sql:
        raise RuntimeError(
            "Port-call detection SQL is empty"
        )

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    log_event(
        logger,
        "port_call_detection_started",
    )

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(sql)

            port_call_count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.port_calls
                    """
                )
            ).scalar_one()
    finally:
        engine.dispose()

    port_call_count = int(port_call_count)

    if port_call_count <= 0:
        raise RuntimeError(
            "Port-call detection produced zero calls"
        )

    log_event(
        logger,
        "port_call_detection_complete",
        port_calls=port_call_count,
    )

    return port_call_count
