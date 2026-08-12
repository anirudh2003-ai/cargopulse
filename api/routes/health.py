"""Health endpoints for the CargoPulse API."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from api.db.database import get_engine
from api.schemas.health import HealthResponse


router = APIRouter(
    tags=["health"],
)


@router.get(
    "/health",
    response_model=HealthResponse,
)
def health_check(
    engine: Annotated[
        Engine,
        Depends(get_engine),
    ],
) -> HealthResponse:
    """Check API and PostgreSQL availability."""

    try:
        with engine.connect() as connection:
            database_check = connection.execute(
                text("SELECT 1")
            ).scalar_one()

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from error

    if database_check != 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed",
        )

    return HealthResponse(
        status="ok",
        database="ok",
    )
