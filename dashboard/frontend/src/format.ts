// Pure formatting and ROI helpers. No React here, so node --test can import it.

type Num = number | null | undefined;

const finite = (value: Num): value is number => typeof value === 'number' && Number.isFinite(value);

/** Whole counts with thousands separators. Empty for missing values. */
export function count(value: Num): string {
  return finite(value) ? Math.round(value).toLocaleString('en-US') : '—';
}

/** Bobcoins: two decimals and the BC suffix, e.g. "3.87 BC". */
export function bobcoins(value: Num): string {
  return finite(value) ? `${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} BC` : '—';
}

/** USD: leading $ and two decimals, e.g. "$1.94". */
export function usd(value: Num): string {
  return finite(value) ? `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';
}

/** Round half up to cents, matching the server (3.87 BC at 0.50 is $1.94). */
export function toUsd(coins: Num, rate: Num): number | null {
  if (!finite(coins) || !finite(rate) || rate <= 0) return null;
  return Math.round((coins * rate + Number.EPSILON) * 100) / 100;
}

export function minutes(value: Num): string {
  if (!finite(value)) return '—';
  if (value < 60) return `${Math.round(value)} min`;
  if (value >= 1440) {
    const days = Math.floor(value / 1440);
    const hours = Math.round((value - days * 1440) / 60);
    return `${days} ${days === 1 ? 'day' : 'days'}${hours ? ` ${hours} h` : ''}`;
  }
  const hours = Math.floor(value / 60);
  const rest = Math.round(value - hours * 60);
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

export function percent(value: Num): string {
  return finite(value) ? `${Math.round(value)}%` : '—';
}

export function median(values: number[]): number | null {
  const clean = values.filter(finite).sort((a, b) => a - b);
  if (!clean.length) return null;
  const middle = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[middle] : (clean[middle - 1] + clean[middle]) / 2;
}

/** Label for a bucket start ("2026-10-13"): "Oct 13", "Week of Oct 6" or "Oct 2026". Hour buckets keep the hour. */
export function bucketLabel(bucket: string, granularity: string): string {
  const date = new Date(granularity === 'hour' ? bucket : `${bucket.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return bucket;
  if (granularity === 'hour') return date.toLocaleString('en-US', { hour: 'numeric', hour12: true });
  if (granularity === 'month') return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  const day = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  return granularity === 'week' ? `Week of ${day}` : day;
}

/** Event types in plain words. The raw name stays in the drawer's technical details. */
export const EVENT_WORDS: Record<string, string> = {
  UserPromptSubmit: 'Prompt sent', PreToolUse: 'Before tool', PostToolUse: 'After tool', SessionStart: 'Session start',
  Stop: 'Turn ended', 'lab.ci_result': 'CI review', 'lab.pr_opened': 'PR opened', 'lab.approved': 'PR approved',
  'lab.merged': 'PR merged', 'lab.ticket_started': 'Ticket started', 'lab.ticket_done': 'Ticket done',
};
export const eventWords = (event: string | null | undefined) => (event ? EVENT_WORDS[event] ?? event : '—');

export const DECISION_WORDS: Record<string, string> = { allowed: 'Allowed', blocked: 'Blocked', observed: 'Flagged', error: 'Error' };

/**
 * Ids to highlight after a load. Only a refetch triggered by the live stream
 * highlights, and only ids that were not loaded before for the same view.
 */
export function freshIds(previous: Set<string> | null, current: string[], viewChanged: boolean, fromStream: boolean): Set<string> {
  if (!previous || viewChanged || !fromStream) return new Set();
  return new Set(current.filter((id) => !previous.has(id)));
}

export function shortTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export interface RoiInput {
  merged: number;
  merged_minutes_total: number;
  bobcoins_merged_total: number | null;
  ci_with_result: number;
  ci_first_try_passed: number;
}

/**
 * hours saved = merged tickets x baseline hours - actual hours (start to merge)
 * Bobcoins per merged PR = Bobcoins on merged tickets / merged tickets
 */
export function roi(input: RoiInput, baselineHours: number, rate: number | null) {
  const baseline = finite(baselineHours) && baselineHours > 0 ? baselineHours : 0;
  const actualHours = input.merged_minutes_total / 60;
  const hoursSaved = input.merged ? input.merged * baseline - actualHours : null;
  const perPr = input.merged && finite(input.bobcoins_merged_total) ? input.bobcoins_merged_total / input.merged : null;
  return {
    hoursSaved: hoursSaved == null ? null : Math.round(hoursSaved * 10) / 10,
    actualHours: Math.round(actualHours * 10) / 10,
    bobcoinsPerPr: perPr == null ? null : Math.round(perPr * 100) / 100,
    usdPerPr: toUsd(perPr, rate),
    firstTryRate: input.ci_with_result ? (input.ci_first_try_passed / input.ci_with_result) * 100 : null,
  };
}

interface StorageLike { getItem(key: string): string | null; setItem(key: string, value: string): void }

function storage(): StorageLike | null {
  try { return typeof localStorage === 'undefined' ? null : localStorage; } catch { return null; }
}

/** A positive number from browser storage, or the fallback. Never throws. */
export function readNumber(key: string, fallback: number | null, store: StorageLike | null = storage()): number | null {
  try {
    const raw = store?.getItem(key);
    if (raw == null || raw.trim() === '') return fallback;
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? value : fallback;
  } catch {
    return fallback;
  }
}

export function writeNumber(key: string, value: number | null, store: StorageLike | null = storage()): void {
  try { store?.setItem(key, value == null ? '' : String(value)); } catch { /* storage blocked: keep in memory only */ }
}

export const BASELINE_KEY = 'governance.baselineHoursPerTicket';
export const RATE_KEY = 'governance.usdPerBobcoin';

/** Seconds as "4.5 s", "8.5 min" or "1.2 h". */
export function seconds(value: Num): string {
  if (!finite(value)) return '—';
  if (value < 60) return `${value.toFixed(1)} s`;
  if (value < 3600) return `${(value / 60).toFixed(1)} min`;
  return `${(value / 3600).toFixed(1)} h`;
}

export function millis(value: Num): string {
  return finite(value) ? `${value < 10 ? value.toFixed(2) : Math.round(value)} ms` : '—';
}

export type Preset = 'today' | '7d' | '30d' | 'month' | 'custom';
export const PRESETS: Array<{ id: Preset; label: string }> = [
  { id: 'today', label: 'Today' },
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
  { id: 'month', label: 'This month' },
  { id: 'custom', label: 'Custom range' },
];

/** Local calendar date as YYYY-MM-DD. */
export function isoDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Inclusive local date range for a preset. Custom keeps the given range. */
export function presetRange(preset: Preset, today: Date, custom?: { since: string; until: string }): { since: string; until: string } {
  const day = (offset: number) => isoDay(new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset));
  switch (preset) {
    case 'today': return { since: day(0), until: day(0) };
    case '30d': return { since: day(29), until: day(0) };
    case 'month': return { since: isoDay(new Date(today.getFullYear(), today.getMonth(), 1)), until: day(0) };
    case 'custom': return custom && custom.since && custom.until && custom.since <= custom.until ? custom : { since: day(6), until: day(0) };
    default: return { since: day(6), until: day(0) };
  }
}

