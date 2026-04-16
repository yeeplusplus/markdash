'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  fmtDate,
  fmtMoney,
  fmtPct,
  fmtTime,
  getEvent,
  getHistory,
  getMarket,
  History,
  Market,
  MarketDetail,
} from '../../lib/api';

type WindowOpt = '1h' | '6h' | '24h' | '7d';

function MarketInner() {
  const params = useSearchParams();
  const id = params.get('id');

  const [detail, setDetail] = useState<MarketDetail | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [window, setWindowOpt] = useState<WindowOpt>('24h');
  const [sumYes, setSumYes] = useState<number | null>(null);
  const [arbGap, setArbGap] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    setLoading(true);
    setError(null);
    getMarket(id)
      .then(async (m) => {
        if (!alive) return;
        setDetail(m);
        if (m.event_id) {
          try {
            const ev = await getEvent(m.event_id);
            if (!alive) return;
            setSumYes(ev.sum_yes);
            setArbGap(ev.arb_gap);
          } catch {
            /* non-fatal */
          }
        }
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [id]);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    getHistory(id, window)
      .then((h) => {
        if (alive) setHistory(h);
      })
      .catch(() => {
        /* keep prior */
      });
    return () => {
      alive = false;
    };
  }, [id, window]);

  if (!id) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <p className="text-sm text-red-600">Missing market id.</p>
      </main>
    );
  }

  if (loading && !detail) {
    return <main className="mx-auto max-w-5xl px-6 py-10">loading…</main>;
  }

  if (error || !detail) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <p className="text-sm text-red-600">error: {error ?? 'not found'}</p>
        <Link href="/" className="text-sm text-blue-700 hover:underline">
          ← back
        </Link>
      </main>
    );
  }

  const chartData = (history?.points ?? []).map((p) => ({
    ts: p.ts,
    label: fmtTime(p.ts),
    yes: p.yes_price,
  }));

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <Link href="/" className="text-sm text-blue-700 hover:underline">
        ← markets
      </Link>

      <header className="mt-3 mb-6">
        <h1 className="text-2xl font-semibold">{detail.question}</h1>
        {detail.event && (
          <p className="mt-1 text-sm text-neutral-600">
            Event: <span className="font-medium">{detail.event.title}</span>
            {detail.side_label && (
              <span className="ml-2 rounded bg-neutral-200 px-2 py-0.5 text-xs font-medium text-neutral-700">
                side: {detail.side_label}
              </span>
            )}
          </p>
        )}
      </header>

      <section className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Yes price" value={fmtPct(detail.yes_price)} />
        <Stat label="Volume" value={fmtMoney(detail.volume)} />
        <Stat label="Liquidity" value={fmtMoney(detail.liquidity)} />
        <Stat label="Ends" value={fmtDate(detail.end_date)} />
      </section>

      <section className="mb-6 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-600">
            Yes price history
          </h2>
          <div className="flex gap-1">
            {(['1h', '6h', '24h', '7d'] as WindowOpt[]).map((w) => (
              <button
                key={w}
                onClick={() => setWindowOpt(w)}
                className={`rounded px-2 py-1 text-xs font-medium ${
                  window === w
                    ? 'bg-blue-600 text-white'
                    : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'
                }`}
              >
                {w}
              </button>
            ))}
          </div>
        </div>
        <div className="h-64">
          {chartData.length === 0 ? (
            <p className="pt-10 text-center text-sm text-neutral-500">
              No snapshots in this window yet.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={24} />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  formatter={(v: number) => fmtPct(v)}
                  labelFormatter={(l) => `@ ${l}`}
                />
                <Line
                  type="monotone"
                  dataKey="yes"
                  stroke="#2563eb"
                  dot={false}
                  strokeWidth={2}
                  isAnimationActive={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      {detail.siblings.length > 0 && (
        <section className="mb-6 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-600">
              Paired markets in this event
            </h2>
            {sumYes !== null && (
              <span className="text-xs text-neutral-600">
                Σ Yes ={' '}
                <span className="font-mono font-semibold">{fmtPct(sumYes)}</span>
                {arbGap !== null && (
                  <span
                    className={`ml-2 rounded px-1.5 py-0.5 font-mono ${
                      Math.abs(arbGap) > 0.05
                        ? 'bg-red-100 text-red-800'
                        : 'bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    Δ {(arbGap * 100).toFixed(1)}%
                  </span>
                )}
              </span>
            )}
          </div>
          <ul className="divide-y divide-neutral-100">
            {detail.siblings.map((s: Market) => (
              <li key={s.id} className="flex items-center justify-between py-2">
                <Link
                  href={`/market?id=${encodeURIComponent(s.id)}`}
                  className="text-sm text-blue-700 hover:underline"
                >
                  {s.side_label ?? s.question}
                </Link>
                <span className="font-mono text-sm">{fmtPct(s.yes_price)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-3 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold">{value}</div>
    </div>
  );
}

export default function MarketPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-5xl px-6 py-10">loading…</main>}>
      <MarketInner />
    </Suspense>
  );
}
