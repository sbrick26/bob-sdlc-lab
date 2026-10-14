import { LineChart, SimpleBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Accordion, AccordionItem, Button } from '@carbon/react';
import { useMemo } from 'react';
import { api } from '../api';
import { ChartPanel } from '../components/ChartPanel';
import { NumberTable, type Column } from '../components/NumberTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { bucketLabel, count, millis, seconds } from '../format';
import { useSummary } from '../hooks';
import { baseOptions, colorScale, slot, tip, useDarkMode } from '../theme';
import type { PerformanceSummary, Stats } from '../types';
import { KpiTile } from '../components/StatCard';

type ToolRow = PerformanceSummary['tools']['items'][number];
const human = (value: number | null) => (value == null ? '—' : value < 60 ? `${Math.round(value)} s` : `${(value / 60).toFixed(1).replace(/\.0$/, '')} min`);

export function PerformancePage() {
  const dark = useDarkMode();
  const state = useSummary(api.performance);
  const data = state.data;

  const charts = useMemo(() => {
    if (!data) return null;
    const label = (day: string) => bucketLabel(day, data.granularity);
    const minutesScale = Math.max(0, ...data.series.map((item) => item.answer_typical_s ?? 0)) > 120;
    const toUnit = (value: number | null) => (value == null ? null : minutesScale ? Math.round((value / 60) * 10) / 10 : Math.round(value));
    return {
      unit: minutesScale ? 'min' : 's',
      answer: data.series.filter((item) => item.answer_typical_s != null).map((item) => ({ group: 'Typical answer time', key: label(item.day), value: toUnit(item.answer_typical_s), answers: item.answers })),
      tools: data.series.filter((item) => item.tool_success_pct != null).map((item) => ({ group: 'Tool runs that succeed', date: new Date(`${item.day}T12:00:00`), key: label(item.day), value: item.tool_success_pct, runs: item.tool_runs })),
    };
  }, [data]);

  if (state.loading && !data) return <PageLoading />;
  if (!data || !charts) return <PageError error={state.error || new Error('No performance data returned')} retry={state.reload} />;
  const k = data.kpis;
  const days = data.period_days;
  const one = colorScale(['Tool runs that succeed'], dark);
  const toolColumns: Column<ToolRow>[] = [
    { key: 'tool', header: 'Tool', render: (row) => row.tool, sort: (row) => row.tool },
    { key: 'runs', header: 'Runs', numeric: true, render: (row) => count(row.runs), sort: (row) => row.runs },
    { key: 'success', header: 'Success', numeric: true, render: (row) => (row.success_pct == null ? '—' : `${row.success_pct.toFixed(1)}%`), sort: (row) => row.success_pct },
    { key: 'typical', header: 'Typical time', numeric: true, render: (row) => seconds(row.typical_s), sort: (row) => row.typical_s },
  ];
  const e = data.engineering;

  return (
    <>
      <PageHeader title="Performance" actions={<Button kind="ghost" size="sm" renderIcon={Renew} hasIconOnly iconDescription="Refresh" onClick={state.reload} />} />
      <section className="kpi-grid kpi-grid--three" aria-label="Performance">
        <KpiTile label="Answer time, typical" kpi={k.turn_p50_s} format={human} better="down" days={days} />
        <KpiTile label="Tool run time, typical" kpi={k.tool_p50_s} format={seconds} better="down" days={days} />
        <KpiTile label="Tool success rate" kpi={k.tool_success_pct} format={(value) => (value == null ? '—' : `${value.toFixed(1)}%`)} better="up" days={days} />
      </section>
      <p className="rate-note">Answer time runs from a prompt to Bob's reply and includes time waiting for people to approve actions.</p>

      <h2 className="section-title">Response time</h2>
      <section className="chart-grid chart-grid--single">
        <ChartPanel title="Typical answer time" empty={!charts.answer.length} emptyDetail="Appears when a prompt is followed by Bob's reply.">
          <SimpleBarChart data={charts.answer} options={{ ...baseOptions(dark, '240px'), axes: { bottom: { mapsTo: 'key', scaleType: 'labels' }, left: { mapsTo: 'value', title: charts.unit === 'min' ? 'Minutes' : 'Seconds' } }, legend: { enabled: false }, color: { scale: { 'Typical answer time': slot(0, dark) } }, ...tip({ 'Typical answer time': slot(0, dark) }, (items) => ({ title: String(items[0]?.key ?? ''), rows: [{ label: 'Typical answer time', value: `${items[0]?.value} ${charts.unit}` }, { label: 'Answers', value: count(items[0]?.answers) }] })) } as never} />
        </ChartPanel>
      </section>

      <h2 className="section-title">Tool reliability</h2>
      <section className="chart-grid">
        <ChartPanel title="Tool runs that succeed (%)" empty={!charts.tools.length} emptyDetail="Appears when tools run in this period.">
          <LineChart data={charts.tools} options={{ ...baseOptions(dark, '260px'), axes: { bottom: { mapsTo: 'key', scaleType: 'labels' }, left: { mapsTo: 'value', title: '%', domain: [Math.min(80, ...charts.tools.map((item) => item.value ?? 100)), 100] } }, curve: 'curveMonotoneX', points: { enabled: true, radius: 3 }, legend: { enabled: false }, color: { scale: one }, ...tip(one, (items) => ({ title: String(items[0]?.key ?? ''), rows: [{ label: 'Succeeded', value: `${items[0]?.value}%` }, { label: 'Tool runs', value: count(items[0]?.runs) }] })) } as never} />
        </ChartPanel>
        <article className="panel chart-panel">
          <div className="panel__header"><h2>Tools</h2></div>
          {data.tools.items.length ? <NumberTable label="Tools" columns={toolColumns} rows={data.tools.items} rowKey={(row) => row.tool} /> : <EmptyState title="No tool runs" detail="No tool ran in this period." />}
        </article>
      </section>

      <Accordion className="engineer-details">
        <AccordionItem title="Details for engineers">
          <EngineerTable groups={[
            { name: 'Bob', rows: [{ name: 'Answer time', stats: e.answer_s, unit: 's' }] },
            { name: 'Tools', rows: toolRows(e.tools) },
            { name: 'Governance', rows: [
              { name: 'Round trip from laptop', stats: e.client_round_trip_ms, unit: 'ms' },
              { name: 'Server check time', stats: e.server_check_ms, unit: 'ms' },
            ] },
          ]} />
          <p className="rate-note">A tool run counts as failed when it starts but never finishes within 10 minutes; blocked actions are not counted.</p>
        </AccordionItem>
      </Accordion>
    </>
  );
}

