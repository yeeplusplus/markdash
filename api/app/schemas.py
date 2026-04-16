from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str | None
    side_label: str | None
    question: str
    slug: str | None
    category: str | None
    end_date: datetime | None
    outcomes: list[Any]
    volume: float | None
    liquidity: float | None
    active: bool | None
    closed: bool | None
    yes_price: float | None
    last_snapshot_ts: datetime | None


class MarketListOut(BaseModel):
    items: list[MarketOut]
    next_cursor: str | None


class EventOut(BaseModel):
    id: str
    title: str
    category: str | None
    start_date: datetime | None
    end_date: datetime | None


class EventWithMarketsOut(EventOut):
    markets: list[MarketOut]
    sum_yes: float | None
    arb_gap: float | None


class MarketDetailOut(MarketOut):
    event: EventOut | None
    siblings: list[MarketOut]


class SnapshotOut(BaseModel):
    ts: datetime
    source_ts: datetime | None
    yes_price: float | None
    prices: dict[str, float]
    volume: float | None
    liquidity: float | None


class HistoryOut(BaseModel):
    market_id: str
    window: str
    points: list[SnapshotOut]


class InsightOut(BaseModel):
    id: int
    kind: str
    event_id: str | None
    event_title: str | None
    window_start: datetime
    window_end: datetime
    window_bucket: datetime
    stddev: float | None
    arb_gap: float | None
    narrative: str
    created_at: datetime


class InsightsListOut(BaseModel):
    items: list[InsightOut]
    stale: bool
