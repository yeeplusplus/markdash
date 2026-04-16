CREATE TABLE IF NOT EXISTS events (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  category      TEXT,
  start_date    TIMESTAMPTZ,
  end_date      TIMESTAMPTZ,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS markets (
  id            TEXT PRIMARY KEY,
  event_id      TEXT REFERENCES events(id),
  side_label    TEXT,
  question      TEXT NOT NULL,
  slug          TEXT,
  category      TEXT,
  end_date      TIMESTAMPTZ,
  outcomes      JSONB NOT NULL,
  volume        NUMERIC,
  liquidity     NUMERIC,
  active        BOOLEAN,
  closed        BOOLEAN,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_markets_event ON markets (event_id);

CREATE TABLE IF NOT EXISTS market_snapshots (
  id         BIGSERIAL PRIMARY KEY,
  market_id  TEXT NOT NULL REFERENCES markets(id),
  ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_ts  TIMESTAMPTZ,
  yes_price  NUMERIC,
  prices     JSONB NOT NULL,
  volume     NUMERIC,
  liquidity  NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_snapshots_market_ts ON market_snapshots (market_id, ts DESC);

CREATE TABLE IF NOT EXISTS ai_insights (
  id            BIGSERIAL PRIMARY KEY,
  kind          TEXT NOT NULL,
  event_id      TEXT REFERENCES events(id),
  window_start  TIMESTAMPTZ NOT NULL,
  window_end    TIMESTAMPTZ NOT NULL,
  window_bucket TIMESTAMPTZ NOT NULL,
  stddev        NUMERIC,
  arb_gap       NUMERIC,
  narrative     TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_insights_kind_created ON ai_insights (kind, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_insights_kind_event_bucket
  ON ai_insights (kind, event_id, window_bucket);
