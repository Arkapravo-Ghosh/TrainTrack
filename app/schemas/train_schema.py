from __future__ import annotations

from datetime import datetime as DateTime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TrainEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw: str = Field(..., description="Raw status line extracted from upstream HTML")
    type: Literal["Arrived", "Departed"] | None = Field(
        None, description="Event type if detected"
    )
    station: str | None = Field(None, description="Station name if detected")
    code: str | None = Field(None, description="Station code if detected")
    datetime: DateTime | None = Field(
        None, description="Best-effort event timestamp (local time)"
    )
    delay: str | None = Field(None, description="Delay string if present, e.g. '00:10'")


class TrainStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    train_number: int = Field(..., description="5-digit Indian Railways train number")
    start_date: str | None = Field(None, description="Start date reported by upstream")
    last_update: DateTime | None = Field(
        None, description="Last update timestamp reported by upstream"
    )
    events: list[TrainEvent] = Field(
        default_factory=list, description="Best-effort parsed arrival/departure events"
    )
