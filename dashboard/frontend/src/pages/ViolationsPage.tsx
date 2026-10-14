import { SimpleBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Button, DataTable, Pagination, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from '@carbon/react';
import { useMemo, useState } from 'react';
import { api } from '../api';
import { ChartPanel } from '../components/ChartPanel';
import { DecisionTag } from '../components/DecisionTag';
import { EventDetail } from '../components/EventDetail';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { StatCard } from '../components/StatCard';
import { count, shortTime } from '../format';
import { useApi } from '../hooks';
import { LABEL_AXIS, baseOptions, countTicks, slot, useDarkMode } from '../theme';
import { bucketLabel } from '../format';
import type { GovernanceEvent } from '../types';

const headers = [
  { key: 'time', header: 'Time' },
  { key: 'user', header: 'User' },
  { key: 'ticket', header: 'Ticket' },
  { key: 'rule', header: 'Rule' },
  { key: 'control_point', header: 'Control point' },
  { key: 'excerpt', header: 'What was attempted' },
  { key: 'decision', header: 'Decision' },
];

export function ViolationsPage() {
  const dark = useDarkMode();
  const state = useApi(api.violations, []);
  const [selected, setSelected] = useState<GovernanceEvent | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const data = state.data;

  const charts = useMemo(() => {
    if (!data) return null;
    const bar = (group: string) => (key: string, value: number) => ({ group, key, value });
    return {
      rule: data.by_rule.map((item) => bar('Blocked')(item.rule_name || item.rule_id, item.blocked)),
      point: data.by_control_point.map((item) => bar('Blocked')(item.control_point, item.blocked)),
      user: data.by_user.map((item) => bar('Blocked')(item.user, item.blocked)),
      time: data.over_time.map((item) => ({ group: 'Blocked', key: bucketLabel(item.bucket, data.granularity), value: item.blocked })),
    };
  }, [data]);

  if (state.loading && !data) return <PageLoading />;
  if (state.error || !data || !charts) return <PageError error={state.error || new Error('No violations returned')} retry={state.reload} />;
  const one = { scale: { Blocked: slot(0, dark) } };
  const barOptions = (title: string, items: Array<{ value: number }>) => ({ ...baseOptions(dark, '280px'), axes: { left: { mapsTo: 'key', ...LABEL_AXIS }, bottom: { mapsTo: 'value', title, ...countTicks(Math.max(0, ...items.map((item) => item.value))) } }, legend: { enabled: false }, color: one });
  const openEvent = async (eventId: string) => {
    setDetailError(null);
    try { setSelected(await api.event(eventId)); }
    catch (value) { setDetailError(value instanceof Error ? value.message : 'The event could not be loaded.'); }
  };
  const visible = data.rows.slice((page - 1) * pageSize, page * pageSize);
  const rows = visible.map((row) => ({
    id: row.event_id, time: shortTime(row.occurred_at), user: row.user, ticket: row.ticket || '—',
    rule: row.rule_name ? `${row.rule_id} ${row.rule_name}` : row.rule_id, control_point: row.control_point,
    excerpt: row.excerpt || '—', decision: row.decision,
  }));
  const t = data.totals;

  return (
    <>
      <PageHeader eyebrow="Policy findings" title="Violations" description="Every action a rule blocked or flagged: which rule, where in Bob's loop, who, and what was attempted. Excerpts are redacted." actions={<Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>} />
      <section className="kpi-grid kpi-grid--four" aria-label="Violation totals">
        <StatCard label="Blocked" value={count(t.blocked)} detail="Actions stopped before they ran" signal={t.blocked ? 'negative' : 'neutral'} />
        <StatCard label="Flagged" value={count(t.observed)} detail="Recorded, not stopped (tool output, response)" />
        <StatCard label="People affected" value={count(t.users_affected)} detail="Users with at least one finding" />
        <StatCard label="Rules fired" value={count(t.rules_fired)} detail="Distinct rules with a finding" />
      </section>
      <section className="chart-grid">
        <ChartPanel eyebrow="By rule" question="Which rules block most often?" empty={!charts.rule.length} emptyDetail="No action has been blocked yet.">
          <SimpleBarChart data={charts.rule} options={barOptions('Blocked actions (count)', charts.rule) as never} />
        </ChartPanel>
        <ChartPanel eyebrow="By control point" question="Where in Bob's loop are actions stopped?" empty={!charts.point.some((item) => item.value > 0)} emptyDetail="No action has been blocked yet.">
          <SimpleBarChart data={charts.point} options={barOptions('Blocked actions (count)', charts.point) as never} />
        </ChartPanel>
        <ChartPanel eyebrow="By person" question="Who triggers the controls?" empty={!charts.user.length} emptyDetail="No action has been blocked yet.">
          <SimpleBarChart data={charts.user} options={barOptions('Blocked actions (count)', charts.user) as never} />
        </ChartPanel>
        <ChartPanel eyebrow="Over time" question={`When were actions blocked, per ${data.granularity}?`} note={`${data.granularity === "day" ? "Days" : "Hours"} in UTC.`} empty={!charts.time.some((item) => item.value > 0)} emptyDetail="No action has been blocked yet.">
          <SimpleBarChart data={charts.time} options={{ ...baseOptions(dark, '280px'), axes: { bottom: { mapsTo: 'key', scaleType: 'labels' }, left: { mapsTo: 'value', title: 'Blocked actions (count)', ...countTicks(Math.max(0, ...charts.time.map((item) => item.value))) } }, legend: { enabled: false }, color: one } as never} />
        </ChartPanel>
      </section>
      <section className="panel table-panel">
        <div className="panel__header"><div><p className="eyebrow">Findings</p><h2>{count(data.rows.length)} violations, newest first</h2></div><span className="muted">Select a row for the full, redacted record</span></div>
        {detailError && <p className="inline-error" role="alert">Event unavailable: {detailError}</p>}
        {data.rows.length ? (
          <>
            <DataTable rows={rows} headers={headers}>
              {({ rows: tableRows, headers: tableHeaders, getHeaderProps, getRowProps, getTableProps }) => (
                <TableContainer className="event-table-wrap">
                  <Table {...getTableProps()} size="md">
                    <TableHead><TableRow>{tableHeaders.map((header) => <TableHeader {...getHeaderProps({ header })} key={header.key}>{header.header}</TableHeader>)}</TableRow></TableHead>
                    <TableBody>
                      {tableRows.map((row) => (
                        <TableRow {...getRowProps({ row })} key={row.id} className="event-row" onClick={() => void openEvent(row.id)} tabIndex={0} onKeyDown={(event) => event.key === 'Enter' && void openEvent(row.id)}>
                          {row.cells.map((cell) => (
                            <TableCell key={cell.id} className={cell.info.header === 'excerpt' ? 'excerpt-cell' : undefined}>
                              {cell.info.header === 'decision' ? <DecisionTag decision={cell.value} /> : String(cell.value)}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DataTable>
            <Pagination page={page} pageSize={pageSize} pageSizes={[10, 25, 50, 100]} totalItems={data.rows.length} onChange={({ page: next, pageSize: size }) => { setPage(next); setPageSize(size); }} />
          </>
        ) : <EmptyState title="No violations" detail="Blocked and flagged actions appear here." />}
      </section>
      {selected && <EventDetail event={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
