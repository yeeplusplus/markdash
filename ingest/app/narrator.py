from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("narrator")

DATABASE_URL = os.environ["DATABASE_URL"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NARRATOR_INTERVAL_SECONDS = int(os.environ.get("NARRATOR_INTERVAL_SECONDS", "900"))  # 15 min
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
VOL_TOP_N = 5
COH_TOP_N = 5

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=1)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


VOL_SQL = text(
    """
    WITH per_market AS (
        SELECT
            m.id AS market_id,
            m.event_id,
            stddev(s.yes_price) AS sd,
            min(s.ts) AS ws,
            max(s.ts) AS we,
            count(*) AS n
        FROM markets m
        JOIN market_snapshots s ON s.market_id = m.id
        WHERE s.ts >= now() - interval '60 minutes'
          AND s.yes_price IS NOT NULL
        GROUP BY m.id, m.event_id
        HAVING count(*) >= 3 AND stddev(s.yes_price) IS NOT NULL
    ),
    per_event AS (
        SELECT event_id, max(sd) AS max_sd, min(ws) AS ws, max(we) AS we
        FROM per_market
        WHERE event_id IS NOT NULL
        GROUP BY event_id
    )
    SELECT p.event_id, e.title, p.max_sd, p.ws, p.we
    FROM per_event p
    JOIN events e ON e.id = p.event_id
    ORDER BY p.max_sd DESC
    LIMIT :limit
    """
)

COH_SQL = text(
    """
    WITH latest AS (
        SELECT DISTINCT ON (m.id)
            m.id AS market_id,
            m.event_id,
            s.yes_price
        FROM markets m
        JOIN market_snapshots s ON s.market_id = m.id
        WHERE m.event_id IS NOT NULL AND s.yes_price IS NOT NULL
        ORDER BY m.id, s.ts DESC
    ),
    agg AS (
        SELECT event_id,
               sum(yes_price) AS sum_yes,
               count(*) AS n
        FROM latest
        GROUP BY event_id
        HAVING count(*) >= 2
    )
    SELECT a.event_id, e.title, a.sum_yes, a.n
    FROM agg a
    JOIN events e ON e.id = a.event_id
    ORDER BY abs(a.sum_yes - 1.0) DESC
    LIMIT :limit
    """
)

UPSERT_SQL = text(
    """
    INSERT INTO ai_insights (
        kind, event_id, window_start, window_end, window_bucket,
        stddev, arb_gap, narrative
    )
    VALUES (
        :kind, :event_id, :window_start, :window_end, :window_bucket,
        :stddev, :arb_gap, :narrative
    )
    ON CONFLICT (kind, event_id, window_bucket) DO UPDATE SET
        window_start = EXCLUDED.window_start,
        window_end = EXCLUDED.window_end,
        stddev = EXCLUDED.stddev,
        arb_gap = EXCLUDED.arb_gap,
        narrative = EXCLUDED.narrative,
        created_at = now()
    """
)


