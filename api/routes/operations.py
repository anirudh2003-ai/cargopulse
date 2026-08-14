"""Operational analytics endpoints for CargoPulse."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.engine import Engine

from api.db.database import get_engine
from api.schemas.operations import (
    BerthPerformance,
    CallAnalytics,
    TerminalDailyMetrics,
)
from api.services.operations import (
    fetch_berth_performance,
    fetch_call_by_id,
    fetch_calls,
    fetch_terminal_daily_metrics,
)

router = APIRouter(
    prefix="/api/v1",
)


@router.get(
    "/calls",
    response_model=list[CallAnalytics],
    tags=["calls"],
)
def list_calls(
    engine: Annotated[
        Engine,
        Depends(get_engine),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
        ),
    ] = 25,
) -> list[CallAnalytics]:
    """Return recent validated LNG terminal calls."""

    records = fetch_calls(
        engine=engine,
        limit=limit,
    )

    return [
        CallAnalytics.model_validate(record)
        for record in records
    ]


@router.get(
    "/calls/{validated_call_id}",
    response_model=CallAnalytics,
    tags=["calls"],
)
def call_by_id(
    validated_call_id: int,
    engine: Annotated[
        Engine,
        Depends(get_engine),
    ],
) -> CallAnalytics:
    """Return one validated LNG terminal call."""

    record = fetch_call_by_id(
        engine=engine,
        validated_call_id=validated_call_id,
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No LNG call found for "
                f"validated_call_id={validated_call_id}"
            ),
        )

    return CallAnalytics.model_validate(record)


@router.get(
    "/berths",
    response_model=list[BerthPerformance],
    tags=["berths"],
)
def berth_performance(
    engine: Annotated[
        Engine,
        Depends(get_engine),
    ],
) -> list[BerthPerformance]:
    """Return aggregate LNG berth performance."""

    records = fetch_berth_performance(engine)

    return [
        BerthPerformance.model_validate(record)
        for record in records
    ]


@router.get(
    "/terminal/daily",
    response_model=list[TerminalDailyMetrics],
    tags=["terminal"],
)
def terminal_daily(
    engine: Annotated[
        Engine,
        Depends(get_engine),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=90,
        ),
    ] = 30,
) -> list[TerminalDailyMetrics]:
    """Return recent LNG terminal daily metrics."""

    records = fetch_terminal_daily_metrics(
        engine=engine,
        limit=limit,
    )

    return [
        TerminalDailyMetrics.model_validate(record)
        for record in records
    ]
