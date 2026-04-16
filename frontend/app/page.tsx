'use client';

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import InsightsPanel from './components/InsightsPanel';
import {
  fmtDate,
  fmtMoney,
  fmtPct,
  listMarkets,
  Market,
} from '../lib/api';

type SortKey = 'volume_desc' | 'liquidity_desc' | 'end_date_asc';

const PAGE_SIZE = 50;

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function HomePage() {
  const [q, setQ] = useState('');
  const [sort, setSort] = useState<SortKey>('volume_desc');
  const [activeOnly, setActiveOnly] = useState(true);
  const [items, setItems] = useState<Market[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debouncedQ = useDebounced(q);
  const reqId = useRef(0);

  useEffect(() => {
    setCursor(null);
    setCursorStack([]);
  }, [debouncedQ, sort, activeOnly]);

  useEffect(() => {
    const myReq = ++reqId.current;
    setLoading(true);
    setError(null);
    listMarkets({
      q: debouncedQ || undefined,
      active: activeOnly ? true : undefined,
      sort,
      cursor: cursor ?? undefined,
      limit: PAGE_SIZE,
    })
      .then((res) => {
        if (myReq !== reqId.current) return;
        setItems(res.items);
        setNextCursor(res.next_cursor);
      })
      .catch((e: Error) => {
        if (myReq !== reqId.current) return;
        setError(e.message);
      })
      .finally(() => {
        if (myReq !== reqId.current) return;
        setLoading(false);
      });
  }, [debouncedQ, sort, activeOnly, cursor]);

  const columns = useMemo<ColumnDef<Market>[]>(
    () => [
      {
        header: 'Market',
        accessorKey: 'question',
        cell: (info) => {
          const m = info.row.original;
          return (
            <Link
              href={`/market?id=${encodeURIComponent(m.id)}`}
              className="font-medium text-blue-700 hover:underline"
            >
              {m.question}
            </Link>
          );
        },
      },
      {
        header: 'Side',
        accessorKey: 'side_label',
        cell: (info) => (
          <span className="text-sm text-neutral-600">
            {info.getValue<string | null>() ?? '—'}
          </span>
        ),
      },
      {
        header: 'Yes',
        accessorKey: 'yes_price',
        cell: (info) => (
          <span className="font-mono text-sm">
            {fmtPct(info.getValue<number | null>())}
          </span>
        ),
      },
      {
        header: 'Volume',
        accessorKey: 'volume',
        cell: (info) => (
          <span className="font-mono text-sm">
            {fmtMoney(info.getValue<number | null>())}
          </span>
        ),
      },
      {
        header: 'Liquidity',
        accessorKey: 'liquidity',
        cell: (info) => (
          <span className="font-mono text-sm">
            {fmtMoney(info.getValue<number | null>())}
          </span>
        ),
      },
      {
        header: 'Ends',
        accessorKey: 'end_date',
        cell: (info) => (
          <span className="text-sm text-neutral-600">
            {fmtDate(info.getValue<string | null>())}
          </span>
        ),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const page = cursorStack.length + 1;
  const canPrev = cursorStack.length > 0;
  const canNext = nextCursor !== null;

  function goNext() {
    if (!canNext) return;
    setCursorStack([...cursorStack, cursor]);
    setCursor(nextCursor);
  }

  function goPrev() {
    if (!canPrev) return;
    const prev = cursorStack[cursorStack.length - 1];
    setCursorStack(cursorStack.slice(0, -1));
    setCursor(prev);
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Markdash</h1>
          <p className="text-sm text-neutral-600">Live Polymarket intelligence</p>
        </div>
      </header>

      <InsightsPanel />

      <section className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search markets…"
          className="w-72 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none"
        />
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm shadow-sm"
        >
          <option value="volume_desc">Volume ↓</option>
          <option value="liquidity_desc">Liquidity ↓</option>
          <option value="end_date_asc">Ends soon ↑</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => setActiveOnly(e.target.checked)}
          />
          Active only
        </label>
        {loading && <span className="text-xs text-neutral-500">loading…</span>}
        {error && <span className="text-xs text-red-600">error: {error}</span>}
      </section>

      <section className="overflow-x-auto rounded-lg border border-neutral-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-neutral-200">
          <thead className="bg-neutral-50">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-neutral-600"
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-neutral-50">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-2 align-top">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-6 text-center text-sm text-neutral-500">
                  No markets match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <nav className="mt-4 flex items-center justify-between">
        <span className="text-xs text-neutral-500">Page {page}</span>
        <div className="flex gap-2">
          <button
            onClick={goPrev}
            disabled={!canPrev}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40"
          >
            ← Prev
          </button>
          <button
            onClick={goNext}
            disabled={!canNext}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      </nav>
    </main>
  );
}