def current_bucket(now: datetime | None = None) -> datetime:
    now = now or datetime.now(tz=timezone.utc)
    floored_minute = (now.minute // 15) * 15
    return now.replace(minute=floored_minute, second=0, microsecond=0)


async def fetch_candidates() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    async with SessionLocal() as session:
        vol_rows = (
            (await session.execute(VOL_SQL, {"limit": VOL_TOP_N})).mappings().all()
        )
        coh_rows = (
            (await session.execute(COH_SQL, {"limit": COH_TOP_N})).mappings().all()
        )

    volatility = [
        {
            "event_id": r["event_id"],
            "event_title": r["title"],
            "stddev": float(r["max_sd"]) if r["max_sd"] is not None else None,
            "window_start": r["ws"].isoformat() if r["ws"] else None,
            "window_end": r["we"].isoformat() if r["we"] else None,
        }
        for r in vol_rows
    ]
    coherence = [
        {
            "event_id": r["event_id"],
            "event_title": r["title"],
            "sum_yes": float(r["sum_yes"]) if r["sum_yes"] is not None else None,
            "arb_gap": float(r["sum_yes"] - 1.0) if r["sum_yes"] is not None else None,
            "n_markets": int(r["n"]),
        }
        for r in coh_rows
    ]
    return volatility, coherence


SYSTEM_PROMPT = (
    "You are a calm, sharp prediction-market analyst. "
    "You read Polymarket data and write one concise, plainspoken sentence "
    "per insight — no hedging, no finance-bro jargon, no emojis. "
    "If data is sparse, say so briefly rather than inventing."
)


def build_user_prompt(vol: list[dict], coh: list[dict]) -> str:
    payload = {
        "volatility_candidates": vol,
        "coherence_candidates": coh,
        "notes": [
            "volatility: stddev of YES price across last 60 min, per event (max across member markets)",
            "coherence: sum of YES prices across paired mutually-exclusive markets in an event; "
            "a sum far from 1.0 suggests an arb or a missing outcome",
        ],
    }
    return (
        "Write one-sentence narratives for each candidate below.\n\n"
        "Return STRICT JSON only, matching this shape:\n"
        '{"volatility":[{"event_id":"...","narrative":"..."}],'
        '"coherence":[{"event_id":"...","narrative":"..."}]}\n\n'
        f"Data:\n{json.dumps(payload, indent=2)}"
    )


def extract_json(text_body: str) -> dict[str, Any]:
    # Find the first {...} block; tolerate model adding preamble.
    match = re.search(r"\{.*\}", text_body, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in response")
    return json.loads(match.group(0))


async def call_claude(vol: list[dict], coh: list[dict]) -> dict[str, Any]:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    msg = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(vol, coh)}],
    )
    body = "".join(block.text for block in msg.content if getattr(block, "type", None) == "text")
    return extract_json(body)


async def upsert_insights(
    kind: str,
    rows: list[dict[str, Any]],
    narratives_by_event: dict[str, str],
    window_bucket: datetime,
) -> int:
    if not rows:
        return 0
    window_end = window_bucket
    window_start = window_bucket - timedelta(minutes=60)
    written = 0
    async with SessionLocal() as session:
        async with session.begin():
            for r in rows:
                event_id = r.get("event_id")
                narrative = narratives_by_event.get(str(event_id))
                if not narrative:
                    continue
                stddev = r.get("stddev") if kind == "volatility" else None
                arb_gap = r.get("arb_gap") if kind == "coherence" else None
                await session.execute(
                    UPSERT_SQL,
                    {
                        "kind": kind,
                        "event_id": event_id,
                        "window_start": window_start,
                        "window_end": window_end,
                        "window_bucket": window_bucket,
                        "stddev": stddev,
                        "arb_gap": arb_gap,
                        "narrative": narrative,
                    },
                )
                written += 1
    return written


async def run_once() -> None:
    vol, coh = await fetch_candidates()
    if not vol and not coh:
        log.info("narrator: no candidates yet; skipping")
        return

    log.info("narrator: candidates vol=%d coh=%d", len(vol), len(coh))
    try:
        response = await call_claude(vol, coh)
    except Exception:
        log.exception("narrator: Claude call failed")
        return

    vol_narratives = {
        str(item.get("event_id")): item.get("narrative", "")
        for item in response.get("volatility", [])
        if item.get("event_id") and item.get("narrative")
    }
    coh_narratives = {
        str(item.get("event_id")): item.get("narrative", "")
        for item in response.get("coherence", [])
        if item.get("event_id") and item.get("narrative")
    }

    bucket = current_bucket()
    vol_written = await upsert_insights("volatility", vol, vol_narratives, bucket)
    coh_written = await upsert_insights("coherence", coh, coh_narratives, bucket)
    log.info(
        "narrator: upserted vol=%d coh=%d bucket=%s",
        vol_written,
        coh_written,
        bucket.isoformat(),
    )


async def main() -> None:
    log.info(
        "narrator starting interval=%ss model=%s",
        NARRATOR_INTERVAL_SECONDS,
        CLAUDE_MODEL,
    )
    # small startup delay so ingestion has some snapshots to work with
    await asyncio.sleep(60)
    while True:
        try:
            await run_once()
        except Exception:
            log.exception("narrator cycle failed")
        await asyncio.sleep(NARRATOR_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
