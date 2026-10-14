import { GroupedBarChart, SimpleBarChart, StackedBarChart } from '@carbon/charts-react';
import { Button } from '@carbon/react';
import { Renew } from '@carbon/icons-react';
import { useMemo } from 'react';
import { api } from '../api';
import { ChartPanel } from '../components/ChartPanel';
import { RateNote, usdText } from '../components/Money';
import { PageHeader } from '../components/PageHeader';
import { PageError, PageLoading } from '../components/States';
import { StatCard } from '../components/StatCard';
import { bobcoins, bucketLabel, count, minutes, percent } from '../format';
import { useApi, useUsdRate } from '../hooks';
import { LABEL_AXIS, baseOptions, colorScale, countTicks, slot, useDarkMode } from '../theme';

const ACTIVITY = ['Prompts', 'Tool calls', 'Blocks'];

export function OverviewPage() {
  const dark = useDarkMode();
  const state = useApi(api.overview, []);
  const { rate, fromBrowser } = useUsdRate(state.data?.usd_rate);
  const data = state.data;

  const charts = useMemo(() => {
    if (!data) return null;
    const label = (bucket: string) => bucketLabel(bucket, data.granularity);
    const buckets = data.activity.map((item) => item.bucket);
    const order = buckets.map(label);
    const series = [...data.users, data.ci_label];
    const spendKeys = new Set(data.bobcoins_by_user.map((item) => item.bucket));
    const spend = [
      ...data.bobcoins_by_user.map((item) => ({ group: item.user, key: label(item.bucket), value: item.bobcoins })),
      ...buckets.filter((bucket) => !spendKeys.has(bucket)).map((bucket) => ({ group: series[0], key: label(bucket), value: 0 })),
    ];
    // Bucket order first, then the stable series order, so the legend matches the colors.
    spend.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key) || series.indexOf(a.group) - series.indexOf(b.group));
    const activity = data.activity.flatMap((item) => [
      { group: 'Prompts', key: label(item.bucket), value: item.prompts },
      { group: 'Tool calls', key: label(item.bucket), value: item.tool_calls },
      { group: 'Blocks', key: label(item.bucket), value: item.blocks },
    ]);
    const merge = data.time_to_merge.map((item) => ({ group: 'Minutes to merge', key: `${item.ticket} · ${item.user}`, value: item.minutes }));
    const rules = data.violations_by_rule.filter((item) => item.blocked > 0).map((item) => ({ group: 'Blocked', key: item.rule_name || item.rule_id, value: item.blocked }));
    return { spend, order, activity, merge, rules };
  }, [data]);

  if (state.loading && !data) return <PageLoading />;
  if (state.error || !data || !charts) return <PageError error={state.error || new Error('No summary returned')} retry={state.reload} />;
  const k = data.kpis;
  const per = data.granularity === 'hour' ? 'per hour' : 'per day';
  const one = (name: string) => ({ scale: { [name]: slot(0, dark) } });

  return (
    <>
      <PageHeader title="Overview" actions={<Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>} />

      <section className="kpi-grid kpi-grid--four" aria-label="Key numbers">
        <StatCard label="Bobcoin spend" value={bobcoins(k.bobcoins)} detail={k.bobcoins == null ? undefined : usdText(k.bobcoins, rate)} />
        <StatCard label="Bobcoins per merged PR" value={bobcoins(k.bobcoins_per_merged_pr)} detail={k.bobcoins_per_merged_pr == null ? undefined : usdText(k.bobcoins_per_merged_pr, rate)} />
        <StatCard label="PRs merged" value={count(k.prs_merged)} />
        <StatCard label="Median time to merge" value={minutes(k.median_minutes_to_merge)} />
        <StatCard label="Violations blocked" value={count(k.blocked)} />
        <StatCard label="Active people" value={count(k.active_users)} />
        <StatCard label="Bob sessions" value={count(k.sessions)} />
        <StatCard label="First-try CI pass rate" value={percent(k.first_try_pass_rate_pct)} />
      </section>
      <RateNote rate={rate} basis={data.usd_rate_basis} fromBrowser={fromBrowser} />

      <section className="chart-grid">
        <ChartPanel title={`Bobcoins by person, ${per}`} empty={!charts.spend.some((item) => item.value > 0)} emptyDetail="Spend appears after Bob sends a Stop event with a session cost.">
          <StackedBarChart data={charts.spend} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'value', stacked: true, title: 'Bobcoins (BC)' }, bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order } }, color: { scale: colorScale(data.users, dark, [data.ci_label]) } } as never} />
        </ChartPanel>
        <ChartPanel title={data.granularity === 'hour' ? 'Hourly activity' : 'Daily activity'} empty={!charts.activity.some((item) => item.value > 0)}>
          <GroupedBarChart data={charts.activity} options={{ ...baseOptions(dark), axes: { bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order }, left: { mapsTo: 'value', title: 'Events (count)' } }, color: { scale: colorScale(ACTIVITY, dark) } } as never} />
        </ChartPanel>
        <ChartPanel title="Time to merge by ticket" empty={!charts.merge.length} emptyDetail="Bars appear when a ticket has a merge event.">
          <SimpleBarChart data={charts.merge} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'key', ...LABEL_AXIS }, bottom: { mapsTo: 'value', title: 'Minutes, start to merge' } }, legend: { enabled: false }, color: one('Minutes to merge') } as never} />
        </ChartPanel>
        <ChartPanel title="Blocks by rule" empty={!charts.rules.length} emptyDetail="No action has been blocked yet.">
          <SimpleBarChart data={charts.rules} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'key', ...LABEL_AXIS }, bottom: { mapsTo: 'value', title: 'Blocked actions (count)', ...countTicks(Math.max(0, ...charts.rules.map((item) => item.value))) } }, legend: { enabled: false }, color: one('Blocked') } as never} />
        </ChartPanel>
      </section>
    </>
  );
}
