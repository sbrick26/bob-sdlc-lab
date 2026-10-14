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
import { bobcoins, bucketLabel, count, minutes } from '../format';
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
    const spendKeys = new Set(data.bobcoins_by_user.map((item) => item.bucket));
    const firstUser = data.users[0] ?? 'unknown';
    const spend = [
      ...data.bobcoins_by_user.map((item) => ({ group: item.user, key: label(item.bucket), value: item.bobcoins })),
      ...buckets.filter((bucket) => !spendKeys.has(bucket)).map((bucket) => ({ group: firstUser, key: label(bucket), value: 0 })),
    ];
    const order = buckets.map(label);
    // Bucket order first, then the stable user order, so the legend matches the colors.
    spend.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key) || data.users.indexOf(a.group) - data.users.indexOf(b.group));
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
  const period = data.granularity === 'hour' ? 'hour' : 'day';
  const usersScale = colorScale(data.users, dark);
  const one = (name: string) => ({ scale: { [name]: slot(0, dark) } });

  return (
    <>
      <PageHeader eyebrow="Bob usage and governance" title="Overview" description="How much the team uses Bob, what it costs, how fast tickets reach a merged PR, and what the controls blocked." actions={<Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>} />

      <section className="kpi-grid kpi-grid--auto" aria-label="Key numbers">
        <StatCard label="Active users" value={count(k.active_users)} detail="People with Bob hook events" />
        <StatCard label="Bob sessions" value={count(k.sessions)} detail="Distinct Bob sessions" />
        <StatCard label="Prompts" value={count(k.prompts)} detail={`${count(k.tool_calls)} tool calls`} />
        <StatCard label="Bobcoin spend" value={bobcoins(k.bobcoins)} detail={k.bobcoins == null ? 'No usage reported yet' : usdText(k.bobcoins, rate)} />
        <StatCard label="Context tokens" value={count(k.tokens)} detail="Sum of per-turn context size" />
        <StatCard label="Violations blocked" value={count(k.blocked)} detail="Stopped before the model or tool ran" signal={k.blocked ? 'negative' : 'neutral'} />
        <StatCard label="PRs merged" value={count(k.prs_merged)} detail="Tickets with a merge event" signal={k.prs_merged ? 'positive' : 'neutral'} />
        <StatCard label="Median start to merge" value={minutes(k.median_minutes_to_merge)} detail="Ticket start to merged PR" />
        <StatCard label="Bobcoins per merged PR" value={bobcoins(k.bobcoins_per_merged_pr)} detail={k.bobcoins_per_merged_pr == null ? 'No merged PR with usage yet' : usdText(k.bobcoins_per_merged_pr, rate)} />
      </section>
      <RateNote rate={rate} basis={data.usd_rate_basis} fromBrowser={fromBrowser} />

      <section className="chart-grid">
        <ChartPanel eyebrow="Spend" question={`Who spent the Bobcoins, per ${period}?`} note={`${period === "day" ? "Days" : "Hours"} in UTC. A session's spend is placed at the Stop events that reported it.`} empty={!charts.spend.some((item) => item.value > 0)} emptyDetail="Spend appears after Bob sends a Stop event with a session cost.">
          <StackedBarChart data={charts.spend} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'value', stacked: true, title: 'Bobcoins (BC)' }, bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order } }, color: { scale: usersScale } } as never} />
        </ChartPanel>
        <ChartPanel eyebrow="Activity" question={`How much did people use Bob, per ${period}?`} note={`${period === "day" ? "Days" : "Hours"} in UTC.`} empty={!charts.activity.some((item) => item.value > 0)}>
          <GroupedBarChart data={charts.activity} options={{ ...baseOptions(dark), axes: { bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order }, left: { mapsTo: 'value', title: 'Events (count)' } }, color: { scale: colorScale(ACTIVITY, dark) } } as never} />
        </ChartPanel>
        <ChartPanel eyebrow="Delivery" question="How long did each ticket take from start to merge?" empty={!charts.merge.length} emptyDetail="Bars appear when a ticket has a merge event.">
          <SimpleBarChart data={charts.merge} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'key', ...LABEL_AXIS }, bottom: { mapsTo: 'value', title: 'Minutes, start to merge' } }, legend: { enabled: false }, color: one('Minutes to merge') } as never} />
        </ChartPanel>
        <ChartPanel eyebrow="Controls" question="Which rules blocked the most actions?" empty={!charts.rules.length} emptyDetail="No action has been blocked yet.">
          <SimpleBarChart data={charts.rules} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'key', ...LABEL_AXIS }, bottom: { mapsTo: 'value', title: 'Blocked actions (count)', ...countTicks(Math.max(0, ...charts.rules.map((item) => item.value))) } }, legend: { enabled: false }, color: one('Blocked') } as never} />
        </ChartPanel>
      </section>
    </>
  );
}
