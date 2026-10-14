import { SimpleBarChart } from '@carbon/charts-react';
import { Renew } from '@carbon/icons-react';
import { Button, DataTable, Pagination, Tab, TabList, TabPanel, TabPanels, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow, Tabs, Tag } from '@carbon/react';
import { useMemo, useState } from 'react';
import { api } from '../api';
import { ChartPanel } from '../components/ChartPanel';
import { DecisionTag } from '../components/DecisionTag';
import { NumberTable, type Column } from '../components/NumberTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { KpiTile } from '../components/StatCard';
import { useEventDrawer } from '../components/useEventDrawer';
import { useFilters, useNewIds } from '../context';
import { HBarList } from '../components/HBarList';
import { bucketLabel, count, drillHref, shortTime } from '../format';
import { useSummary } from '../hooks';
import { baseOptions, countTicks, neutral, plural, severityColor, simpleTip, slot, teamColors, useDarkMode } from '../theme';
import type { RuleSummary, ViolationRow, ViolationsSummary } from '../types';

const headers = [
  { key: 'time', header: 'Time' }, { key: 'user', header: 'User' }, { key: 'team', header: 'Team' },
  { key: 'ticket', header: 'Ticket' }, { key: 'rule', header: 'Rule' }, { key: 'control_point', header: 'Control point' },
  { key: 'excerpt', header: 'What was attempted' }, { key: 'decision', header: 'Decision' },
];

function RuleLink({ id, url }: { id: string; url?: string | null }) {
  return url ? <a href={url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}><code className="rule-id">{id}</code></a> : <code className="rule-id">{id}</code>;
}

export function ViolationsPage() {
  const [tab, setTab] = useState(0);
  const state = useSummary(api.violations);
  const rules = useSummary(api.rules);
  if (state.loading && !state.data) return <PageLoading />;
  if (!state.data) return <PageError error={state.error || new Error('No violations returned')} retry={state.reload} />;
  return (
    <>
      <PageHeader title="Violations" actions={<Button kind="ghost" size="sm" renderIcon={Renew} hasIconOnly iconDescription="Refresh" onClick={() => { void state.reload(); void rules.reload(); }} />} />
      <Tabs selectedIndex={tab} onChange={({ selectedIndex }) => setTab(selectedIndex)}>
        <TabList aria-label="Violations and rules" className="page-tabs">
          <Tab>Violations</Tab>
          <Tab>Rules</Tab>
        </TabList>
        <TabPanels>
          <TabPanel className="tab-panel"><ViolationsTab data={state.data} /></TabPanel>
          <TabPanel className="tab-panel">{rules.data ? <RulesTab rules={rules.data.rules} source={rules.data.source} /> : <PageLoading />}</TabPanel>
        </TabPanels>
      </Tabs>
    </>
  );
}

