'use client';

import { useEffect, useState } from 'react';
import { Insight, listInsights } from '../../lib/api';

export default function InsightsPanel() {
  const [items, setItems] = useState<Insight[]>([]);
  const [stale, setStale] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [vol, coh] = await Promise.all([
          listInsights('volatility', 5),
          listInsights('coherence', 5),
        ]);
        if (!alive) return;
        const merged = [...vol.items, ...coh.items].sort((a, b) =>
          a.created_at < b.created_at ? 1 : -1,
        );
        setItems(merged.slice(0, 6));
        setStale(vol.stale && coh.stale);
      } catch (e) {
        if (alive) setError((e as Error).message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="mb-6 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-600">
          AI insights — event coherence & volatility
        </h2>
        {stale && !loading && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            stale (&gt;20 min)
          </span>
        )}
      </div>
      {loading && <p className="text-sm text-neutral-500">loading…</p>}
      {error && <p className="text-sm text-red-600">error: {error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-neutral-500">
          No insights yet — the AI narrator publishes a new round every ~15 minutes.
        </p>
      )}
      <ul className="space-y-2">
        {items.map((i) => (
          <li key={i.id} className="rounded-md border border-neutral-100 bg-neutral-50 p-3">
            <div className="mb-1 flex items-center gap-2 text-xs text-neutral-500">
              <span
                className={`rounded px-1.5 py-0.5 font-medium uppercase ${
                  i.kind === 'volatility'
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-purple-100 text-purple-800'
                }`}
              >
                {i.kind}
              </span>
              {i.event_title && <span className="truncate">{i.event_title}</span>}
              <span className="ml-auto">{new Date(i.created_at).toLocaleTimeString()}</span>
            </div>
            <p className="text-sm text-neutral-800">{i.narrative}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
