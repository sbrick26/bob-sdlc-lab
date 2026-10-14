import { useFilters } from '../context';
import { BudgetCell } from './Budget';
import { bobcoins, count, minutes, percent } from '../format';
import type { TeamRow } from '../types';
import { usdText } from './Money';
import { NumberTable, type Column } from './NumberTable';
import { EmptyState } from './States';

/** One row per team; a row click filters the page to that team. */
export function TeamTable({ rows, rate }: { rows: TeamRow[] | undefined; rate: number | null }) {
  const { setTeam } = useFilters();
  const columns: Column<TeamRow>[] = [
    { key: 'team', header: 'Team', render: (row) => <button type="button" className="link-button" onClick={() => setTeam(row.team)}>{row.team}</button> },
    { key: 'users', header: 'Users', numeric: true, render: (row) => count(row.users) },
    { key: 'coins', header: 'Bobcoin spend', numeric: true, render: (row) => bobcoins(row.bobcoins) },
    { key: 'usd', header: 'USD', numeric: true, render: (row) => usdText(row.bobcoins, rate) },
    { key: 'budget', header: 'Budget used (this month)', render: (row) => <BudgetCell spent={row.budget_bobcoins} budget={row.budget} pct={row.budget_used_pct} /> },
    { key: 'merged', header: 'PRs merged', numeric: true, render: (row) => count(row.prs_merged) },
    { key: 'ttm', header: 'Median time to merge', numeric: true, render: (row) => minutes(row.median_minutes_to_merge) },
    { key: 'blocked', header: 'Violations', numeric: true, render: (row) => count(row.blocked) },
    { key: 'ci', header: 'First-try CI pass', numeric: true, render: (row) => percent(row.first_try_pass_rate_pct) },
  ];
  return (
    <section className="panel table-panel">
      <div className="panel__header"><h2>By team</h2></div>
      {rows?.length ? <NumberTable label="By team" columns={columns} rows={rows} rowKey={(row) => row.team} /> : <EmptyState title="No teams" detail="Teams appear when hook events carry X-Governance-Team." />}
    </section>
  );
}
