from __future__ import annotations

from datetime import datetime, time, timedelta

import requests
from fastapi import HTTPException

from app.helpers.train_helper import parse_train_status_html
from app.schemas.train_schema import TrainEvent, TrainStatusResponse
from app.utils.train_util import UpstreamError, fetch_train_status_html


def _compute_event_window(
    *,
    start_time_raw: str | None,
    end_time_raw: str | None,
) -> tuple[datetime, datetime]:
    now = datetime.now()
    today = now.date()

    local_tz = datetime.now().astimezone().tzinfo

    def _normalize_dt(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt
        if local_tz is None:
            return dt.replace(tzinfo=None)
        return dt.astimezone(local_tz).replace(tzinfo=None)

    def _parse_bound(raw: str) -> tuple[datetime | None, time | None]:
        s = raw.strip()
        # Support common ISO form with Z suffix.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(s)
            return _normalize_dt(dt), None
        except ValueError:
            pass

        try:
            return None, time.fromisoformat(s)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid time format: '{raw}'. Use HH:MM[:SS] or ISO datetime "
                    "(e.g. 2026-01-01T10:30:00 or 2026-01-01T10:30:00Z)."
                ),
            ) from e

    start_dt_raw: datetime | None = None
    start_t_raw: time | None = None
    end_dt_raw: datetime | None = None
    end_t_raw: time | None = None

    if start_time_raw is not None:
        start_dt_raw, start_t_raw = _parse_bound(start_time_raw)
    if end_time_raw is not None:
        end_dt_raw, end_t_raw = _parse_bound(end_time_raw)

    if start_time_raw is None and end_time_raw is None:
        start_dt = datetime.combine(today, time(0, 0, 0))
        end_dt = datetime.combine(today + timedelta(days=1), time(0, 0, 0))
        return start_dt, end_dt

    base_date = (
        start_dt_raw.date()
        if start_dt_raw is not None
        else (end_dt_raw.date() if end_dt_raw is not None else today)
    )

    def _to_datetime(dt_part: datetime | None, t_part: time | None) -> datetime:
        if dt_part is not None:
            return dt_part
        if t_part is not None:
            return datetime.combine(base_date, t_part)
        return now

    if start_time_raw is None and end_time_raw is not None:
        start_dt = now
        end_dt = _to_datetime(end_dt_raw, end_t_raw)
        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt
        return start_dt, end_dt

    if start_time_raw is not None and end_time_raw is None:
        start_dt = _to_datetime(start_dt_raw, start_t_raw)
        end_dt = now
        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt
        return start_dt, end_dt

    # Both provided
    start_dt = _to_datetime(start_dt_raw, start_t_raw)
    end_dt = _to_datetime(end_dt_raw, end_t_raw)

    if end_dt < start_dt:
        # If both were time-only, interpret as spanning midnight into the next day.
        if start_dt_raw is None and end_dt_raw is None and start_t_raw and end_t_raw:
            end_dt = end_dt + timedelta(days=1)
        else:
            start_dt, end_dt = end_dt, start_dt
    return start_dt, end_dt


def _validate_train_number(train_number: int) -> None:

    # Indian Railways train numbers are typically 5 digits.
    if train_number < 10000 or train_number > 99999:
        raise HTTPException(
            status_code=422,
            detail="train_number must be a 5-digit number (10000-99999)",
        )


def get_train_status(
    train_number: int,
    start_time: str | None = None,
    end_time: str | None = None,
) -> TrainStatusResponse:
    """Orchestrate fetching + parsing into a Swagger-friendly response model."""
    _validate_train_number(train_number)

    try:
        html_text = fetch_train_status_html(train_number)
    except UpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail="Upstream request failed while fetching train status",
        ) from e

    parsed = parse_train_status_html(html_text)
    events = [TrainEvent(**e) for e in parsed.get("events", [])]

    window_start, window_end = _compute_event_window(
        start_time_raw=start_time,
        end_time_raw=end_time,
    )

    events = [
        e
        for e in events
        if e.datetime is not None and window_start <= e.datetime < window_end
    ]

    return TrainStatusResponse(
        train_number=train_number,
        start_date=parsed.get("start_date"),
        last_update=parsed.get("last_update"),
        events=events,
    )
