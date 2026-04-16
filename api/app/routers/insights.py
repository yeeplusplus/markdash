from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import InsightOut, InsightsListOut

router = APIRouter(prefix="/api/insights", tags=["insights"])

STALE_SECONDS = 20 * 60  # consider stale if no insight in last 20 minutes


@router.get("/volatility", response_model=InsightsListOut)
async def volatility_insights(
    kind: Literal["volatility", "coherence"] = "volatility",
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> InsightsListOut:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                    i.id, i.kind, i.event_id,
                    e.title AS event_title,
                    i.window_start, i.window_end, i.window_bucket,
                    i.stddev, i.arb_gap, i.narrative, i.created_at
                FROM ai_insights i
                LEFT JOIN events e ON e.id = i.event_id
                WHERE i.kind = :kind
                ORDER BY i.created_at DESC
                LIMIT :limit
                """
            ),
            {"kind": kind, "limit": limit},
        )
    ).mappings().all()

    age_row = (
        await session.execute(
            text(
                """
                SELECT EXTRACT(EPOCH FROM (now() - max(created_at))) AS age
                FROM ai_insights WHERE kind = :kind
                """
            ),
            {"kind": kind},
        )
    ).first()
    age = age_row.age if age_row and age_row.age is not None else None
    stale = age is None or age > STALE_SECONDS

    items = [
        InsightOut(
            id=r["id"],
            kind=r["kind"],
            event_id=r["event_id"],
            event_title=r["event_title"],
            window_start=r["window_start"],
            window_end=r["window_end"],
            window_bucket=r["window_bucket"],
            stddev=float(r["stddev"]) if r["stddev"] is not None else None,
            arb_gap=float(r["arb_gap"]) if r["arb_gap"] is not None else None,
            narrative=r["narrative"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return InsightsListOut(items=items, stale=stale)
