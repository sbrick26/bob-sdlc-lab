import { StackedBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Button, Tag } from '@carbon/react';
import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { BudgetCell, BudgetTile } from '../components/Budget';
import { ChartPanel } from '../components/ChartPanel';
import { HBarList } from '../components/HBarList';
import { RateNote, usdText } from '../components/Money';
import { NumberTable, type Column } from '../components/NumberTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { KpiTile } from '../components/StatCard';
import { TeamTable } from '../components/TeamTable';
import { bobcoins, bucketLabel, count, drillHref, percent } from '../format';
import { useSummary, useUsdRate } from '../hooks';
import { baseOptions, teamColors, tip, useDarkMode, type TipSpec } from '../theme';
import type { BudgetEntry, CostSummary } from '../types';

type UserRow = CostSummary['people'][number] & { automation?: boolean };
type Outlier = CostSummary['outliers'][number];

const FLAG_LABEL: Record<string, string> = { 'context tokens': 'Tokens', turns: 'Turns', Bobcoins: 'Bobcoins' };
const LEVEL_TAG: Record<string, 'red' | 'magenta' | 'gray'> = { over: 'red', near: 'magenta' };

export function UsagePage() {
  const dark = useDarkMode();
  const [params] = useSearchParams();
  const userFilter = params.get('user') ?? '';
  const state = useSummary(api.cost);
  const { rate, fromBrowser } = useUsdRate(state.data?.usd_rate);
  const data = state.data;

  const charts = useMemo(() => {
    if (!data) return null;
    const label = (day: string) => bucketLabel(day, data.granularity);
    const teams = [...new Set(data.daily.flatMap((item) => Object.keys(item.teams)))];
    const colors = teamColors([...data.teams, ...teams], dark);
    const spend = data.daily.flatMap((item) => Object.entries(item.teams).map(([team, value]) => ({ group: team, key: label(item.day), value, day: item.day })));
    const paceFactor = data.granularity === 'day' ? 1 : data.granularity === 'week' ? 7 : 30;
    const pace = data.budgets.daily_pace == null ? null : data.budgets.daily_pace * paceFactor;
    const burn = [...data.budgets.teams].sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0) || a.name.localeCompare(b.name)).slice(0, 10).map((item) => ({
      label: item.name, value: item.pct ?? 0, display: percent(item.pct),
      color: (item.pct ?? 0) >= 100 ? '#da1e28' : (item.pct ?? 0) >= 80 ? '#f1c21b' : colors[item.name] ?? '#4589ff',
      tip: { title: item.name, rows: [{ label: 'Spent this month', value: bobcoins(item.bobcoins), sub: rate == null ? undefined : usdText(item.bobcoins, rate) }, { label: 'Budget', value: bobcoins(item.budget) }, { label: 'Used', value: percent(item.pct) }] },
    }));
    return { label, colors, spend, order: data.daily.map((item) => label(item.day)), pace, burn };
  }, [data, dark, rate]);

  if (state.loading && !data) return <PageLoading />;
  if (!data || !charts) return <PageError error={state.error || new Error('No usage data returned')} retry={state.reload} />;
  const days = data.period_days;
  const eq = data.equation;

  const users: UserRow[] = [
    ...data.people.filter((row) => !userFilter || row.user === userFilter),
    ...(data.automation && !userFilter ? [{ ...data.automation, user: data.automation.label, team: '—', budget_pct: null, automation: true }] : []),
  ];
  const userColumns: Column<UserRow>[] = [
    { key: 'user', header: 'User', width: '12rem', render: (row) => row.user, sort: (row) => row.user },
    { key: 'team', header: 'Team', render: (row) => row.team, sort: (row) => row.team },
    { key: 'sessions', header: 'Sessions', numeric: true, render: (row) => count(row.sessions), sort: (row) => row.sessions },
    { key: 'turns', header: 'Turns', numeric: true, render: (row) => count(row.turns), sort: (row) => row.turns },
    { key: 'coins', header: 'Bobcoins', numeric: true, render: (row) => bobcoins(row.bobcoins), sort: (row) => row.bobcoins },
    { key: 'usd', header: 'USD', numeric: true, render: (row) => usdText(row.bobcoins, rate) },
    { key: 'tokens', header: 'Context tokens', numeric: true, width: '8.5rem', render: (row) => count(row.tokens), sort: (row) => row.tokens },
    { key: 'budget', header: 'User budget (this month)', width: '15rem', render: (row) => <BudgetCell spent={row.budget_bobcoins ?? null} budget={row.budget ?? null} pct={row.budget_pct} />, sort: (row) => row.budget_pct },
  ];
  const nearColumns: Column<BudgetEntry>[] = [
    { key: 'name', header: 'Name', render: (row) => row.name, sort: (row) => row.name },
    { key: 'kind', header: 'Kind', render: (row) => (row.kind === 'person' ? 'User' : 'Team'), sort: (row) => row.kind },
    { key: 'budget', header: 'Budget used (this month)', width: '15rem', render: (row) => <BudgetCell spent={row.bobcoins} budget={row.budget} pct={row.pct} />, sort: (row) => row.pct },
    { key: 'level', header: '', render: (row) => <Tag size="sm" type={LEVEL_TAG[row.level ?? ''] ?? 'gray'}>{row.level === 'over' ? 'Over' : 'Near'}</Tag> },
    { key: 'left', header: 'Bobcoins left', numeric: true, render: (row) => bobcoins(row.left), sort: (row) => row.left },
  ];
  const t = data.outlier_thresholds;
  const jira = data.jira_base_url;
  const outlierColumns: Column<Outlier>[] = [
    { key: 'user', header: 'User', render: (row) => <a href={`#/usage?user=${encodeURIComponent(row.user)}`}>{row.user}</a>, sort: (row) => row.user },
    { key: 'ticket', header: 'Ticket', render: (row) => (row.ticket ? <a href={jira ? `${jira}/browse/${row.ticket}` : `#/audit?ticket=${encodeURIComponent(row.ticket)}`} target={jira ? '_blank' : undefined} rel="noreferrer">{row.ticket}</a> : '—'), sort: (row) => row.ticket },
    { key: 'session', header: 'Session', width: '7rem', render: (row) => <a href={`#/audit?session=${encodeURIComponent(row.session_id)}`}><code>{row.session}</code></a> },
    { key: 'tokens', header: 'Context tokens', numeric: true, width: '8.5rem', render: (row) => count(row.tokens), sort: (row) => row.tokens },
    { key: 'turns', header: 'Turns', numeric: true, render: (row) => count(row.turns), sort: (row) => row.turns },
    { key: 'coins', header: 'Bobcoins', numeric: true, render: (row) => bobcoins(row.bobcoins), sort: (row) => row.bobcoins },
    { key: 'flags', header: 'Over the limit on', width: '14rem', render: (row) => <span className="flag-tags">{row.flags.map((flag) => <Tag key={flag} size="sm" type="magenta">{FLAG_LABEL[flag] ?? flag}</Tag>)}</span> },
  ];
  const spendTip = (day: string | undefined): TipSpec => {
    const item = data.daily.find((entry) => entry.day === day);
    const entries = Object.entries(item?.teams ?? {});
    return {
      title: day ? charts.label(day) : '',
      rows: entries.map(([team, value]) => ({ label: team, value: bobcoins(value), sub: rate == null ? undefined : usdText(value, rate) })),
      total: entries.length > 1 && item ? { label: 'Total', value: bobcoins(item.total), sub: rate == null ? undefined : usdText(item.total, rate) } : undefined,
      footer: item && data.budgets.total_budget ? { label: 'Month to date', value: `${item.month_to_date.toFixed(2)} / ${data.budgets.total_budget.toFixed(0)} BC` } : undefined,
    };
  };
  const per = data.granularity === 'day' ? 'Daily' : data.granularity === 'week' ? 'Weekly' : 'Monthly';

  return (
    <>
      <PageHeader title="Usage" actions={
        <>
          <Button kind="ghost" size="sm" renderIcon={Renew} hasIconOnly iconDescription="Refresh" onClick={state.reload} />
        </>
      } />
      <section className="kpi-grid kpi-grid--three" aria-label="Spend">
        <KpiTile label="Total Bobcoin spend" kpi={eq.total_bobcoins} format={bobcoins} days={days} detail={eq.total_bobcoins?.value == null ? undefined : usdText(eq.total_bobcoins.value, rate)} />
        <KpiTile label="User spend" kpi={eq.people_bobcoins} format={bobcoins} days={days} detail={eq.people_bobcoins?.value == null ? undefined : usdText(eq.people_bobcoins.value, rate)} />
        <KpiTile label={data.ci_label} kpi={eq.ci_bobcoins} format={bobcoins} days={days} detail={eq.ci_bobcoins?.value == null ? undefined : usdText(eq.ci_bobcoins.value, rate)} />
        <BudgetTile spent={data.budgets.used_bobcoins} budget={data.budgets.total_budget} pct={data.budgets.used_pct} />
        <KpiTile label="Active users" kpi={eq.active_people} format={count} better="up" days={days} />
        <KpiTile label="Bobcoins per active user" kpi={eq.bobcoins_per_user} format={bobcoins} days={days} detail={eq.bobcoins_per_user?.value == null ? undefined : usdText(eq.bobcoins_per_user.value, rate)} />
      </section>
      <RateNote rate={rate} basis={data.usd_rate_basis} fromBrowser={fromBrowser} />

      <section className="chart-grid chart-grid--single">
        <ChartPanel title={`${per} Bobcoin spend`} empty={!charts.spend.length} emptyDetail="Spend appears after Bob sends a Stop event with a session cost.">
          <StackedBarChart data={charts.spend} options={{
            ...baseOptions(dark, '280px'),
            axes: {
              left: { mapsTo: 'value', stacked: true, title: 'Bobcoins (BC)', ...(charts.pace ? { thresholds: [{ value: charts.pace, label: `Budget pace ${charts.pace.toFixed(1)} BC`, fillColor: '#8d8d8d' }] } : {}) },
              bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order },
            },
            color: { scale: charts.colors }, ...tip(charts.colors, (items) => spendTip(items[0]?.day)),
          } as never} />
        </ChartPanel>
      </section>
      <section className="chart-grid">
        <ChartPanel title="Budget burn, this month" empty={!charts.burn.length} emptyDetail="No team budgets are configured.">
          <HBarList label="Budget burn" items={charts.burn} max={110} markers={[{ value: 50, label: '50%', tone: 'neutral' }, { value: 80, label: '80%', tone: 'warning' }, { value: 100, label: '100%', tone: 'danger' }]} />
        </ChartPanel>
        <article className="panel chart-panel">
          <div className="panel__header"><h2>Near limit</h2></div>
          {data.budgets.near_limit.length
            ? <NumberTable label="Near limit" columns={nearColumns} rows={data.budgets.near_limit} rowKey={(row) => `${row.kind}-${row.name}`} />
            : <EmptyState title="Nobody is near a limit" detail="Users and teams at 80% or more of their monthly budget appear here." />}
        </article>
      </section>
      <TeamTable rows={data.by_team} rate={rate} />
      <section className="panel table-panel" id="users">
        <div className="panel__header"><h2>{userFilter ? `Spend for ${userFilter}` : 'Spend per user'}</h2>{userFilter && <a className="chart-panel__link" href="#/usage">Show all users</a>}</div>
        {users.length ? <NumberTable label="Users" columns={userColumns} rows={users} rowKey={(row) => row.user} rowClass={(row) => (row.automation ? 'row--automation' : undefined)} rowHref={(row) => (row.automation ? undefined : drillHref('audit', { user: row.user }))} /> : <EmptyState title="No usage in this period" detail="Rows appear after Bob sends usage on Stop events." />}
      </section>
      <section className="panel table-panel">
        <div className="panel__header panel__header--stacked"><h2>Outlier sessions</h2><p className="panel__subtitle">Over {count(t.tokens)} context tokens, over {t.turns} turns, or over {t.bobcoins} BC in one session.</p></div>
        {data.outliers.length
          ? <NumberTable label="Outlier sessions" columns={outlierColumns} rows={data.outliers} rowKey={(row) => row.session_id} />
          : <EmptyState title="No outliers" detail="No session crossed a limit in this period." />}
      </section>
    </>
  );
}
