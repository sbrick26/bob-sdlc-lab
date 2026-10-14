import { SimpleBarChart } from '@carbon/charts-react';
import { Download, Renew } from '@carbon/icons-react';
import { Button, Pagination, Select, SelectItem, Tag } from '@carbon/react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { EventTable } from '../components/EventTable';
import { usdText } from '../components/Money';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { useEventDrawer } from '../components/useEventDrawer';
import { filterParams, useFilters, useLive, useNewIds } from '../context';
import { bobcoins, count, eventWords, minutes, shortTime, toolWords } from '../format';
import { FilterChips } from '../components/FilterChips';
import { useApi, useUsdRate } from '../hooks';
import { baseOptions, simpleTip, slot, useDarkMode } from '../theme';
import type { SessionSummary } from '../types';

const LOCAL_KEYS = ['user', 'ticket', 'event', 'decision', 'session', 'tool', 'outcome', 'rule'] as const;
type Local = Record<(typeof LOCAL_KEYS)[number], string>;

export function AuditLogPage() {
  const { filters: global, setTeam } = useFilters();
  const { version } = useLive();
  const [params, setParams] = useSearchParams();
  const local = Object.fromEntries(LOCAL_KEYS.map((key) => [key, params.get(key) ?? ''])) as Local;
  const teamParam = params.get('team');
  useEffect(() => { if (teamParam != null && teamParam !== global.team) setTeam(teamParam); }, [teamParam]); // eslint-disable-line react-hooks/exhaustive-deps
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const drawer = useEventDrawer();
  const session = local.session;
  const query = useMemo(() => {
    const result = session ? new URLSearchParams() : filterParams(global);
    result.set('tz_offset', String(new Date().getTimezoneOffset()));
    // A drill-down to one day carries its own since/until.
    if (params.get('since')) { result.set('since', params.get('since')!); result.set('until', params.get('until') ?? params.get('since')!); }
    Object.entries(local).forEach(([key, value]) => value && result.set(key, value));
    return result;
  }, [global, params]); // eslint-disable-line react-hooks/exhaustive-deps
  const state = useApi(async () => {
    const list = new URLSearchParams(query);
    list.set('limit', '1000');
    if (session) list.set('direction', 'asc');
    const [events, facets, summary] = await Promise.all([api.events(list), api.facets(), session ? api.session(session).catch(() => null) : Promise.resolve(null)]);
    return { events: events.events, facets, summary };
  }, [query, version]);
  const fresh = useNewIds(state.data?.events.map((event) => event.event_id) ?? [], query.toString());
  const visible = useMemo(() => state.data?.events.slice((page - 1) * pageSize, page * pageSize) ?? [], [state.data, page, pageSize]);
  const update = (key: keyof Local, value: string) => {
    setPage(1);
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };

  if (state.loading && !state.data) return <PageLoading />;
  if (!state.data) return <PageError error={state.error || new Error('No events returned')} retry={state.reload} />;
  const { facets, events, summary } = state.data;
  return (
    <>
      <PageHeader title="Audit log" actions={
        <>
          <Button kind="ghost" size="sm" renderIcon={Renew} hasIconOnly iconDescription="Refresh" onClick={state.reload} />
          <Button kind="tertiary" size="sm" renderIcon={Download} href={api.exportUrl('jsonl', query)}>JSONL</Button>
          <Button kind="primary" size="sm" renderIcon={Download} href={api.exportUrl('csv', query)}>CSV</Button>
        </>
      } />
      <section className="filter-panel filter-panel--audit" aria-label="Audit log filters">
        <div className="filter-panel__title"><strong>Filters</strong><Button kind="ghost" size="sm" onClick={() => { setPage(1); setParams(new URLSearchParams(), { replace: true }); }}>Clear</Button></div>
        <FacetSelect id="filter-user" label="User" value={local.user} values={facets.users} onChange={(value) => update('user', value)} />
        <FacetSelect id="filter-ticket" label="Ticket" value={local.ticket} values={facets.tickets ?? []} onChange={(value) => update('ticket', value)} />
        <FacetSelect id="filter-event" label="Event type" value={local.event} values={facets.events} words={eventWords} onChange={(value) => update('event', value)} />
        <FacetSelect id="filter-decision" label="Decision" value={local.decision} values={['violation', ...facets.decisions]} words={(value) => ({ violation: 'Violations (blocked or flagged)', allowed: 'Allowed', blocked: 'Blocked', observed: 'Flagged' }[value] ?? value)} onChange={(value) => update('decision', value)} />
        <FacetSelect id="filter-tool" label="Tool" value={local.tool} values={facets.tools ?? []} words={toolWords} onChange={(value) => update('tool', value)} />
        <FacetSelect id="filter-outcome" label="Tool outcome" value={local.outcome} values={['completed', 'failed', 'blocked']} words={(value) => value[0].toUpperCase() + value.slice(1)} onChange={(value) => update('outcome', value)} />
      </section>
      <FilterChips />
      {session && <SessionHeader summary={summary} sessionId={session} onClear={() => update('session', '')} />}
      <section className="panel table-panel">
        <div className="panel__header"><h2>{session ? `Session timeline (${count(events.length)})` : `Events (${count(events.length)})`}</h2></div>
        {events.length ? (
          <>
            <EventTable events={visible} onSelect={(id) => void drawer.show(id)} fresh={fresh} />
            <Pagination page={page} pageSize={pageSize} pageSizes={[25, 50, 100]} totalItems={events.length} onChange={({ page: next, pageSize: size }) => { setPage(next); setPageSize(size); }} />
          </>
        ) : <EmptyState title="No events match" detail="Change the date range, team or filters." />}
      </section>
      {drawer.drawer}
    </>
  );
}

