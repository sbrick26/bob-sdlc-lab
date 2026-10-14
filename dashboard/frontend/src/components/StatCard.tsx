import type { ReactNode } from 'react';
import { deltaText, type Better } from '../format';
import type { Kpi } from '../types';

export function StatCard({ label, value, detail, delta }: { label: string; value: string | number; detail?: ReactNode; delta?: { text: string; tone: string } | null }) {
  return (
    <section className="stat-card">
      <p className="stat-card__label">{label}</p>
      <p className="stat-card__value">{value}</p>
      {detail && <p className="stat-card__detail">{detail}</p>}
      {delta && <p className={`stat-card__delta stat-card__delta--${delta.tone}`}>{delta.text}</p>}
    </section>
  );
}

/** A KPI tile with its delta vs the prior period. `better` says which direction is good, or null. */
export function KpiTile({ label, kpi, format, better = null, days, detail }: {
  label: string; kpi: Kpi | undefined; format: (value: number | null) => string; better?: Better; days: number | null; detail?: ReactNode;
}) {
  return <StatCard label={label} value={format(kpi?.value ?? null)} detail={detail} delta={deltaText(kpi?.delta_pct, days, better)} />;
}
