import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { freshIds, presetRange, type Preset } from './format';
import { throttle } from './throttle';

// ---------------------------------------------------------------- global filters

export interface Filters { preset: Preset; since: string; until: string; team: string }
interface FiltersValue { filters: Filters; setPreset: (preset: Preset) => void; setCustom: (since: string, until: string) => void; setTeam: (team: string) => void }

const FILTERS_KEY = 'governance.filters';
const FiltersContext = createContext<FiltersValue | null>(null);

function loadFilters(): Filters {
  let saved: Partial<Filters> = {};
  try { saved = JSON.parse(localStorage.getItem(FILTERS_KEY) || '{}') as Partial<Filters>; } catch { saved = {}; }
  const preset = (saved.preset as Preset) || '7d';
  const range = presetRange(preset, new Date(), { since: saved.since || '', until: saved.until || '' });
  return { preset, ...range, team: saved.team || '' };
}

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<Filters>(loadFilters);
  useEffect(() => { try { localStorage.setItem(FILTERS_KEY, JSON.stringify(filters)); } catch { /* storage blocked */ } }, [filters]);
  const setPreset = useCallback((preset: Preset) => setFilters((current) => ({ ...current, preset, ...presetRange(preset, new Date(), current) })), []);
  const setCustom = useCallback((since: string, until: string) => setFilters((current) => ({ ...current, preset: 'custom', ...presetRange('custom', new Date(), { since, until }) })), []);
  const setTeam = useCallback((team: string) => setFilters((current) => ({ ...current, team })), []);
  const value = useMemo(() => ({ filters, setPreset, setCustom, setTeam }), [filters, setPreset, setCustom, setTeam]);
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersValue {
  const value = useContext(FiltersContext);
  if (!value) throw new Error('FiltersProvider missing');
  return value;
}

/** Query parameters every summary and the audit log take. */
export function filterParams(filters: Filters): URLSearchParams {
  const params = new URLSearchParams({ since: filters.since, until: filters.until, tz_offset: String(new Date().getTimezoneOffset()) });
  if (filters.team) params.set('team', filters.team);
  return params;
}

// ---------------------------------------------------------------- live updates

type LiveStatus = 'live' | 'paused' | 'offline';
interface LiveValue { version: number; status: LiveStatus; toggle: () => void }
const LiveContext = createContext<LiveValue>({ version: 0, status: 'offline', toggle: () => undefined });

/**
 * One EventSource for the app. Each event bumps `version` at most once every
 * 3 s, which makes the current page refetch. If the stream fails, poll every 10 s.
 */
export function LiveProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const [paused, setPaused] = useState(false);
  const [connected, setConnected] = useState(false);
  const bump = useRef(throttle(() => setVersion((value) => value + 1), 3000));
  useEffect(() => {
    if (paused) return undefined;
    let poll: ReturnType<typeof setInterval> | null = null;
    let source: EventSource | null = null;
    const startPolling = () => { if (!poll) poll = setInterval(() => bump.current(), 10_000); };
    try {
      source = new EventSource('/api/v1/stream');
      source.onopen = () => { setConnected(true); if (poll) { clearInterval(poll); poll = null; } };
      source.onmessage = () => bump.current();
      source.onerror = () => { setConnected(false); startPolling(); };
    } catch {
      startPolling();
    }
    return () => { source?.close(); if (poll) clearInterval(poll); bump.current.cancel(); setConnected(false); };
  }, [paused]);
  const value = useMemo<LiveValue>(() => ({
    version, status: paused ? 'paused' : connected ? 'live' : 'offline', toggle: () => setPaused((value) => !value),
  }), [version, paused, connected]);
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveValue {
  return useContext(LiveContext);
}

/**
 * Rows to highlight: ids that arrive through a live-stream refetch after the
 * first load of the current view (`viewKey` changes reset the baseline).
 */
export function useNewIds(ids: string[], viewKey: string): Set<string> {
  const { version } = useLive();
  const seen = useRef<{ key: string; version: number; ids: Set<string> } | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const idsKey = ids.join('|');
  useEffect(() => {
    const previous = seen.current;
    const viewChanged = !previous || previous.key !== viewKey;
    const fromStream = !!previous && previous.version !== version;
    const added = freshIds(previous?.ids ?? null, ids, viewChanged, fromStream);
    seen.current = { key: viewKey, version, ids: new Set([...(viewChanged ? [] : previous?.ids ?? []), ...ids]) };
    setFresh(added);
    if (!added.size) return undefined;
    const timer = setTimeout(() => setFresh(new Set()), 2500);
    return () => clearTimeout(timer);
  }, [idsKey, viewKey]); // eslint-disable-line react-hooks/exhaustive-deps
  return fresh;
}
