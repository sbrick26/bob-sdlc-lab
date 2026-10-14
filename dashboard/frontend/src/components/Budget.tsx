import { percent } from '../format';

const level = (pct: number | null) => (pct == null ? 'under' : pct >= 100 ? 'over' : pct >= 80 ? 'near' : 'under');
const fraction = (spent: number | null, budget: number | null) => `${(spent ?? 0).toFixed(2)} / ${budget == null ? '—' : budget.toFixed(0)} BC`;

/** "64.10 / 200 BC", "32% used" and a thin bar: warning at 80%, red at 100%. */
export function BudgetTile({ spent, budget, pct }: { spent: number | null; budget: number | null; pct: number | null }) {
  return (
    <section className="stat-card">
      <p className="stat-card__label">Budget used (this month)</p>
      <p className="stat-card__value">{budget ? fraction(spent, budget) : '—'}</p>
      {budget ? (
        <>
          <p className="stat-card__detail">{percent(pct)} used</p>
          <span className={`budget-bar budget-bar--${level(pct)} budget-bar--tile`}><span className="budget-bar__track"><span className="budget-bar__fill" style={{ width: `${Math.min(pct ?? 0, 100)}%` }} /></span></span>
        </>
      ) : <p className="stat-card__detail">No budget set</p>}
    </section>
  );
}

/** Table cell: "46.22 / 100 BC", a small bar, and the percent. */
export function BudgetCell({ spent, budget, pct }: { spent: number | null; budget: number | null; pct: number | null }) {
  if (!budget) return <>—</>;
  return (
    <span className={`budget-bar budget-bar--${level(pct)}`}>
      <span className="budget-bar__value">{fraction(spent, budget)}</span>
      <span className="budget-bar__track"><span className="budget-bar__fill" style={{ width: `${Math.min(pct ?? 0, 100)}%` }} /></span>
      <span className="budget-bar__pct">{percent(pct)}</span>
    </span>
  );
}
