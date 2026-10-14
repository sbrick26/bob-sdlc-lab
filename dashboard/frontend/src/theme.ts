import { useEffect, useState } from 'react';

// Reference categorical palette, fixed order, validated for adjacent pairs in
// light (surface #ffffff) and dark (surface #262626). Slots 3 to 5 sit under
// 3:1 on light, so every chart ships a legend and the data-table view.
const LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
const DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
const OTHER = { light: '#a8a8a8', dark: '#6f6f6f' };

export function useDarkMode(): boolean {
  const query = '(prefers-color-scheme: dark)';
  const [dark, setDark] = useState(() => typeof window !== 'undefined' && window.matchMedia?.(query).matches);
  useEffect(() => {
    const media = window.matchMedia?.(query);
    if (!media) return undefined;
    const listener = (event: MediaQueryListEvent) => setDark(event.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, []);
  return dark;
}

export function slot(index: number, dark: boolean): string {
  const palette = dark ? DARK : LIGHT;
  return palette[index] ?? (dark ? OTHER.dark : OTHER.light);
}

/** Color follows the entity: the index in a stable, sorted list, never rank. */
export function colorScale(names: string[], dark: boolean, muted: string[] = []): Record<string, string> {
  return {
    ...Object.fromEntries(names.map((name, index) => [name, slot(index, dark)])),
    ...Object.fromEntries(muted.map((name) => [name, dark ? OTHER.dark : OTHER.light])),
  };
}

/** Shared Carbon chart options: no animation, legend, table view in the toolbar. */
export function baseOptions(dark: boolean, height = '300px'): Record<string, unknown> {
  return {
    height,
    theme: dark ? 'g100' : 'g10',
    animations: false,
    legend: { alignment: 'left', truncation: { type: 'end_line', threshold: 32, numCharacter: 32 } },
    toolbar: { enabled: true, numberOfIcons: 1, controls: [{ type: 'Show as data-table' }] },
    grid: { x: { enabled: false } },
    bars: { maxWidth: 28 },
  };
}

/** Whole-number ticks for count axes with small maxima (no 0.2, 0.4 ...). */
export function countTicks(max: number): Record<string, unknown> {
  if (!Number.isFinite(max) || max <= 0 || max > 10) return {};
  return { ticks: { values: Array.from({ length: Math.ceil(max) + 1 }, (_, index) => index) }, domain: [0, Math.ceil(max)] };
}

export const LABEL_AXIS = { scaleType: 'labels', truncation: { type: 'end_line', threshold: 40, numCharacter: 40 } };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Datum = { group: string; key?: string; date?: Date; value: number | null; [field: string]: any };

const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] as string));

export interface TipRow { label: string; value: string; sub?: string; color?: string }
export interface TipSpec { title: string; rows: TipRow[]; total?: TipRow; footer?: TipRow }

/** "Fri, Oct 11" for a local YYYY-MM-DD day. */
export function dayTitle(day: string | undefined): string {
  if (!day) return '';
  const date = new Date(`${day}T12:00:00`);
  return Number.isNaN(date.getTime()) ? day : date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function row(item: TipRow, extra = ''): string {
  const dot = item.color ? `<span class="viz-tip__dot" style="background:${escapeHtml(item.color)}"></span>` : '';
  const sub = item.sub ? `<span class="viz-tip__sub">${escapeHtml(item.sub)}</span>` : '';
  return `<div class="viz-tip__row${extra}">${dot}<span class="viz-tip__label">${escapeHtml(item.label)}</span><span class="viz-tip__value">${escapeHtml(item.value)}${sub}</span></div>`;
}

export function tipCard(spec: TipSpec): string {
  return `<div class="viz-tip"><div class="viz-tip__title">${escapeHtml(spec.title)}</div>${spec.rows.map((item) => row(item)).join('')}${spec.total ? row(spec.total, ' viz-tip__row--total') : ''}${spec.footer ? row(spec.footer, ' viz-tip__row--footer') : ''}</div>`;
}

/**
 * Structured tooltip card: bold title, one row per value with the series dot,
 * label left and value right. `colors` maps a series name to its color.
 */
export function tip(colors: Record<string, string>, build: (data: Datum[]) => TipSpec): Record<string, unknown> {
  return {
    tooltip: {
      truncation: { type: 'none' },
      customHTML: (data: Datum[] | Datum) => {
        const items = Array.isArray(data) ? data : [data];
        const spec = build(items);
        spec.rows = spec.rows.map((item) => ({ color: colors[item.label], ...item }));
        return tipCard(spec);
      },
    },
  };
}

/** Single series: title from the datum, one row. */
export function simpleTip(colors: Record<string, string>, label: string, value: (datum: Datum) => string, title: (datum: Datum) => string = (datum) => String(datum.key ?? '')) {
  return tip(colors, (data) => ({ title: title(data[0]), rows: data.map((datum) => ({ label: datum.group || label, value: value(datum) })) }));
}

export const plural = (value: number | null | undefined, one: string, many: string) => `${value ?? 0} ${value === 1 ? one : many}`;

/** Severity colors for rule bars: high = red tone, medium = orange, low and info = grey. */
export function severityColor(severity: string | null | undefined, dark: boolean): string {
  if (severity === 'critical' || severity === 'high') return dark ? '#fa4d56' : '#da1e28';
  if (severity === 'medium') return dark ? '#ff832b' : '#eb6834';
  return dark ? '#8d8d8d' : '#a8a8a8';
}

/** Neutral bar color, with the top bar emphasized in the accent. */
export function neutral(index: number, dark: boolean): string {
  return index === 0 ? slot(0, dark) : dark ? '#6f6f6f' : '#a8a8a8';
}

/** Team colors follow the sorted list of all teams, so a team keeps its color on every page; "Other" is grey. */
export function teamColors(teams: string[], dark: boolean): Record<string, string> {
  return colorScale([...teams].filter((team) => team !== 'Other').sort(), dark, ['Other']);
}
