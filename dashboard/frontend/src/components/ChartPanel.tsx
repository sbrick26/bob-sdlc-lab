import type { ReactNode } from 'react';
import { EmptyState } from './States';

/** A chart card with a short title and an empty state. */
export function ChartPanel({ title, empty, emptyDetail, children }: { title: string; empty: boolean; emptyDetail?: string; children: ReactNode }) {
  return (
    <article className="panel chart-panel">
      <div className="panel__header"><h2>{title}</h2></div>
      {empty ? <EmptyState title="No data yet" detail={emptyDetail || 'This chart fills in when Bob sends events.'} /> : <div className="chart-body">{children}</div>}
    </article>
  );
}
