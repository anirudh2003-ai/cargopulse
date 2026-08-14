"""CargoPulse FastAPI application."""

from fastapi import FastAPI

from api.routes.health import router as health_router
from api.routes.operations import router as operations_router
from api.routes.risk import router as risk_router

app = FastAPI(
    title="CargoPulse API",
    description=(
        "Read-only LNG terminal operational "
        "intelligence and supply-risk API."
    ),
    version="0.1.0",
)


app.include_router(health_router)
app.include_router(risk_router)
app.include_router(operations_router)
