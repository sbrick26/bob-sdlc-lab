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

/** Label for a local-time bucket from the API ("2026-10-13" or "2026-10-13T14:00:00"). */
export function bucketLabel(bucket: string, granularity: string): string {
  const date = new Date(granularity === 'hour' ? bucket : `${bucket}T12:00:00`);
  if (Number.isNaN(date.getTime())) return bucket;
  return granularity === 'hour'
    ? date.toLocaleString('en-US', { hour: 'numeric', hour12: true })
    : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
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
