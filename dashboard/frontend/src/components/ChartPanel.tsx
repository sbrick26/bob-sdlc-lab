import type { ReactNode } from 'react';
import { EmptyState } from './States';

/** A chart card with a short title, an optional "View all" link and footnote, and an empty state. */
export function ChartPanel({ title, empty, emptyDetail, viewAll, foot, children }: {
  title: string; empty: boolean; emptyDetail?: string; viewAll?: { href: string; label?: string } | null; foot?: ReactNode; children: ReactNode;
}) {
  return (
    <article className="panel chart-panel">
      <div className="panel__header"><h2>{title}</h2>{viewAll && <a className="chart-panel__link" href={viewAll.href}>{viewAll.label ?? 'View all'}</a>}</div>
      {empty ? <EmptyState title="No data yet" detail={emptyDetail || 'This chart fills in when Bob sends events.'} /> : <div className="chart-body">{children}</div>}
      {foot && !empty && <p className="chart-foot">{foot}</p>}
    </article>
  );
}