function SessionHeader({ summary, sessionId, onClear }: { summary: SessionSummary | null; sessionId: string; onClear: () => void }) {
  const dark = useDarkMode();
  const { rate } = useUsdRate(null);
  if (!summary) return <section className="panel table-panel"><EmptyState title="Session not found" detail={`No events for session ${sessionId.slice(0, 8)}.`} /></section>;
  const turns = summary.per_turn.filter((turn) => turn.bobcoins != null).map((turn) => ({ group: 'Bobcoins', key: `Turn ${turn.index}`, value: turn.bobcoins, at: turn.occurred_at }));
  const facts: Array<[string, string]> = [
    ['User', summary.user ?? '—'], ['Team', summary.team ?? '—'], ['Ticket', summary.ticket ?? '—'],
    ['Started', shortTime(summary.started_at)], ['Ended', shortTime(summary.ended_at)], ['Duration', minutes(summary.duration_minutes)],
    ['Turns', count(summary.turns)], ['Bobcoins', `${bobcoins(summary.bobcoins)}${summary.bobcoins != null && rate != null ? ` (${usdText(summary.bobcoins, rate)})` : ''}`],
    ['Context tokens', count(summary.tokens)], ['Violations', count(summary.violations)],
  ];
  return (
    <section className="panel table-panel session-panel">
      <div className="panel__header"><h2>Session <code>{summary.short_id}</code></h2><Tag size="sm" type="gray" filter onClose={onClear}>Filtered to this session</Tag></div>
      <div className="session-panel__body">
        <dl className="session-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        <div className="session-chart">
          <h3>Bobcoins per turn</h3>
          {turns.length
            ? <SimpleBarChart data={turns} options={{ ...baseOptions(dark, '200px'), toolbar: { enabled: false }, axes: { bottom: { mapsTo: 'key', scaleType: 'labels' }, left: { mapsTo: 'value', title: 'BC' } }, legend: { enabled: false }, color: { scale: { Bobcoins: slot(0, dark) } }, ...simpleTip({ Bobcoins: slot(0, dark) }, 'Bobcoins', (d) => bobcoins(d.value)) } as never} />
            : <p className="muted">No Stop events with a cost in this session.</p>}
        </div>
      </div>
    </section>
  );
}

function FacetSelect({ id, label, value, values, onChange, words = (item: string) => item }: { id: string; label: string; value: string; values: string[]; onChange: (value: string) => void; words?: (value: string) => string }) {
  return <Select id={id} labelText={label} value={value} onChange={(event) => onChange(event.currentTarget.value)}><SelectItem value="" text="All" />{values.map((item) => <SelectItem value={item} text={words(item)} key={item} />)}</Select>;
}
