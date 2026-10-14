import { SimpleBarChart, StackedBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Button } from '@carbon/react';
import { useMemo } from 'react';
import { api } from '../api';
import { BudgetTile } from '../components/Budget';
import { ChartPanel } from '../components/ChartPanel';
import { HBarList } from '../components/HBarList';
import { RateNote, usdText } from '../components/Money';
import { PageHeader } from '../components/PageHeader';
import { PageError, PageLoading } from '../components/States';
import { KpiTile } from '../components/StatCard';
import { TeamTable } from '../components/TeamTable';
import { bobcoins, bucketLabel, count, drillHref, minutes, percent } from '../format';
import { useSummary, useUsdRate } from '../hooks';
import { baseOptions, countTicks, severityColor, simpleTip, slot, teamColors, tip, useDarkMode, type TipSpec } from '../theme';

export function OverviewPage() {
  const dark = useDarkMode();
  const state = useSummary(api.overview);
  const { rate, fromBrowser } = useUsdRate(state.data?.usd_rate);
  const data = state.data;

  const charts = useMemo(() => {
    if (!data) return null;
    const label = (day: string) => bucketLabel(day, data.granularity);
    const order = data.days.map(label);
    const teams = [...new Set(data.spend_by_team.map((item) => item.team))];
    const spend = data.spend_by_team.map((item) => ({ group: item.team, key: label(item.day), value: item.bobcoins, day: item.day }));
    const active = data.daily_active.map((item) => ({ group: 'Daily active users', key: label(item.day), value: item.people, day: item.day }));
    const maxMinutes = Math.max(0, ...data.merge_median_per_day.map((item) => item.minutes ?? 0));
    const hours = maxMinutes > 180;
    const merge = data.merge_median_per_day.filter((item) => item.minutes != null).map((item) => ({
      group: 'Median time to merge', key: label(item.day), value: hours ? Math.round((item.minutes as number) / 6) / 10 : item.minutes, day: item.day, merged: item.merged,
    }));
    return { order, teams, spend, active, merge, mergeUnit: hours ? 'h' : 'min', label };
  }, [data]);

  if (state.loading && !data) return <PageLoading />;
  if (!data || !charts) return <PageError error={state.error || new Error('No summary returned')} retry={state.reload} />;
  const k = data.kpis;
  const days = data.period_days;
  const colors = teamColors([...data.teams, ...charts.teams], dark);
  const one = (name: string) => ({ scale: { [name]: slot(0, dark) } });
  const per = data.granularity === 'day' ? 'per day' : data.granularity === 'week' ? 'per week' : 'per month';
  const spendTip = (day: string | undefined): TipSpec => {
    const items = data.spend_by_team.filter((item) => item.day === day);
    const total = items.reduce((sum, item) => sum + item.bobcoins, 0);
    return {
      title: day ? charts.label(day) : '',
      rows: items.map((item) => ({ label: item.team, value: bobcoins(item.bobcoins), sub: rate == null ? undefined : usdText(item.bobcoins, rate) })),
      total: items.length > 1 ? { label: 'Total', value: bobcoins(total), sub: rate == null ? undefined : usdText(total, rate) } : undefined,
    };
  };
  const teamBars = data.violations_by_team.items.map((item) => ({
    label: item.team, other: item.other, value: item.violations, display: count(item.violations), color: item.other ? '#8d8d8d' : colors[item.team] ?? slot(0, dark),
    href: item.other ? undefined : drillHref('violations', { team: item.team }),
    tip: { title: item.team, rows: [{ label: 'Violations', value: count(item.violations), color: colors[item.team] }] },
  }));
  const ruleBars = data.violations_by_rule.items.map((item) => ({
    label: item.other ? item.rule_id : item.rule_name || item.rule_id, other: item.other, value: item.violations, display: count(item.violations),
    color: item.other ? '#8d8d8d' : severityColor(item.severity, dark), href: item.other ? undefined : drillHref('violations', { rule: item.rule_id }),
    tip: { title: item.rule_name || item.rule_id, rows: [{ label: 'Blocked', value: count(item.blocked) }, { label: 'Flagged', value: count(item.observed) }, ...(item.severity ? [{ label: 'Severity', value: item.severity }] : [])] },
  }));

  return (
    <>
      <PageHeader title="Overview" actions={<Button kind="ghost" size="sm" renderIcon={Renew} hasIconOnly iconDescription="Refresh" onClick={state.reload} />} />
      <section className="kpi-grid kpi-grid--four" aria-label="Key numbers">
        <KpiTile label="Bobcoin spend" kpi={k.bobcoins} format={bobcoins} days={days} detail={k.bobcoins?.value == null ? undefined : usdText(k.bobcoins.value, rate)} />
        <BudgetTile spent={k.budget_used_bobcoins?.value ?? null} budget={k.budget_total?.value ?? null} pct={k.budget_used_pct?.value ?? null} />
        <KpiTile label="Bobcoins per merged PR" kpi={k.bobcoins_per_merged_pr} format={bobcoins} better="down" days={days} detail={k.bobcoins_per_merged_pr?.value == null ? undefined : usdText(k.bobcoins_per_merged_pr.value, rate)} />
        <KpiTile label="PRs merged" kpi={k.prs_merged} format={count} better="up" days={days} href="#/delivery" />
        <KpiTile label="Daily active users (avg)" kpi={k.daily_active_people} format={(value) => (value == null ? '—' : value.toFixed(1))} better="up" days={days} />
        <KpiTile label="Median time to merge" kpi={k.median_minutes_to_merge} format={minutes} better="down" days={days} />
        <KpiTile label="Violations" kpi={k.violations} format={count} better="down" days={days} href="#/violations" />
        <KpiTile label="First-try CI pass rate" kpi={k.first_try_pass_rate_pct} format={percent} better="up" days={days} />
      </section>
      <RateNote rate={rate} basis={data.usd_rate_basis} fromBrowser={fromBrowser} />

      <TeamTable rows={data.by_team} rate={rate} />

      <section className="chart-grid">
        <ChartPanel title="Bobcoin spend by team" empty={!charts.spend.length} emptyDetail="Spend appears after Bob sends a Stop event with a session cost.">
          <StackedBarChart data={charts.spend} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'value', stacked: true, title: `Bobcoins (BC) ${per}` }, bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order } }, color: { scale: colors }, ...tip(colors, (items) => spendTip(items[0]?.day)) } as never} />
        </ChartPanel>
        <ChartPanel title="Violations by team" empty={!teamBars.length} emptyDetail="No violations in this period." viewAll={data.violations_by_team.truncated ? { href: '#/violations' } : null}>
          <HBarList label="Violations by team" items={teamBars} />
        </ChartPanel>
        <ChartPanel title={data.granularity === 'day' ? 'Daily active users' : `Daily active users (average ${per})`} empty={!charts.active.some((item) => item.value > 0)}>
          <SimpleBarChart data={charts.active} options={{ ...baseOptions(dark), axes: { bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order }, left: { mapsTo: 'value', ...countTicks(Math.max(0, ...charts.active.map((item) => item.value))) } }, legend: { enabled: false }, color: one('Daily active users'), ...simpleTip({ 'Daily active users': slot(0, dark) }, 'Active users', (d) => (d.value ?? 0).toLocaleString('en-US', { maximumFractionDigits: 1 }), (d) => String(d.key ?? '')) } as never} />
        </ChartPanel>
        <ChartPanel title={`Time to merge, median ${per}`} empty={!charts.merge.length} emptyDetail="Appears when tickets merge in this period.">
          <SimpleBarChart data={charts.merge} options={{ ...baseOptions(dark), axes: { bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order }, left: { mapsTo: 'value', title: charts.mergeUnit === 'h' ? 'Hours' : 'Minutes' } }, legend: { enabled: false }, color: one('Median time to merge'), ...tip({ 'Median time to merge': slot(0, dark) }, (items) => ({ title: String(items[0]?.key ?? ''), rows: [{ label: 'Median time to merge', value: `${items[0]?.value} ${charts.mergeUnit}` }, { label: 'Tickets merged', value: count(items[0]?.merged) }] })) } as never} />
        </ChartPanel>
      </section>
      <section className="chart-grid chart-grid--single">
        <ChartPanel title="Violations by rule" empty={!ruleBars.length} emptyDetail="No violations in this period." viewAll={data.violations_by_rule.truncated ? { href: '#/violations' } : null}>
          <HBarList label="Violations by rule" items={ruleBars} />
        </ChartPanel>
      </section>
    </>
  );
}
