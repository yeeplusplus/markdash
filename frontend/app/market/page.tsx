'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

function MarketInner() {
  const params = useSearchParams();
  const id = params.get('id');
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Market</h1>
      <p className="mt-2 text-sm text-neutral-600">id: {id ?? '(none)'} — detail view coming in Phase 5.</p>
    </main>
  );
}

export default function MarketPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-5xl px-6 py-10">loading…</main>}>
      <MarketInner />
    </Suspense>
  );
}
