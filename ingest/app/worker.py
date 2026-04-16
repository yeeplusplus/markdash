from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("ingest")

DATABASE_URL = os.environ["DATABASE_URL"]
POLYMARKET_BASE_URL = os.environ.get(
    "POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com"
)
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "8"))
HTTP_RETRY_BACKOFFS = (0.5, 1.0, 2.0)
FETCH_LIMIT = int(os.environ.get("FETCH_LIMIT", "500"))

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=3, max_overflow=2)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ------- HTTP --------------------------------------------------------------


async def fetch_markets_once(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    url = f"{POLYMARKET_BASE_URL}/markets"
    last_exc: Exception | None = None
    for attempt, backoff in enumerate([0.0, *HTTP_RETRY_BACKOFFS]):
        if backoff:
            await asyncio.sleep(backoff)
        try:
            resp = await client.get(
                url,
                params={"limit": FETCH_LIMIT, "active": "true", "closed": "false"},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            log.warning("gamma fetch attempt %d failed: %s", attempt + 1, exc)
    assert last_exc is not None
    raise last_exc


# ------- Parsing + normalization -------------------------------------------


def _parse_json_str(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _parse_ts(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_prices(outcomes: list | None, outcome_prices: list | None) -> dict[str, float]:
    """Return {label: price_float} map for JSONB storage. Drops invalid rows."""
    if not outcomes or not outcome_prices:
        return {}
    prices: dict[str, float] = {}
    for label, raw in zip(outcomes, outcome_prices):
        try:
            prices[str(label)] = float(raw)
        except (TypeError, ValueError):
            continue
    return prices


def derive_yes_price(prices: dict[str, float]) -> float | None:
    """3-case rule per spec:
    (a) explicit "Yes" key -> use it
    (b) exactly two outcomes -> first one as YES-equivalent
    (c) else -> None
    """
    if not prices:
        return None
    for key in prices:
        if key.lower() == "yes":
            return prices[key]
    if len(prices) == 2:
        first_key = next(iter(prices))
        return prices[first_key]
    return None


# ------- Persistence --------------------------------------------------------


UPSERT_EVENT_SQL = text(
    """
    INSERT INTO events (id, title, category, start_date, end_date, first_seen_at, last_seen_at)
    VALUES (:id, :title, :category, :start_date, :end_date, now(), now())
    ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title,
        category = COALESCE(EXCLUDED.category, events.category),
        start_date = COALESCE(EXCLUDED.start_date, events.start_date),
        end_date = COALESCE(EXCLUDED.end_date, events.end_date),
        last_seen_at = now()
    """
)

UPSERT_MARKET_SQL = text(
    """
    INSERT INTO markets (
        id, event_id, side_label, question, slug, category, end_date,
        outcomes, volume, liquidity, active, closed, first_seen_at, last_seen_at
    )
    VALUES (
        :id, :event_id, :side_label, :question, :slug, :category, :end_date,
        CAST(:outcomes AS jsonb), :volume, :liquidity, :active, :closed, now(), now()
    )
    ON CONFLICT (id) DO UPDATE SET
        event_id = COALESCE(EXCLUDED.event_id, markets.event_id),
        side_label = COALESCE(EXCLUDED.side_label, markets.side_label),
        question = EXCLUDED.question,
        slug = COALESCE(EXCLUDED.slug, markets.slug),
        category = COALESCE(EXCLUDED.category, markets.category),
        end_date = COALESCE(EXCLUDED.end_date, markets.end_date),
        outcomes = EXCLUDED.outcomes,
        volume = EXCLUDED.volume,
        liquidity = EXCLUDED.liquidity,
        active = EXCLUDED.active,
        closed = EXCLUDED.closed,
        last_seen_at = now()
    """
)

INSERT_SNAPSHOT_SQL = text(
    """
    INSERT INTO market_snapshots (market_id, ts, source_ts, yes_price, prices, volume, liquidity)
    VALUES (:market_id, now(), :source_ts, :yes_price, CAST(:prices AS jsonb), :volume, :liquidity)
    """
)


async def persist_market(
    session: AsyncSession,
    market: dict[str, Any],
    log_shape_once: dict[str, bool],
) -> bool:
    outcomes = _parse_json_str(market.get("outcomes")) or []
    outcome_prices = _parse_json_str(market.get("outcomePrices")) or []
    prices = normalize_prices(outcomes, outcome_prices)
    yes_price = derive_yes_price(prices)

    events = market.get("events") or []
    primary_event = events[0] if events else None
    event_id: str | None = None
    if primary_event and primary_event.get("id"):
        event_id = str(primary_event["id"])
        await session.execute(
            UPSERT_EVENT_SQL,
            {
                "id": event_id,
                "title": primary_event.get("title") or "(untitled)",
                "category": primary_event.get("category"),
                "start_date": _parse_ts(primary_event.get("startDate")),
                "end_date": _parse_ts(primary_event.get("endDate")),
            },
        )

    market_id = str(market["id"])
    await session.execute(
        UPSERT_MARKET_SQL,
        {
            "id": market_id,
            "event_id": event_id,
            "side_label": market.get("groupItemTitle"),
            "question": market.get("question") or "(untitled)",
            "slug": market.get("slug"),
            "category": market.get("category"),
            "end_date": _parse_ts(market.get("endDate")),
            "outcomes": json.dumps(outcomes),
            "volume": market.get("volumeNum"),
            "liquidity": market.get("liquidityNum"),
            "active": market.get("active"),
            "closed": market.get("closed"),
        },
    )

    await session.execute(
        INSERT_SNAPSHOT_SQL,
        {
            "market_id": market_id,
            "source_ts": _parse_ts(market.get("updatedAt")),
            "yes_price": yes_price,
            "prices": json.dumps(prices),
            "volume": market.get("volumeNum"),
            "liquidity": market.get("liquidityNum"),
        },
    )

    if not log_shape_once["logged"]:
        log.info(
            "first market parsed: id=%s event_id=%s outcomes_keys=%s yes_price=%s",
            market_id,
            event_id,
            list(prices.keys()),
            yes_price,
        )
        log_shape_once["logged"] = True

    return yes_price is not None


# ------- Main loop ----------------------------------------------------------


async def ingest_cycle(client: httpx.AsyncClient, log_shape_once: dict[str, bool]) -> None:
    markets = await fetch_markets_once(client)
    normalized_count = 0
    async with SessionLocal() as session:
        async with session.begin():
            for market in markets:
                try:
                    if await persist_market(session, market, log_shape_once):
                        normalized_count += 1
                except Exception:
                    log.exception("persist_market failed for id=%s", market.get("id"))
    log.info(
        "ingest: poll ok rows=%d yes_normalized=%d", len(markets), normalized_count
    )


async def main() -> None:
    log.info(
        "ingest-worker starting poll_interval=%ss base_url=%s",
        POLL_INTERVAL_SECONDS,
        POLYMARKET_BASE_URL,
    )
    log_shape_once = {"logged": False}
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await ingest_cycle(client, log_shape_once)
            except Exception:
                log.exception("ingest cycle failed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
