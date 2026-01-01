from fastapi import FastAPI, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.train_schema import TrainStatusResponse
from app.services.train_service import get_train_status

app = FastAPI(
    title="Train Track API",
    version="0.1.0",
    description="FastAPI service for fetching and parsing Indian Railways train running status.",
)


@app.get("/")
async def read_root():
    return {"message": "Welcome to the Train Track API"}


@app.get("/train/{train_number}", response_model=TrainStatusResponse)
async def get_train(
    train_number: int,
    start_time: str | None = Query(
        default=None,
        description=(
            "Optional lower-bound for filtering events. Accepts either time-only "
            "(HH:MM[:SS]) or ISO datetime (e.g. 2026-01-01T10:30:00)."
        ),
    ),
    end_time: str | None = Query(
        default=None,
        description=(
            "Optional upper-bound for filtering events. Accepts either time-only "
            "(HH:MM[:SS]) or ISO datetime (e.g. 2026-01-01T18:30:00)."
        ),
    ),
) -> TrainStatusResponse:
    """Get train running status for the given train number."""
    return await run_in_threadpool(get_train_status, train_number, start_time, end_time)