function ViolationsTab({ data }: { data: ViolationsSummary }) {
  const dark = useDarkMode();
  const { filters } = useFilters();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const drawer = useEventDrawer();
  const fresh = useNewIds(data.rows.map((row) => row.event_id), JSON.stringify(filters));
  const colors = teamColors(data.teams, dark);
  const charts = useMemo(() => ({
    time: data.over_time.map((item) => ({ group: 'Violations', key: bucketLabel(item.day, data.granularity), value: item.violations, day: item.day })),
    rule: data.by_rule.items.map((item) => ({
      label: item.other ? item.rule_id : item.rule_name || item.rule_id, other: item.other, value: item.violations, display: count(item.violations),
      color: item.other ? '#8d8d8d' : severityColor(item.severity, dark), href: item.other ? undefined : drillHref('violations', { rule: item.rule_id }),
      tip: { title: item.rule_name || item.rule_id, rows: [{ label: 'Violations', value: count(item.violations) }, ...(item.severity ? [{ label: 'Severity', value: item.severity }] : [])] },
    })),
    user: data.by_user.items.map((item, index) => ({
      label: item.user, other: item.other, value: item.violations, display: count(item.violations), color: item.other ? '#8d8d8d' : neutral(index, dark),
      href: item.other ? undefined : drillHref('violations', { user: item.user }),
      tip: { title: item.user, rows: [{ label: 'Violations', value: count(item.violations) }] },
    })),
    team: data.violations_by_team.items.map((item) => ({
      label: item.team, other: item.other, value: item.violations, display: count(item.violations), color: item.other ? '#8d8d8d' : colors[item.team] ?? slot(0, dark),
      href: item.other ? undefined : drillHref('violations', { team: item.team }),
      tip: { title: item.team, rows: [{ label: 'Violations', value: count(item.violations), color: colors[item.team] }] },
    })),
    rate: data.rate_by_user.items.map((item, index) => ({
      label: item.other ? `${item.user}, average` : item.user, other: item.other, value: item.violation_rate, display: `${item.violation_rate.toFixed(1)} per 100`,
      color: item.other ? '#8d8d8d' : neutral(index, dark), href: item.other ? undefined : drillHref('violations', { user: item.user }),
      tip: { title: item.user, rows: [{ label: 'Violation rate', value: `${item.violation_rate.toFixed(1)} per 100 actions` }, { label: 'Violations', value: count(item.violations) }, { label: 'Actions', value: count(item.actions) }] },
    })),
  }), [data, dark, colors]);
  const k = data.kpis;
  const days = data.period_days;
  const per = data.granularity === 'day' ? 'Violations over time' : `Violations over time, per ${data.granularity}`;
  const visible = data.rows.slice((page - 1) * pageSize, page * pageSize);
  const byId = new Map<string, ViolationRow>(visible.map((row) => [row.event_id, row]));
  const rows = visible.map((row) => ({
    id: row.event_id, time: shortTime(row.occurred_at), user: row.user, team: row.team, ticket: row.ticket || '—',
    rule: row.rule_name || row.rule_id, control_point: row.control_point, excerpt: row.excerpt || '—', decision: row.decision,
  }));
  const rate = data.rate_by_user;
  return (
    <>
      <section className="kpi-grid kpi-grid--four" aria-label="Violation totals">
        <KpiTile label="Violations" kpi={k.violations} format={count} better="down" days={days} />
        <KpiTile label="Violation rate (per 100 actions)" kpi={k.violation_rate} format={(value) => (value == null ? '—' : value.toFixed(1))} better="down" days={days} />
        <KpiTile label="Users affected" kpi={k.users_affected} format={count} better="down" days={days} />
        <KpiTile label="Repeat violations" kpi={k.repeat_violations} format={count} better="down" days={days} />
      </section>
      <section className="chart-grid chart-grid--single">
        <ChartPanel title={per} empty={!charts.time.some((item) => item.value > 0)} emptyDetail="No violations in this period.">
          <SimpleBarChart data={charts.time} options={{ ...baseOptions(dark, '220px'), axes: { bottom: { mapsTo: 'key', scaleType: 'labels' }, left: { mapsTo: 'value', ...countTicks(Math.max(0, ...charts.time.map((item) => item.value))) } }, legend: { enabled: false }, color: { scale: { Violations: slot(0, dark) } }, ...simpleTip({ Violations: slot(0, dark) }, 'Violations', (d) => count(d.value)) } as never} />
        </ChartPanel>
      </section>
      <section className="chart-grid chart-grid--three chart-grid--even">
        <ChartPanel title="Violations by rule" empty={!charts.rule.length} emptyDetail="No violations in this period." viewAll={data.by_rule.truncated ? { href: '#/violations', label: 'View all rules' } : null}>
          <HBarList label="Violations by rule" items={charts.rule} />
        </ChartPanel>
        <ChartPanel title="Violations by user" empty={!charts.user.length} emptyDetail="No violations in this period." viewAll={data.by_user.truncated ? { href: '#/usage' } : null}>
          <HBarList label="Violations by user" items={charts.user} />
        </ChartPanel>
        <ChartPanel title="Violations by team" empty={!charts.team.length} emptyDetail="No violations in this period." viewAll={data.violations_by_team.truncated ? { href: '#/usage' } : null}>
          <HBarList label="Violations by team" items={charts.team} />
        </ChartPanel>
      </section>
      <section className="chart-grid chart-grid--single">
        <ChartPanel title="Violation rate by user, per 100 actions" empty={!charts.rate.length} emptyDetail={`No user had ${rate.min_actions ?? 20} or more prompts and tool calls in this period.`}
          viewAll={rate.truncated ? { href: '#/usage' } : null}
          foot={rate.unranked ? `Users with fewer than ${rate.min_actions ?? 20} actions in this range are not ranked (${rate.unranked}).` : undefined}>
          <HBarList label="Violation rate by user" items={charts.rate} />
        </ChartPanel>
      </section>
      <section className="panel table-panel">
        <div className="panel__header"><h2>Violations ({count(data.rows.length)})</h2></div>
        {data.rows.length ? (
          <>
            <DataTable rows={rows} headers={headers}>
              {({ rows: tableRows, headers: tableHeaders, getHeaderProps, getRowProps, getTableProps }) => (
                <TableContainer className="event-table-wrap">
                  <Table {...getTableProps()} size="md">
                    <TableHead><TableRow>{tableHeaders.map((header) => <TableHeader {...getHeaderProps({ header })} key={header.key}>{header.header}</TableHeader>)}</TableRow></TableHead>
                    <TableBody>
                      {tableRows.map((row) => {
                        const source = byId.get(row.id)!;
                        return (
                          <TableRow {...getRowProps({ row })} key={row.id} className={`event-row${fresh.has(row.id) ? ' row--new' : ''}`} onClick={() => void drawer.show(row.id)} tabIndex={0} onKeyDown={(event) => event.key === 'Enter' && void drawer.show(row.id)}>
                            {row.cells.map((cell) => (
                              <TableCell key={cell.id} className={cell.info.header === 'excerpt' ? 'excerpt-cell' : undefined}>
                                {cell.info.header === 'decision' ? <DecisionTag decision={source.decision} />
                                  : cell.info.header === 'rule' ? <span className="rule-cell"><RuleLink id={source.rule_id} url={source.rule_url} /> {source.rule_name}</span>
                                    : String(cell.value)}
                              </TableCell>
                            ))}
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DataTable>
            <Pagination page={page} pageSize={pageSize} pageSizes={[10, 25, 50, 100]} totalItems={data.rows.length} onChange={({ page: next, pageSize: size }) => { setPage(next); setPageSize(size); }} />
          </>
        ) : <EmptyState title="No violations" detail="Blocked and flagged actions in this period appear here." />}
      </section>
      {drawer.drawer}
    </>
  );
}


function RulesTab({ rules, source }: { rules: RuleSummary[]; source?: { url: string; ref?: string | null; loaded_at?: string | null; path?: string | null; last_error?: string | null } }) {
  const columns: Column<RuleSummary>[] = [
    { key: 'id', header: 'Rule', render: (row) => <RuleLink id={row.rule_id} url={row.url} />, sort: (row) => row.rule_id },
    { key: 'name', header: 'Name', render: (row) => <strong>{row.name}</strong>, sort: (row) => row.name },
    { key: 'checks', header: 'What it checks', render: (row) => <span className="rule-checks">{row.checks}</span>, sort: (row) => row.checks },
    { key: 'where', header: 'Where it runs', render: (row) => row.control_point, sort: (row) => row.control_point },
    { key: 'action', header: 'Action', render: (row) => (row.enabled ? <Tag size="sm" type={row.action === 'blocked' ? 'red' : 'purple'}>{row.action === 'blocked' ? 'Blocks' : 'Flags'}</Tag> : <Tag size="sm" type="gray">Off</Tag>) },
    { key: 'fired', header: 'Times fired', numeric: true, render: (row) => count(row.blocked + row.observed), sort: (row) => row.blocked + row.observed },
    { key: 'last', header: 'Last fired', render: (row) => shortTime(row.last_fired), sort: (row) => row.last_fired },
  ];
  return (
    <section className="panel table-panel">
      <div className="panel__header panel__header--stacked">
        <h2>Rules ({rules.length})</h2>
        {source && <p className="panel__subtitle">Source: {source.path ?? 'built-in defaults'}{source.ref ? ` on ${source.ref}` : ''}{source.loaded_at ? `, loaded ${shortTime(source.loaded_at)}` : ''}</p>}
      </div>
      {rules.length ? <NumberTable label="Rules" columns={columns} rows={rules} rowKey={(row) => row.rule_id} /> : <EmptyState title="No rules" detail="The rule catalog is empty." />}
    </section>
  );
}
