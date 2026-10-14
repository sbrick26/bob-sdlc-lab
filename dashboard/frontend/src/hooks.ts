import { useCallback, useEffect, useState } from 'react';
import { RATE_KEY, readNumber, writeNumber } from './format';

export function useApi<T>(loader: () => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loader());
    } catch (value) {
      setError(value instanceof Error ? value : new Error('Request failed'));
    } finally {
      setLoading(false);
    }
  }, dependencies); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void reload(); }, [reload]);
  return { data, setData, error, loading, reload };
}

/** USD per Bobcoin: a value saved in this browser wins, else the server rate. */
export function useUsdRate(serverRate: number | null | undefined) {
  const [saved, setSaved] = useState<number | null>(() => readNumber(RATE_KEY, null));
  const update = useCallback((value: number | null) => { setSaved(value); writeNumber(RATE_KEY, value); }, []);
  return { rate: saved ?? serverRate ?? null, saved, fromBrowser: saved != null, setRate: update };
}
