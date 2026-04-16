from __future__ import annotations

import base64
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import (
    EventOut,
    HistoryOut,
    MarketDetailOut,
    MarketListOut,
    MarketOut,
    SnapshotOut,
)

router = APIRouter(prefix="/api/markets", tags=["markets"])

SortKey = Literal["volume_desc", "liquidity_desc", "end_date_asc"]

SORT_SQL: dict[str, tuple[str, str]] = {
    # (select expression for sort value, order by clause)
    "volume_desc": ("COALESCE(m.volume, 0)", "sort_val DESC, m.id ASC"),
    "liquidity_desc": ("COALESCE(m.liquidity, 0)", "sort_val DESC, m.id ASC"),
    "end_date_asc": (
        "EXTRACT(EPOCH FROM COALESCE(m.end_date, 'infinity'::timestamptz))",
        "sort_val ASC, m.id ASC",
    ),
}

WINDOW_INTERVAL: dict[str, str] = {
    "1h": "1 hour",
    "6h": "6 hours",
    "24h": "24 hours",
    "7d": "7 days",
}


def _encode_cursor(sort_val: float, id_: str) -> str:
    payload = json.dumps({"v": sort_val, "i": id_}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[float, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return float(payload["v"]), str(payload["i"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc


@router.get("", response_model=MarketListOut)
async def list_markets(
    q: str | None = Query(None, description="search on question"),
    category: str | None = None,
    active: bool | None = None,
    sort: SortKey = "volume_desc",
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> MarketListOut:
    sort_expr, order_by = SORT_SQL[sort]
    direction_op = "<" if "DESC" in order_by else ">"

    clauses: list[str] = []
    params: dict[str, object] = {"limit": limit + 1}

    if q:
        clauses.append("m.question ILIKE :q")
        params["q"] = f"%{q}%"
    if category:
        clauses.append("m.category = :category")
        params["category"] = category
    if active is not None:
        clauses.append("m.active = :active")
        params["active"] = active

    if cursor:
        cur_val, cur_id = _decode_cursor(cursor)
        clauses.append(
            f"({sort_expr}, m.id) {direction_op} (:cur_val, :cur_id)"
        )
        params["cur_val"] = cur_val
        params["cur_id"] = cur_id

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    sql = text(
        f"""
        SELECT
            m.id, m.event_id, m.side_label, m.question, m.slug, m.category,
            m.end_date, m.outcomes, m.volume, m.liquidity, m.active, m.closed,
            s.yes_price, s.ts AS last_snapshot_ts,
            {sort_expr} AS sort_val
        FROM markets m
        LEFT JOIN LATERAL (
            SELECT yes_price, ts
            FROM market_snapshots
            WHERE market_id = m.id
            ORDER BY ts DESC
            LIMIT 1
        ) s ON TRUE
        {where}
        ORDER BY {order_by}
        LIMIT :limit
        """
    )

    result = await session.execute(sql, params)
    rows = result.mappings().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(float(last["sort_val"]), last["id"])
        rows = rows[:limit]

    items = [
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
    return MarketListOut(items=items, next_cursor=next_cursor)


@router.get("/{market_id}", response_model=MarketDetailOut)
async def get_market(
    market_id: str,
    session: AsyncSession = Depends(get_session),
) -> MarketDetailOut:
    row_sql = text(
        """
        SELECT
            m.id, m.event_id, m.side_label, m.question, m.slug, m.category,
            m.end_date, m.outcomes, m.volume, m.liquidity, m.active, m.closed,
            s.yes_price, s.ts AS last_snapshot_ts,
            e.id AS e_id, e.title AS e_title, e.category AS e_category,
            e.start_date AS e_start_date, e.end_date AS e_end_date
        FROM markets m
        LEFT JOIN LATERAL (
            SELECT yes_price, ts FROM market_snapshots
            WHERE market_id = m.id ORDER BY ts DESC LIMIT 1
        ) s ON TRUE
        LEFT JOIN events e ON e.id = m.event_id
        WHERE m.id = :id
        """
    )
    r = (await session.execute(row_sql, {"id": market_id})).mappings().first()
    if r is None:
        raise HTTPException(status_code=404, detail="market not found")

    siblings: list[MarketOut] = []
    if r["event_id"]:
        sib_sql = text(
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
            WHERE m.event_id = :event_id AND m.id <> :id
            ORDER BY COALESCE(m.volume, 0) DESC
            """
        )
        sib_rows = (
            await session.execute(sib_sql, {"event_id": r["event_id"], "id": market_id})
        ).mappings().all()
        siblings = [
            MarketOut(
                id=sr["id"],
                event_id=sr["event_id"],
                side_label=sr["side_label"],
                question=sr["question"],
                slug=sr["slug"],
                category=sr["category"],
                end_date=sr["end_date"],
                outcomes=sr["outcomes"] or [],
                volume=float(sr["volume"]) if sr["volume"] is not None else None,
                liquidity=float(sr["liquidity"]) if sr["liquidity"] is not None else None,
                active=sr["active"],
                closed=sr["closed"],
                yes_price=float(sr["yes_price"]) if sr["yes_price"] is not None else None,
                last_snapshot_ts=sr["last_snapshot_ts"],
            )
            for sr in sib_rows
        ]

    event = None
    if r["e_id"]:
        event = EventOut(
            id=r["e_id"],
            title=r["e_title"],
            category=r["e_category"],
            start_date=r["e_start_date"],
            end_date=r["e_end_date"],
        )

    return MarketDetailOut(
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
        event=event,
        siblings=siblings,
    )


@router.get("/{market_id}/history", response_model=HistoryOut)
async def market_history(
    market_id: str,
    window: Literal["1h", "6h", "24h", "7d"] = "24h",
    session: AsyncSession = Depends(get_session),
) -> HistoryOut:
    interval = WINDOW_INTERVAL[window]
    exists = (
        await session.execute(
            text("SELECT 1 FROM markets WHERE id = :id"), {"id": market_id}
        )
    ).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="market not found")

    sql = text(
        f"""
        SELECT ts, source_ts, yes_price, prices, volume, liquidity
        FROM market_snapshots
        WHERE market_id = :id
          AND ts >= now() - interval '{interval}'
        ORDER BY ts ASC
        """
    )
    rows = (await session.execute(sql, {"id": market_id})).mappings().all()

    points = [
        SnapshotOut(
            ts=r["ts"],
            source_ts=r["source_ts"],
            yes_price=float(r["yes_price"]) if r["yes_price"] is not None else None,
            prices={k: float(v) for k, v in (r["prices"] or {}).items()},
            volume=float(r["volume"]) if r["volume"] is not None else None,
            liquidity=float(r["liquidity"]) if r["liquidity"] is not None else None,
        )
        for r in rows
    ]
    return HistoryOut(market_id=market_id, window=window, points=points)
