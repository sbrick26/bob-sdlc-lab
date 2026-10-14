import type { ReactNode } from 'react';
import { EmptyState } from './States';

/** A chart card titled with the question it answers, with an empty state. */
export function ChartPanel({ question, eyebrow, note, empty, emptyDetail, wide, children }: {
  question: string; eyebrow: string; note?: ReactNode; empty: boolean; emptyDetail?: string; wide?: boolean; children: ReactNode;
}) {
  return (
    <article className={`panel chart-panel${wide ? ' panel--wide' : ''}`}>
      <div className="panel__header"><div><p className="eyebrow">{eyebrow}</p><h2>{question}</h2></div></div>
      {empty ? <EmptyState title="No data yet" detail={emptyDetail || 'This chart fills in when Bob sends events.'} /> : <div className="chart-body">{children}</div>}
      {note && !empty && <p className="chart-note">{note}</p>}
    </article>
  );
}
