import { GroupedBarChart, SimpleBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Button, Tag } from '@carbon/react';
import { useMemo } from 'react';
import { api } from '../api';
import { ChartPanel } from '../components/ChartPanel';
import { HBarList } from '../components/HBarList';
import { usdText } from '../components/Money';
import { NumberTable, type Column } from '../components/NumberTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { KpiTile, StatCard } from '../components/StatCard';
import { TeamTable } from '../components/TeamTable';
import { bobcoins, bucketLabel, count, minutes, percent, shortTime, usd } from '../format';
import { useSummary, useUsdRate } from '../hooks';
import { baseOptions, colorScale, countTicks, plural, simpleTip, slot, teamColors, tip, useDarkMode } from '../theme';
import type { TicketRow } from '../types';

export function DeliveryPage() {
  const dark = useDarkMode();
  const state = useSummary(api.delivery);
  const { rate } = useUsdRate(state.data?.usd_rate);
  const data = state.data;

  const charts = useMemo(() => {
    if (!data) return null;
    const colors = teamColors(data.teams, dark);
    return {
      merge: data.merge_by_team.items.map((item) => ({
        label: item.team, other: item.other, value: item.minutes, display: minutes(item.minutes), color: item.other ? '#8d8d8d' : colors[item.team] ?? slot(0, dark),
        tip: { title: item.team, rows: [{ label: 'Median time to merge', value: minutes(item.minutes) }, { label: 'Merged PRs', value: count(item.merged) }] },
      })),
      perPr: data.cost_per_pr_by_team.items.map((item) => ({
        label: item.team, value: item.bobcoins_per_pr, display: bobcoins(item.bobcoins_per_pr), color: colors[item.team] ?? slot(0, dark),
        tip: { title: item.team, rows: [{ label: 'Bobcoins per merged PR', value: bobcoins(item.bobcoins_per_pr), sub: rate == null ? undefined : usdText(item.bobcoins_per_pr, rate) }, { label: 'Merged PRs', value: count(item.merged) }] },
      })),
      prs: data.prs_per_day.flatMap((item) => [
        { group: 'Opened', key: bucketLabel(item.day, data.granularity), value: item.opened, day: item.day },
        { group: 'Merged', key: bucketLabel(item.day, data.granularity), value: item.merged, day: item.day },
      ]),
      order: data.prs_per_day.map((item) => bucketLabel(item.day, data.granularity)),
      distribution: data.merge_distribution.map((item) => ({ group: 'Tickets', key: item.bucket, value: item.count })),
    };
  }, [data, dark, rate]);

  if (state.loading && !data) return <PageLoading />;
  if (!data || !charts) return <PageError error={state.error || new Error('No delivery data returned')} retry={state.reload} />;
  const r = data.roi;
  const k = data.kpis;
  const days = data.period_days;
  const per = data.granularity === 'day' ? 'per day' : `per ${data.granularity}`;
  const columns: Column<TicketRow>[] = [
    { key: 'ticket', header: 'Ticket', width: '6rem', render: (row) => row.ticket, sort: (row) => row.ticket },
    { key: 'user', header: 'User', width: '6rem', render: (row) => row.user ?? '—', sort: (row) => row.user },
    { key: 'team', header: 'Team', width: '6.5rem', render: (row) => row.team, sort: (row) => row.team },
    { key: 'started', header: 'Started', width: '8.5rem', render: (row) => shortTime(row.started_at), sort: (row) => row.started_at },
    { key: 'pr', header: 'PR opened', width: '8.5rem', render: (row) => shortTime(row.pr_opened_at), sort: (row) => row.pr_opened_at },
    { key: 'merged', header: 'Merged', width: '8.5rem', render: (row) => (row.merged_at ? shortTime(row.merged_at) : <Tag size="sm" type="gray">{row.status.replace('_', ' ')}</Tag>), sort: (row) => row.merged_at },
    { key: 'topr', header: 'Time to PR', numeric: true, width: '7rem', render: (row) => minutes(row.minutes_to_pr), sort: (row) => row.minutes_to_pr },
    { key: 'tomerge', header: 'Time to merge', numeric: true, width: '7rem', render: (row) => minutes(row.minutes_to_merge), sort: (row) => row.minutes_to_merge },
    { key: 'hands', header: 'Active time', title: 'Time spent working with Bob from the first prompt to the PR, not counting gaps over 15 minutes', numeric: true, width: '7rem', render: (row) => minutes(row.hands_on_hours == null ? null : row.hands_on_hours * 60), sort: (row) => row.hands_on_hours },
    { key: 'coins', header: 'Bobcoins', numeric: true, width: '6.5rem', render: (row) => bobcoins(row.bobcoins), sort: (row) => row.bobcoins },
    { key: 'usd', header: 'USD', numeric: true, width: '5rem', render: (row) => usdText(row.bobcoins, rate) },
    { key: 'verdict', header: 'Review', width: '5rem', render: (row) => (row.verdict ? <Tag size="sm" type={row.verdict === 'PASS' ? 'green' : 'red'}>{row.verdict}</Tag> : '—'), sort: (row) => row.verdict },
    { key: 'findings', header: 'Findings', numeric: true, width: '5rem', render: (row) => count(row.findings), sort: (row) => row.findings },
  ];
  const unrankedPr = data.cost_per_pr_by_team.unranked;

  return (
    <>
      <PageHeader title="Delivery" actions={<Button kind="ghost" size="sm" renderIcon={Renew} hasIconOnly iconDescription="Refresh" onClick={state.reload} />} />
      <section className="kpi-grid kpi-grid--four" aria-label="Delivery">
        <StatCard label="Average time to PR" value={minutes(r.avg_minutes_to_pr)} />
        <StatCard label="Average time to merge" value={minutes(r.avg_minutes_to_merge)} />
        <KpiTile label="Bobcoins per merged PR" kpi={k.bobcoins_per_merged_pr} format={bobcoins} better="down" days={days} detail={r.bobcoins_per_merged_pr == null ? undefined : usdText(r.bobcoins_per_merged_pr, rate)} />
        <KpiTile label="First-try CI pass rate" kpi={k.first_try_pass_rate_pct} format={percent} better="up" days={days} />
      </section>
      <p className="formula">Bobcoins per merged PR = all Bobcoins in the period ÷ PRs merged in the period. USD at {rate == null ? 'no rate' : usd(rate)} per Bobcoin.</p>

      <section className="chart-grid">
        <ChartPanel title="Time to merge, median by team" empty={!charts.merge.length} emptyDetail="Appears when tickets merge in this period." viewAll={data.merge_by_team.truncated ? { href: '#/delivery' } : null}>
          <HBarList label="Time to merge by team" items={charts.merge} />
        </ChartPanel>
        <ChartPanel title="Bobcoins per merged PR by team" empty={!charts.perPr.length} emptyDetail="Needs a team with 3 or more merged PRs in this period."
          foot={unrankedPr ? `Teams with fewer than ${data.cost_per_pr_by_team.min_prs ?? 3} merged PRs in this range are not ranked (${unrankedPr}).` : undefined}>
          <HBarList label="Bobcoins per merged PR by team" items={charts.perPr} />
        </ChartPanel>
        <ChartPanel title="Time to merge distribution" empty={!charts.distribution.some((item) => item.value > 0)} emptyDetail="Appears when tickets merge in this period.">
          <SimpleBarChart data={charts.distribution} options={{ ...baseOptions(dark, '260px'), axes: { bottom: { mapsTo: 'key', scaleType: 'labels' }, left: { mapsTo: 'value', ...countTicks(Math.max(0, ...charts.distribution.map((item) => item.value))) } }, legend: { enabled: false }, color: { scale: { Tickets: slot(0, dark) } }, ...simpleTip({ Tickets: slot(0, dark) }, 'Tickets merged', (d) => count(d.value)) } as never} />
        </ChartPanel>
        <ChartPanel title={`PRs opened and merged ${per}`} empty={!charts.prs.some((item) => item.value > 0)} emptyDetail="No PR was opened or merged in this period.">
          <GroupedBarChart data={charts.prs} options={{ ...baseOptions(dark, '260px'), axes: { bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order }, left: { mapsTo: 'value', ...countTicks(Math.max(0, ...charts.prs.map((item) => item.value))) } }, color: { scale: colorScale(['Opened', 'Merged'], dark) }, ...tip(colorScale(['Opened', 'Merged'], dark), (items) => ({ title: String(items[0]?.key ?? ''), rows: items.map((d) => ({ label: d.group, value: plural(d.value, 'PR', 'PRs') })) })) } as never} />
        </ChartPanel>
      </section>
      <TeamTable rows={data.by_team} rate={rate} />
      <section className="panel table-panel">
        <div className="panel__header"><h2>Tickets</h2></div>
        {data.tickets.length ? <NumberTable label="Tickets" minWidth="80rem" columns={columns} rows={data.tickets} rowKey={(row) => row.ticket} /> : <EmptyState title="No tickets in this period" detail="Tickets appear when events carry a ticket key." />}
      </section>
    </>
  );
}
