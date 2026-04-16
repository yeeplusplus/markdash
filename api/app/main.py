from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .db import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("api")

STATIC_DIR = "/app/static"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


async def run_schema_bootstrap() -> None:
    sql = SCHEMA_FILE.read_text()
    async with engine.begin() as conn:
        for stmt in _split_sql(sql):
            await conn.execute(text(stmt))
    log.info("schema bootstrap complete")


def _split_sql(sql: str) -> list[str]:
    # split on semicolons that terminate statements, ignore trailing blanks
    parts = [s.strip() for s in sql.split(";")]
    return [s for s in parts if s]


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api starting up")
    try:
        await run_schema_bootstrap()
    except Exception:
        log.exception("schema bootstrap failed")
        raise
    yield
    log.info("api shutting down")
    await engine.dispose()


app = FastAPI(title="markdash", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    db_ok = False
    ingest_fresh = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
            row = await conn.execute(
                text("SELECT EXTRACT(EPOCH FROM (now() - max(ts))) FROM market_snapshots")
            )
            age = row.scalar()
            if age is not None and age <= 90:
                ingest_fresh = True
    except Exception:
        log.exception("healthz db probe failed")

    return {
        "db_ok": db_ok,
        "ingest_fresh": ingest_fresh,
        "static_bundle_ok": os.path.exists(os.path.join(STATIC_DIR, "index.html")),
    }


if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
