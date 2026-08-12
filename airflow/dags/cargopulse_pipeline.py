"""Apache Airflow orchestration for the CargoPulse pipeline."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from airflow.sdk import Param, dag, get_current_context, task


@dag(
    dag_id="cargopulse_pipeline",
    description=(
        "End-to-end LNG terminal intelligence pipeline "
        "for CargoPulse."
    ),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=[
        "cargopulse",
        "lng",
        "data-engineering",
    ],
    params={
        "input_csv": Param(
            "",
            type="string",
            minLength=1,
            description=(
                "Raw NOAA AIS CSV path relative to "
                "/opt/cargopulse, for example "
                "data/raw/ais_2023_01.csv"
            ),
        ),
        "enrichment_limit": Param(
            50,
            type="integer",
            minimum=1,
            maximum=500,
            description=(
                "Maximum number of vessels to process "
                "through USCG PSIX."
            ),
        ),
        "skip_enrichment": Param(
            False,
            type="boolean",
            description=(
                "Queue vessels without calling USCG PSIX."
            ),
        ),
    },
)
def cargopulse_pipeline():
    """Orchestrate the complete CargoPulse data pipeline."""

    @task(
        task_id="ingest_ais",
        retries=1,
        retry_delay=timedelta(minutes=2),
    )
    def ingest_ais() -> None:
        from pipeline.stages.ingest import run_ingest

        context = get_current_context()

        input_csv = Path(
            context["params"]["input_csv"]
        )

        run_ingest(
            input_csv=input_csv,
        )

    @task(
        task_id="validate_raw",
        retries=1,
        retry_delay=timedelta(minutes=1),
    )
    def validate_raw() -> None:
        from pipeline.stages.validate_raw import (
            run_validate_raw,
        )

        run_validate_raw()

    @task(
        task_id="load_postgres",
        retries=1,
        retry_delay=timedelta(minutes=2),
    )
    def load_postgres() -> None:
        from pipeline.stages.load import run_load

        run_load()

    @task(
        task_id="enrich_vessels",
        retries=2,
        retry_delay=timedelta(minutes=5),
    )
    def enrich_vessels() -> None:
        from pipeline.stages.enrich import run_enrich

        context = get_current_context()

        run_enrich(
            enrichment_limit=int(
                context["params"]["enrichment_limit"]
            ),
            skip_enrichment=bool(
                context["params"]["skip_enrichment"]
            ),
        )

    @task(
        task_id="validate_database",
        retries=1,
        retry_delay=timedelta(minutes=1),
    )
    def validate_database() -> None:
        from pipeline.stages.validate_database import (
            run_validate_database,
        )

        run_validate_database()

    @task(
        task_id="dbt_build",
        retries=1,
        retry_delay=timedelta(minutes=2),
    )
    def dbt_build() -> None:
        from pipeline.stages.transform import (
            run_transform,
        )

        run_transform()

    @task(
        task_id="export_gold",
        retries=1,
        retry_delay=timedelta(minutes=1),
    )
    def export_gold() -> None:
        from pipeline.stages.export import run_export

        run_export()

    @task(
        task_id="quality_gate",
        retries=1,
        retry_delay=timedelta(minutes=1),
    )
    def quality_gate() -> None:
        from pipeline.stages.quality_gate import (
            run_quality_gate,
        )

        run_quality_gate()

    ingest_task = ingest_ais()
    validate_raw_task = validate_raw()
    load_task = load_postgres()
    enrich_task = enrich_vessels()
    validate_database_task = validate_database()
    dbt_task = dbt_build()
    export_task = export_gold()
    quality_task = quality_gate()

    (
        ingest_task
        >> validate_raw_task
        >> load_task
        >> enrich_task
        >> validate_database_task
        >> dbt_task
        >> export_task
        >> quality_task
    )


cargopulse_pipeline()
