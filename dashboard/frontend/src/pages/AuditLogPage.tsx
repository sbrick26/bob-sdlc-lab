import { Download, Renew } from '@carbon/icons-react';
import { Button, Pagination, Select, SelectItem, TextInput } from '@carbon/react';
import { useMemo, useState } from 'react';
import { api } from '../api';
import { EventDetail } from '../components/EventDetail';
import { EventTable } from '../components/EventTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { count } from '../format';
import { useApi } from '../hooks';
import type { GovernanceEvent } from '../types';

type Filters = { user: string; ticket: string; event: string; decision: string; since: string; until: string };
const initial: Filters = { user: '', ticket: '', event: '', decision: '', since: '', until: '' };

function toParams(filters: Filters, limit?: string) {
  const params = new URLSearchParams(limit ? { limit } : {});
  Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
  return params;
}

export function AuditLogPage() {
  const [filters, setFilters] = useState(initial);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<GovernanceEvent | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const state = useApi(async () => {
    const [events, facets] = await Promise.all([api.events(toParams(filters, '1000')), api.facets()]);
    return { events: events.events, facets };
  }, [filters]);
  const visible = useMemo(() => state.data?.events.slice((page - 1) * pageSize, page * pageSize) ?? [], [state.data, page, pageSize]);
  const update = (key: keyof Filters, value: string) => { setPage(1); setFilters((current) => ({ ...current, [key]: value })); };
  const openEvent = async (summary: GovernanceEvent) => {
    setSelected(summary);
    setDetailError(null);
    try { setSelected(await api.event(summary.event_id)); }
    catch (value) { setDetailError(value instanceof Error ? value.message : 'The event content could not be loaded.'); }
  };

  if (state.loading && !state.data) return <PageLoading />;
  if (state.error || !state.data) return <PageError error={state.error || new Error('No events returned')} retry={state.reload} />;
  const { facets, events } = state.data;
  return (
    <>
      <PageHeader eyebrow="Every hook and lab event" title="Audit log" description="Filter the full record, open any event for its redacted detail, or download the filtered rows as CSV." actions={
        <>
          <Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>
          <Button kind="primary" size="sm" renderIcon={Download} href={api.csvUrl(toParams(filters))}>Download CSV</Button>
        </>
      } />
      <section className="filter-panel filter-panel--audit" aria-label="Audit log filters">
        <div className="filter-panel__title"><strong>Filter events</strong><Button kind="ghost" size="sm" onClick={() => { setPage(1); setFilters(initial); }}>Clear</Button></div>
        <FacetSelect id="filter-user" label="User" value={filters.user} values={facets.users} onChange={(value) => update('user', value)} />
        <FacetSelect id="filter-ticket" label="Ticket" value={filters.ticket} values={facets.tickets ?? []} onChange={(value) => update('ticket', value)} />
        <FacetSelect id="filter-event" label="Event type" value={filters.event} values={facets.events} onChange={(value) => update('event', value)} />
        <FacetSelect id="filter-decision" label="Decision" value={filters.decision} values={facets.decisions} onChange={(value) => update('decision', value)} />
        <TextInput id="filter-since" type="date" labelText="From" value={filters.since} onChange={(event) => update('since', event.currentTarget.value)} />
        <TextInput id="filter-until" type="date" labelText="To" value={filters.until} onChange={(event) => update('until', event.currentTarget.value)} />
      </section>
      <section className="panel table-panel">
        <div className="panel__header"><div><p className="eyebrow">Records</p><h2>{count(events.length)} events</h2></div><span className="muted">CSV holds metadata only, no prompt or tool content</span></div>
        {detailError && <p className="inline-error" role="alert">Event content unavailable: {detailError}</p>}
        {events.length ? (
          <>
            <EventTable events={visible} onSelect={openEvent} />
            <Pagination page={page} pageSize={pageSize} pageSizes={[10, 25, 50, 100]} totalItems={events.length} onChange={({ page: next, pageSize: size }) => { setPage(next); setPageSize(size); }} />
          </>
        ) : <EmptyState title="No events match" detail="Change or clear the filters." />}
      </section>
      {selected && <EventDetail event={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function FacetSelect({ id, label, value, values, onChange }: { id: string; label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return <Select id={id} labelText={label} value={value} onChange={(event) => onChange(event.currentTarget.value)}><SelectItem value="" text="All" />{values.map((item) => <SelectItem value={item} text={item} key={item} />)}</Select>;
}
