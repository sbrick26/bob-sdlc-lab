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
export function colorScale(names: string[], dark: boolean): Record<string, string> {
  return Object.fromEntries(names.map((name, index) => [name, slot(index, dark)]));
}

/** Shared Carbon chart options: no animation, legend, table view in the toolbar. */
export function baseOptions(dark: boolean, height = '300px'): Record<string, unknown> {
  return {
    height,
    theme: dark ? 'g100' : 'g10',
    animations: false,
    legend: { alignment: 'left' },
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
