from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import EventWithMarketsOut, MarketOut

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/{event_id}", response_model=EventWithMarketsOut)
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> EventWithMarketsOut:
    ev = (
        await session.execute(
            text(
                """
                SELECT id, title, category, start_date, end_date
                FROM events WHERE id = :id
                """
            ),
            {"id": event_id},
        )
    ).mappings().first()
    if ev is None:
        raise HTTPException(status_code=404, detail="event not found")

    rows = (
        await session.execute(
            text(
                """
                SELECT
                    m.id, m.event_id, m.side_label, m.question, m.slug, m.category,
                    m.end_date, m.outcomes, m.volume, m.liquidity, m.active, m.closed,
                    s.yes_price, s.ts AS last_snapshot_ts
                FROM markets m
                LEFT JOIN LATERAL (
                    SELECT yes_price, ts FROM market_snapshots
                    WHERE market_id = m.id ORDER BY ts DESC LIMIT 1
                ) s ON TRUE
                WHERE m.event_id = :id
                ORDER BY COALESCE(m.volume, 0) DESC
                """
            ),
            {"id": event_id},
        )
    ).mappings().all()

    markets = [
        MarketOut(
            id=r["id"],
            event_id=r["event_id"],
            side_label=r["side_label"],
            question=r["question"],
            slug=r["slug"],
            category=r["category"],
            end_date=r["end_date"],
            outcomes=r["outcomes"] or [],
            volume=float(r["volume"]) if r["volume"] is not None else None,
            liquidity=float(r["liquidity"]) if r["liquidity"] is not None else None,
            active=r["active"],
            closed=r["closed"],
            yes_price=float(r["yes_price"]) if r["yes_price"] is not None else None,
            last_snapshot_ts=r["last_snapshot_ts"],
        )
        for r in rows
    ]

    yes_prices = [m.yes_price for m in markets if m.yes_price is not None]
    sum_yes = sum(yes_prices) if yes_prices else None
    arb_gap = (sum_yes - 1.0) if (sum_yes is not None and len(yes_prices) >= 2) else None

    return EventWithMarketsOut(
        id=ev["id"],
        title=ev["title"],
        category=ev["category"],
        start_date=ev["start_date"],
        end_date=ev["end_date"],
        markets=markets,
        sum_yes=sum_yes,
        arb_gap=arb_gap,
    )
