"""Risk analytics endpoints for CargoPulse."""

from datetime import date
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
from api.schemas.risk import (
    RiskDetail,
    RiskSummary,
)
from api.services.risk import (
    fetch_latest_risk,
    fetch_risk_by_date,
    fetch_risk_history,
)

router = APIRouter(
    prefix="/api/v1/risk",
    tags=["risk"],
)


@router.get(
    "/latest",
    response_model=RiskDetail,
)
def latest_risk(
    engine: Annotated[
        Engine,
        Depends(get_engine),
    ],
) -> RiskDetail:
    """Return the latest operational supply-risk index."""

    record = fetch_latest_risk(engine)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No risk data available",
        )

    return RiskDetail.model_validate(record)


@router.get(
    "/daily",
    response_model=list[RiskSummary],
)
def daily_risk(
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
) -> list[RiskSummary]:
    """Return recent operational risk history."""

    records = fetch_risk_history(
        engine=engine,
        limit=limit,
    )

    return [
        RiskSummary.model_validate(record)
        for record in records
    ]


@router.get(
    "/{metric_date}",
    response_model=RiskDetail,
)
def risk_by_date(
    metric_date: date,
    engine: Annotated[
        Engine,
        Depends(get_engine),
    ],
) -> RiskDetail:
    """Return operational risk for a specific date."""

    record = fetch_risk_by_date(
        engine=engine,
        metric_date=metric_date,
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No risk data available for "
                f"{metric_date.isoformat()}"
            ),
        )

    return RiskDetail.model_validate(record)
