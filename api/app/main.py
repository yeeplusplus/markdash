from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("api")

STATIC_DIR = "/app/static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api starting up")
    yield
    log.info("api shutting down")


app = FastAPI(title="markdash", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {
        "db_ok": False,
        "ingest_fresh": False,
        "static_bundle_ok": os.path.exists(os.path.join(STATIC_DIR, "index.html")),
    }


if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
