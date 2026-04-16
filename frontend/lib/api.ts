export type Market = {
  id: string;
  event_id: string | null;
  side_label: string | null;
  question: string;
  slug: string | null;
  category: string | null;
  end_date: string | null;
  outcomes: unknown[];
  volume: number | null;
  liquidity: number | null;
  active: boolean | null;
  closed: boolean | null;
  yes_price: number | null;
  last_snapshot_ts: string | null;
};

export type MarketList = {
  items: Market[];
  next_cursor: string | null;
};

export type EventRef = {
  id: string;
  title: string;
  category: string | null;
  start_date: string | null;
  end_date: string | null;
};

export type MarketDetail = Market & {
  event: EventRef | null;
  siblings: Market[];
};

export type Snapshot = {
  ts: string;
  source_ts: string | null;
  yes_price: number | null;
  prices: Record<string, number>;
  volume: number | null;
  liquidity: number | null;
};

export type History = {
  market_id: string;
  window: string;
  points: Snapshot[];
};

export type EventWithMarkets = EventRef & {
  markets: Market[];
  sum_yes: number | null;
  arb_gap: number | null;
};

export type Insight = {
  id: number;
  kind: string;
  event_id: string | null;
  event_title: string | null;
  window_start: string;
  window_end: string;
  window_bucket: string;
  stddev: number | null;
  arb_gap: number | null;
  narrative: string;
  created_at: string;
};

export type InsightsList = {
  items: Insight[];
  stale: boolean;
};

export type ListParams = {
  q?: string;
  category?: string;
  active?: boolean;
  sort?: 'volume_desc' | 'liquidity_desc' | 'end_date_asc';
  cursor?: string;
  limit?: number;
};

const BASE = '';

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${res.status} ${path}: ${await res.text()}`);
  return (await res.json()) as T;
}

export function listMarkets(params: ListParams = {}): Promise<MarketList> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.category) qs.set('category', params.category);
  if (params.active !== undefined) qs.set('active', String(params.active));
  if (params.sort) qs.set('sort', params.sort);
  if (params.cursor) qs.set('cursor', params.cursor);
  if (params.limit) qs.set('limit', String(params.limit));
  const s = qs.toString();
  return getJSON<MarketList>(`/api/markets${s ? `?${s}` : ''}`);
}

export function getMarket(id: string): Promise<MarketDetail> {
  return getJSON<MarketDetail>(`/api/markets/${encodeURIComponent(id)}`);
}

export function getHistory(id: string, window: '1h' | '6h' | '24h' | '7d' = '24h'): Promise<History> {
  return getJSON<History>(`/api/markets/${encodeURIComponent(id)}/history?window=${window}`);
}

export function getEvent(id: string): Promise<EventWithMarkets> {
  return getJSON<EventWithMarkets>(`/api/events/${encodeURIComponent(id)}`);
}

export function listInsights(kind: 'volatility' | 'coherence' = 'volatility', limit = 10): Promise<InsightsList> {
  return getJSON<InsightsList>(`/api/insights/volatility?kind=${kind}&limit=${limit}`);
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

export function fmtMoney(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}
