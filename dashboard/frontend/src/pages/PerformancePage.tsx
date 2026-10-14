import { GroupedBarChart, SimpleBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Button } from '@carbon/react';
import { useMemo } from 'react';
import { api } from '../api';
import { ChartPanel } from '../components/ChartPanel';
import { NumberTable, type Column } from '../components/NumberTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { KpiTile } from '../components/StatCard';
import { bucketLabel, count, millis, seconds } from '../format';
import { useSummary } from '../hooks';
import { LABEL_AXIS, baseOptions, colorScale, simpleTip, slot, tip, useDarkMode } from '../theme';
import type { PerformanceSummary } from '../types';

type Tool = PerformanceSummary['tools'][number];

export function PerformancePage() {
  const dark = useDarkMode();
  const state = useSummary(api.performance);
  const data = state.data;

  const charts = useMemo(() => data && ({
    tools: [...data.tools].filter((item) => item.p50_s != null).sort((a, b) => b.calls - a.calls || a.tool.localeCompare(b.tool)).slice(0, 10).flatMap((item) => [
      { group: 'p50', key: item.tool, value: item.p50_s },
      { group: 'p95', key: item.tool, value: item.p95_s },
    ]),
    turns: data.series.map((item) => ({ group: 'Turn time p95', key: bucketLabel(item.day, data.granularity), day: item.day, value: item.turn_p95_s == null ? null : Math.round(item.turn_p95_s / 6) / 10 })),
    failures: data.series.map((item) => ({ group: 'Tool failure rate', key: bucketLabel(item.day, data.granularity), day: item.day, value: item.tool_failure_rate_pct })),
    order: data.series.map((item) => bucketLabel(item.day, data.granularity)),
  }), [data]);

  if (state.loading && !data) return <PageLoading />;
  if (!data || !charts) return <PageError error={state.error || new Error('No performance data returned')} retry={state.reload} />;
  const k = data.kpis;
  const days = data.period_days;
  const columns: Column<Tool>[] = [
    { key: 'tool', header: 'Tool', render: (row) => row.tool, sort: (row) => row.tool },
    { key: 'calls', header: 'Calls', numeric: true, render: (row) => count(row.calls), sort: (row) => row.calls },
    { key: 'p50', header: 'p50', numeric: true, render: (row) => seconds(row.p50_s), sort: (row) => row.p50_s },
    { key: 'p95', header: 'p95', numeric: true, render: (row) => seconds(row.p95_s), sort: (row) => row.p95_s },
    { key: 'failures', header: 'Failures', numeric: true, render: (row) => count(row.failures), sort: (row) => row.failures },
  ];

  return (
    <>
      <PageHeader title="Performance" actions={<Button kind="ghost" size="sm" renderIcon={Renew} hasIconOnly iconDescription="Refresh" onClick={state.reload} />} />
      <section className="kpi-grid kpi-grid--four" aria-label="Performance">
        <KpiTile label="Tool time p50 / p95" kpi={k.tool_p95_s} format={() => `${seconds(k.tool_p50_s?.value)} / ${seconds(k.tool_p95_s?.value)}`} better="down" days={days} />
        <KpiTile label="Turn time p50 / p95" kpi={k.turn_p95_s} format={() => `${seconds(k.turn_p50_s?.value)} / ${seconds(k.turn_p95_s?.value)}`} better="down" days={days} />
        <KpiTile label="Governance check p50 / p95" kpi={k.check_p95_ms} format={() => `${millis(k.check_p50_ms?.value)} / ${millis(k.check_p95_ms?.value)}`} better="down" days={days} />
        <KpiTile label="Tool failure rate" kpi={k.tool_failure_rate_pct} format={(value) => (value == null ? '—' : `${value.toFixed(1)}%`)} better="down" days={days} />
      </section>
      <section className="chart-grid">
        <ChartPanel title="Tool time by tool, top 10 by calls" empty={!charts.tools.length} emptyDetail="Appears when tool calls have both a PreToolUse and a PostToolUse.">
          <GroupedBarChart data={charts.tools} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'key', ...LABEL_AXIS }, bottom: { mapsTo: 'value', title: 'Seconds' } }, color: { scale: colorScale(['p50', 'p95'], dark) }, ...tip(colorScale(['p50', 'p95'], dark), (data) => ({ title: String(data[0]?.key ?? ''), rows: data.map((d) => ({ label: d.group, value: seconds(d.value) })) })) } as never} />
        </ChartPanel>
        <ChartPanel title="Turn time p95" empty={!charts.turns.some((item) => item.value != null)} emptyDetail="Appears when a prompt is followed by a Stop event.">
          <SimpleBarChart data={charts.turns.filter((item) => item.value != null)} options={{ ...baseOptions(dark), axes: { bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order }, left: { mapsTo: 'value', title: 'Minutes, prompt to Stop' } }, legend: { enabled: false }, color: { scale: { 'Turn time p95': slot(0, dark) } }, ...simpleTip({ 'Turn time p95': slot(0, dark) }, 'Turn time p95', (d) => `${d.value} min`) } as never} />
        </ChartPanel>
        <ChartPanel title="Tool failure rate" empty={!charts.failures.some((item) => item.value != null)} emptyDetail="Appears when tool calls run in this period.">
          <SimpleBarChart data={charts.failures.filter((item) => item.value != null)} options={{ ...baseOptions(dark), axes: { bottom: { mapsTo: 'key', scaleType: 'labels', domain: charts.order }, left: { mapsTo: 'value', title: '% of tool calls with no result in 10 min' } }, legend: { enabled: false }, color: { scale: { 'Tool failure rate': slot(0, dark) } }, ...simpleTip({ 'Tool failure rate': slot(0, dark) }, 'Tool calls with no result', (d) => `${d.value}%`) } as never} />
        </ChartPanel>
        <article className="panel chart-panel">
          <div className="panel__header"><h2>Tools</h2></div>
          {data.tools.length ? <NumberTable label="Tools" columns={columns} rows={data.tools} rowKey={(row) => row.tool} /> : <EmptyState title="No tool calls" detail="No tool ran in this period." />}
        </article>
      </section>
      <p className="rate-note">Samples: {count(data.samples.tool_calls)} tool calls, {count(data.samples.turns)} turns, {count(data.samples.checks)} governance checks.</p>
    </>
  );
}
