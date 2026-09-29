from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import alerts, areas, health, live, risk, saved
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Heavy-rainfall early warning and inundation prediction for Assam (SIH PS 26071).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (health.router, areas.router, risk.router, alerts.router, saved.router, live.router):
    app.include_router(router, prefix="/api")


@app.exception_handler(NotImplementedError)
async def not_implemented(_: Request, exc: NotImplementedError) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": str(exc)})
