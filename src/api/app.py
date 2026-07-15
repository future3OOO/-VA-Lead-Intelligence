from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import (
    campaign_router,
    campaign_run_router,
    company_router,
    cost_ledger_router,
    discovery_event_router,
    export_record_router,
    lead_assessment_router,
    outcome_router,
    review_assignment_router,
    scorecard_router,
    source_health_router,
    suppression_router,
    workspace_router,
)
from config.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings()
    app.state.settings = settings
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="VA Lead Intelligence API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(workspace_router)
    app.include_router(company_router)
    app.include_router(campaign_router)
    app.include_router(campaign_run_router)
    app.include_router(discovery_event_router)
    app.include_router(scorecard_router)
    app.include_router(lead_assessment_router)
    app.include_router(review_assignment_router)
    app.include_router(suppression_router)
    app.include_router(export_record_router)
    app.include_router(outcome_router)
    app.include_router(cost_ledger_router)
    app.include_router(source_health_router)
    return app


app = create_app()