/** Number of days in an inclusive range. */
export function rangeDays(since: string, until: string): number {
  const start = new Date(`${since}T12:00:00`).getTime();
  const end = new Date(`${until}T12:00:00`).getTime();
  return Number.isFinite(start) && Number.isFinite(end) ? Math.round((end - start) / 86_400_000) + 1 : 0;
}

export type Better = 'up' | 'down' | null;

/** "+12% vs prior 7 days" and its tone. Tone is set only when the direction has a clear meaning. */
export function deltaText(pct: Num, days: number | null | undefined, better: Better): { text: string; tone: 'good' | 'bad' | 'neutral' } | null {
  if (!finite(pct)) return null;
  const sign = pct > 0 ? '+' : pct < 0 ? '−' : '±';
  const period = days === 1 ? 'prior day' : `prior ${days ?? ''} days`.replace('  ', ' ');
  const text = `${sign}${Math.abs(Math.round(pct))}% vs ${period}`;
  if (!better || pct === 0) return { text, tone: 'neutral' };
  const good = better === 'up' ? pct > 0 : pct < 0;
  return { text, tone: good ? 'good' : 'bad' };
}

const TOOL_WORDS: Record<string, string> = {
  write_file: 'Write file', execute_command: 'Run command', read_file: 'Read file', apply_diff: 'Edit file',
  insert_content: 'Insert into file', search_and_replace: 'Search and replace',
};
export const toolWords = (tool: string | null | undefined) => (tool ? TOOL_WORDS[tool] ?? tool.replace(/_/g, ' ') : '—');

const CHIP_LABELS: Record<string, string> = {
  user: 'User', ticket: 'Ticket', event: 'Event type', decision: 'Decision', session: 'Session', tool: 'Tool',
  outcome: 'Outcome', rule: 'Rule', team: 'Team',
};

/** Removable chips for the drill-down filters in a page URL ("Tool: Run command ×"). */
export function filterChips(params: URLSearchParams): Array<{ key: string; label: string }> {
  const chips: Array<{ key: string; label: string }> = [];
  for (const key of Object.keys(CHIP_LABELS)) {
    const value = params.get(key);
    if (!value) continue;
    const shown = key === 'tool' ? toolWords(value) : key === 'event' ? eventWords(value)
      : key === 'decision' ? DECISION_WORDS[value] ?? value : key === 'session' ? value.slice(0, 8) : value;
    chips.push({ key, label: `${CHIP_LABELS[key]}: ${shown}` });
  }
  return chips;
}

/** A hash link with drill-down filters, dropping empty values. */
export function drillHref(page: string, filters: Record<string, string | null | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
  const query = params.toString();
  return `#/${page}${query ? `?${query}` : ''}`;
}
