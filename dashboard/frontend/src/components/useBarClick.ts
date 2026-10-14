import { useEffect, useRef } from 'react';
import type { Datum } from '../theme';

type ChartEvents = { addEventListener: (name: string, fn: (event: Event) => void) => void; removeEventListener: (name: string, fn: (event: Event) => void) => void };

/** Ref for a Carbon bar chart that calls `handler` with the clicked bar's datum. */
export function useBarClick(handler: (datum: Datum) => void) {
  const ref = useRef<{ chart?: { services?: { events?: ChartEvents } } } | null>(null);
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  useEffect(() => {
    const events = ref.current?.chart?.services?.events;
    if (!events) return undefined;
    const listener = (event: Event) => {
      const datum = (event as CustomEvent<{ datum?: Datum }>).detail?.datum;
      if (datum) handlerRef.current(datum);
    };
    events.addEventListener('bar-click', listener);
    return () => events.removeEventListener('bar-click', listener);
  });
  return ref;
}

/** Open the Audit log for one bucket (a day, or the week or month starting that day). */
export function openBucket(day: string | undefined, granularity: string, extra: Record<string, string> = {}) {
  if (!day) return;
  const start = new Date(`${day}T12:00:00`);
  const end = new Date(start);
  if (granularity === 'week') end.setDate(end.getDate() + 6);
  if (granularity === 'month') { end.setMonth(end.getMonth() + 1); end.setDate(0); }
  const iso = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const params = new URLSearchParams({ since: day, until: iso(end), ...extra });
  window.location.hash = `/audit?${params}`;
}
