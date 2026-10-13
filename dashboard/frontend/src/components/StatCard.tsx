import type { ReactNode } from 'react';

export function StatCard({ label, value, detail, signal, footer }: { label: string; value: string | number; detail: string; signal?: 'neutral' | 'positive' | 'negative'; footer?: ReactNode }) {
  return (
    <section className={`stat-card stat-card--${signal ?? 'neutral'}`}>
      <p className="stat-card__label">{label}</p>
      <p className="stat-card__value">{value}</p>
      <p className="stat-card__detail">{detail}</p>
      {footer && <div className="stat-card__footer">{footer}</div>}
    </section>
  );
}
