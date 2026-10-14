import { useState, type MouseEvent } from 'react';
import { EmptyState } from './States';
import type { TipSpec } from '../theme';

export interface HBar { label: string; value: number; display: string; color: string; tip?: TipSpec; href?: string }
export interface Marker { value: number; label: string; tone: 'neutral' | 'warning' | 'danger' }

/** Tooltip card at a screen point, 12 px right of the pointer, flipped left near the right edge. */
export function TipCardView({ spec, x, y }: { spec: TipSpec; x: number; y: number }) {
  const flip = typeof window !== 'undefined' && x > window.innerWidth - 280;
  return (
    <div className="viz-tip viz-tip--floating" style={{ left: flip ? undefined : x + 12, right: flip ? window.innerWidth - x + 12 : undefined, top: y - 12 }} role="tooltip">
      <div className="viz-tip__title">{spec.title}</div>
      {spec.rows.map((row) => <TipRowView key={row.label} row={row} />)}
      {spec.total && <TipRowView row={spec.total} extra="viz-tip__row--total" />}
      {spec.footer && <TipRowView row={spec.footer} extra="viz-tip__row--footer" />}
    </div>
  );
}

function TipRowView({ row, extra = '' }: { row: TipSpec['rows'][number]; extra?: string }) {
  return (
    <div className={`viz-tip__row ${extra}`}>
      {row.color && <span className="viz-tip__dot" style={{ background: row.color }} />}
      <span className="viz-tip__label">{row.label}</span>
      <span className="viz-tip__value">{row.value}{row.sub && <span className="viz-tip__sub">{row.sub}</span>}</span>
    </div>
  );
}

/**
 * Horizontal bars as plain HTML: sorted by the caller, value at the bar end,
 * fixed 20 px bars, 32 px rows, optional marker lines (e.g. 50/80/100% of budget).
 */
export function HBarList({ items, max, markers, empty, label }: { items: HBar[]; max?: number; markers?: Marker[]; empty?: string; label: string }) {
  const [hover, setHover] = useState<{ index: number; x: number; y: number } | null>(null);
  if (!items.length) return <EmptyState title="No data yet" detail={empty ?? 'Nothing in this period.'} />;
  const top = Math.max(max ?? 0, ...items.map((item) => item.value), ...(markers ?? []).map((marker) => marker.value)) || 1;
  const move = (index: number) => (event: MouseEvent) => setHover({ index, x: event.clientX, y: event.clientY });
  return (
    <div className="hbar" role="list" aria-label={label} onMouseLeave={() => setHover(null)}>
      {items.map((item, index) => (
        <div className="hbar__row" role="listitem" key={item.label} onMouseMove={move(index)} onMouseEnter={move(index)}>
          <span className="hbar__label" title={item.label}>{item.href ? <a href={item.href}>{item.label}</a> : item.label}</span>
          <span className="hbar__track">
            <span className="hbar__fill" style={{ width: `${(item.value / top) * 100}%`, background: item.color }} />
            <span className="hbar__value" style={{ left: `calc(${(item.value / top) * 100}% + 6px)` }}>{item.display}</span>
            {markers?.map((marker) => <span key={marker.value} className={`hbar__marker hbar__marker--${marker.tone}`} style={{ left: `${(marker.value / top) * 100}%` }} />)}
          </span>
        </div>
      ))}
      {markers?.length ? (
        <div className="hbar__row hbar__row--axis" aria-hidden="true">
          <span className="hbar__label" />
          <span className="hbar__track hbar__track--axis">
            {markers.map((marker) => <span key={marker.value} className={`hbar__marker-label hbar__marker-label--${marker.tone}`} style={{ left: `${(marker.value / top) * 100}%` }}>{marker.label}</span>)}
          </span>
        </div>
      ) : null}
      {hover && items[hover.index]?.tip && <TipCardView spec={items[hover.index].tip!} x={hover.x} y={hover.y} />}
    </div>
  );
}

/** Sort high to low, ties alphabetical. */
export function sortBars<T extends { value: number; label: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}
