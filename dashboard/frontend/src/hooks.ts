import { useCallback, useEffect, useRef, useState } from 'react';
import { filterParams, useFilters, useLive } from './context';

/** Load data; reloads when dependencies change. A reload keeps the previous data on screen. */
export function useApi<T>(loader: () => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await loaderRef.current());
      setError(null);
    } catch (value) {
      setError(value instanceof Error ? value : new Error('Request failed'));
    } finally {
      setLoading(false);
    }
  }, dependencies); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void reload(); }, [reload]);
  return { data, setData, error, loading, reload };
}

/** A page summary scoped by the global date range and team, refreshed by live events. */
export function useSummary<T>(load: (params: URLSearchParams) => Promise<T>) {
  const { filters } = useFilters();
  const { version } = useLive();
  return useApi(() => load(filterParams(filters)), [filters, version]);
}

/** USD per Bobcoin comes only from the server (BOBCOIN_USD_RATE), so every viewer sees the same figures. */
export function useUsdRate(serverRate: number | null | undefined) {
  return { rate: serverRate ?? null, fromBrowser: false };
}