const TOOL_NAMES: Record<string, string> = {
  write_file: 'Write file', execute_command: 'Run command', read_file: 'Read file', apply_diff: 'Edit file (diff)',
  insert_content: 'Insert into file', search_and_replace: 'Search and replace', list_files: 'List files', search_files: 'Search files',
  use_mcp_tool: 'MCP tool', access_mcp_resource: 'MCP resource',
};
const toolName = (tool: string) => TOOL_NAMES[tool] ?? tool.replace(/_/g, ' ').replace(/^./, (char) => char.toUpperCase());

type EngineerRow = { name: string; stats: Stats; unit: 's' | 'ms'; other?: boolean };

function toolRows(tools: Array<Stats & { tool: string }>): EngineerRow[] {
  const sorted = [...tools].sort((a, b) => b.samples - a.samples || a.tool.localeCompare(b.tool));
  const head: EngineerRow[] = sorted.slice(0, 10).map((item) => ({ name: toolName(item.tool), stats: item, unit: 's' }));
  const tail = sorted.slice(10);
  if (tail.length) head.push({ name: `Other (${tail.length} tools)`, stats: { p50: null, p95: null, p99: null, samples: tail.reduce((sum, item) => sum + item.samples, 0) }, unit: 's', other: true });
  return head;
}

function unitText(value: number | null, unit: 's' | 'ms'): string {
  if (value == null) return '—';
  return unit === 'ms' ? millis(value) : seconds(value);
}

/** One aligned table: typical, slow and slowest values, and a range bar from p50 to p95 with a tick at p99. */
function EngineerTable({ groups }: { groups: Array<{ name: string; rows: EngineerRow[] }> }) {
  return (
    <table className="engineer-table">
      <colgroup><col /><col style={{ width: '7.5rem' }} /><col style={{ width: '7.5rem' }} /><col style={{ width: '7.5rem' }} /><col style={{ width: '12rem' }} /><col style={{ width: '6rem' }} /></colgroup>
      <thead><tr><th>Measure</th><th className="num">Typical (p50)</th><th className="num">Slow (p95)</th><th className="num">Slowest (p99)</th><th>Range</th><th className="num">Samples</th></tr></thead>
      {groups.map((group) => (
        <tbody key={group.name}>
          <tr className="engineer-table__group"><th colSpan={6}>{group.name}</th></tr>
          {group.rows.map((row) => {
            const { p50, p95, p99 } = row.stats;
            const top = Math.max(p99 ?? 0, p95 ?? 0, p50 ?? 0) * 1.05 || 1;
            return (
              <tr key={row.name} className={row.other ? 'engineer-table__other' : undefined}>
                <td>{row.name}</td>
                <td className="num">{unitText(p50, row.unit)}</td>
                <td className="num">{unitText(p95, row.unit)}</td>
                <td className="num">{unitText(p99, row.unit)}</td>
                <td>
                  {p50 != null && p95 != null ? (
                    <span className="range-bar" aria-hidden="true">
                      <span className="range-bar__span" style={{ left: `${(p50 / top) * 100}%`, width: `${Math.max(((p95 - p50) / top) * 100, 1)}%` }} />
                      {p99 != null && <span className="range-bar__tick" style={{ left: `${(p99 / top) * 100}%` }} />}
                    </span>
                  ) : null}
                </td>
                <td className="num">{count(row.stats.samples)}</td>
              </tr>
            );
          })}
        </tbody>
      ))}
    </table>
  );
}
