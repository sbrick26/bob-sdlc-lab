import { LineChart, SimpleBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Button, Tag, TextInput } from '@carbon/react';
import { useMemo, useState } from 'react';
import { api } from '../api';
import { ChartPanel } from '../components/ChartPanel';
import { RateNote, usdText } from '../components/Money';
import { NumberTable, type Column } from '../components/NumberTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { StatCard } from '../components/StatCard';
import { BASELINE_KEY, bobcoins, count, minutes, percent, readNumber, roi, shortTime, writeNumber } from '../format';
import { useApi, useUsdRate } from '../hooks';
import { LABEL_AXIS, baseOptions, slot, useDarkMode } from '../theme';
import type { PersonUsage, TicketUsage } from '../types';

type PersonRow = Omit<PersonUsage, 'blocks' | 'prs_opened' | 'prs_merged'> & { automation?: boolean; blocks: number | null; prs_opened: number | null; prs_merged: number | null };

const DEFAULT_BASELINE_HOURS = 4;

export function UsagePage() {
  const dark = useDarkMode();
  const state = useApi(api.usage, []);
  const { rate, saved, fromBrowser, setRate } = useUsdRate(state.data?.usd_rate);
  const [baseline, setBaseline] = useState<number>(() => readNumber(BASELINE_KEY, DEFAULT_BASELINE_HOURS) ?? DEFAULT_BASELINE_HOURS);
  const [baselineText, setBaselineText] = useState(String(baseline));
  const [rateText, setRateText] = useState(saved == null ? '' : String(saved));
  const data = state.data;

  const charts = useMemo(() => data && ({
    over: data.bobcoins_over_time.map((item) => ({ group: 'Cumulative Bobcoins', date: new Date(item.time), value: item.bobcoins })),
    perPr: data.cost_per_merged_pr.map((item) => ({ group: 'Bobcoins', key: `${item.ticket} · ${item.user ?? '—'}`, value: item.bobcoins })),
  }), [data]);

  if (state.loading && !data) return <PageLoading />;
  if (state.error || !data || !charts) return <PageError error={state.error || new Error('No usage returned')} retry={state.reload} />;
  const result = roi(data.roi, baseline, rate);
  const onBaseline = (text: string) => {
    setBaselineText(text);
    const value = Number(text);
    if (Number.isFinite(value) && value > 0) { setBaseline(value); writeNumber(BASELINE_KEY, value); }
  };
  const onRate = (text: string) => {
    setRateText(text);
    const value = Number(text);
    if (text.trim() === '') setRate(null);
    else if (Number.isFinite(value) && value > 0) setRate(value);
  };

  const people: Column<PersonRow>[] = [
    { key: 'user', header: 'Person', render: (row) => row.user },
    { key: 'sessions', header: 'Sessions', numeric: true, render: (row) => count(row.sessions) },
    { key: 'turns', header: 'Turns', numeric: true, render: (row) => count(row.turns) },
    { key: 'prompts', header: 'Prompts', numeric: true, render: (row) => count(row.prompts) },
    { key: 'tools', header: 'Tool calls', numeric: true, render: (row) => count(row.tool_calls) },
    { key: 'coins', header: 'Bobcoins', numeric: true, render: (row) => bobcoins(row.bobcoins) },
    { key: 'usd', header: 'USD', numeric: true, render: (row) => usdText(row.bobcoins, rate) },
    { key: 'tokens', header: 'Context tokens', numeric: true, render: (row) => count(row.tokens) },
    { key: 'blocks', header: 'Blocks', numeric: true, render: (row) => count(row.blocks) },
    { key: 'opened', header: 'PRs opened', numeric: true, render: (row) => count(row.prs_opened) },
    { key: 'merged', header: 'Merged', numeric: true, render: (row) => count(row.prs_merged) },
    { key: 'ci', header: 'CI first try', numeric: true, render: (row) => row.ci_with_result ? `${row.ci_first_try_passed} of ${row.ci_with_result}` : '—' },
  ];
  const tickets: Column<TicketUsage>[] = [
    { key: 'ticket', header: 'Ticket', render: (row) => row.ticket },
    { key: 'user', header: 'Person', render: (row) => row.user ?? '—' },
    { key: 'started', header: 'Started', render: (row) => shortTime(row.started_at) },
    { key: 'pr', header: 'PR opened', render: (row) => shortTime(row.pr_opened_at) },
    { key: 'merged', header: 'Merged', render: (row) => row.merged_at ? shortTime(row.merged_at) : <Tag size="sm" type="gray">{row.status.replace('_', ' ')}</Tag> },
    { key: 'topr', header: 'Min to PR', numeric: true, render: (row) => count(row.minutes_to_pr) },
    { key: 'tomerge', header: 'Min to merge', numeric: true, render: (row) => count(row.minutes_to_merge) },
    { key: 'coins', header: 'Bobcoins', numeric: true, render: (row) => bobcoins(row.bobcoins) },
    { key: 'usd', header: 'USD', numeric: true, render: (row) => usdText(row.bobcoins, rate) },
    { key: 'verdict', header: 'Review', render: (row) => row.verdict ? <Tag size="sm" type={row.verdict === 'PASS' ? 'green' : 'red'}>{row.verdict}</Tag> : '—' },
    { key: 'findings', header: 'Findings', numeric: true, render: (row) => count(row.findings) },
  ];
  const r = data.roi;
  const automation = data.automation;
  const peopleRows: PersonRow[] = [
    ...data.people,
    ...(automation ? [{
      user: automation.label, automation: true, sessions: automation.sessions, turns: automation.turns,
      prompts: automation.prompts, tool_calls: automation.tool_calls, bobcoins: automation.bobcoins, usd: automation.usd,
      tokens: automation.tokens, blocks: null, prs_opened: null, prs_merged: null, ci_first_try_passed: 0, ci_with_result: 0,
    }] : []),
  ];

  return (
    <>
      <PageHeader title="Usage & ROI" actions={
        <div className="roi-inputs">
          <TextInput id="baseline-hours" size="sm" type="number" min={0.25} step={0.25} labelText="Baseline hours per ticket" value={baselineText} onChange={(event) => onBaseline(event.currentTarget.value)} />
          <TextInput id="usd-rate" size="sm" type="number" min={0} step={0.01} labelText="USD per Bobcoin" placeholder={data.usd_rate == null ? 'Set rate' : String(data.usd_rate)} value={rateText} onChange={(event) => onRate(event.currentTarget.value)} />
          <Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>
        </div>
      } />
      <section className="kpi-grid kpi-grid--four" aria-label="Return on investment">
        <StatCard label="Hours saved" value={result.hoursSaved == null ? '—' : `${result.hoursSaved.toLocaleString('en-US')} h`} />
        <StatCard label="Bobcoins per merged PR" value={bobcoins(result.bobcoinsPerPr)} detail={result.bobcoinsPerPr == null ? undefined : usdText(result.bobcoinsPerPr, rate)} />
        <StatCard label="Bobcoin spend" value={bobcoins(r.bobcoins_total)} detail={r.bobcoins_total == null ? undefined : usdText(r.bobcoins_total, rate)} />
        <StatCard label="First-try CI pass rate" value={percent(result.firstTryRate)} />
      </section>
      <p className="formula">Hours saved = merged tickets × {baseline} h baseline − actual hours from ticket start to merge. Bobcoins per merged PR = Bobcoins on merged tickets ÷ merged PRs. USD = Bobcoins × rate.</p>
      <RateNote rate={rate} basis={data.usd_rate_basis} fromBrowser={fromBrowser} />

      <section className="chart-grid">
        <ChartPanel title="Cumulative Bobcoins" empty={!charts.over.length} emptyDetail="Spend appears after Bob sends a Stop event with a session cost.">
          <LineChart data={charts.over} options={{ ...baseOptions(dark), axes: { bottom: { mapsTo: 'date', scaleType: 'time' }, left: { mapsTo: 'value', title: 'Cumulative Bobcoins (BC)' } }, curve: 'curveStepAfter', points: { enabled: false }, legend: { enabled: false }, color: { scale: { 'Cumulative Bobcoins': slot(0, dark) } } } as never} />
        </ChartPanel>
        <ChartPanel title="Bobcoins per merged PR" empty={!charts.perPr.length} emptyDetail="Bars appear when a merged ticket has usage.">
          <SimpleBarChart data={charts.perPr} options={{ ...baseOptions(dark), axes: { left: { mapsTo: 'key', ...LABEL_AXIS }, bottom: { mapsTo: 'value', title: 'Bobcoins (BC) per merged PR' } }, legend: { enabled: false }, color: { scale: { Bobcoins: slot(0, dark) } } } as never} />
        </ChartPanel>
      </section>

      <section className="panel table-panel">
        <div className="panel__header"><h2>Usage by person</h2></div>
        {peopleRows.length ? <NumberTable label="Usage by person" columns={people} rows={peopleRows} rowKey={(row) => row.user} rowClass={(row) => row.automation ? 'row--automation' : undefined} /> : <EmptyState title="No users yet" detail="People appear after their first Bob event." />}
      </section>
      <section className="panel table-panel">
        <div className="panel__header"><h2>Delivery and cost by ticket</h2></div>
        {data.tickets.length ? <NumberTable label="Delivery per ticket" columns={tickets} rows={data.tickets} rowKey={(row) => row.ticket} /> : <EmptyState title="No tickets yet" detail="Tickets appear when events carry X-Lab-Ticket." />}
      </section>
    </>
  );
}
