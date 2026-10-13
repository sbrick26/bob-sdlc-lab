import { Filter, Renew } from '@carbon/icons-react';
import { Button, Pagination, Search, Select, SelectItem } from '@carbon/react';
import { useMemo, useState } from 'react';
import { api } from '../api';
import { EventDetail } from '../components/EventDetail';
import { EventTable } from '../components/EventTable';
import { PageHeader } from '../components/PageHeader';
import { PageError, PageLoading } from '../components/States';
import { useApi } from '../hooks';
import type { GovernanceEvent } from '../types';

type Filters = { decision: string; user: string; event: string; rule: string; severity: string; q: string };
const initial: Filters = { decision: '', user: '', event: '', rule: '', severity: '', q: '' };

export function ActivityPage() {
  const [filters, setFilters] = useState(initial);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<GovernanceEvent | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const state = useApi(async () => {
    const params = new URLSearchParams({ limit: '1000' });
    Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
    const [events, facets] = await Promise.all([api.events(params), api.facets()]);
    return { events: events.events, facets };
  }, [filters]);
  const visible = useMemo(() => state.data?.events.slice((page - 1) * pageSize, page * pageSize) ?? [], [state.data, page, pageSize]);
  const update = (key: keyof Filters, value: string) => { setPage(1); setFilters((current) => ({ ...current, [key]: value })); };
  const openEvent = async (summary: GovernanceEvent) => {
    setSelected(summary);
    setDetailError(null);
    try { setSelected(await api.event(summary.event_id)); }
    catch (value) { setDetailError(value instanceof Error ? value.message : 'The investigation content could not be loaded.'); }
  };

  if (state.loading && !state.data) return <PageLoading />;
  if (state.error || !state.data) return <PageError error={state.error || new Error('No events returned')} retry={state.reload} />;
  const { facets, events } = state.data;
  return (
    <>
      <PageHeader eyebrow="Decision records" title="Activity" description="Filter policy decisions, inspect evidence, and trace the control that produced each outcome." actions={<Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>} />
      <section className="filter-panel" aria-label="Activity filters">
        <div className="filter-panel__title"><Filter size={20} /><strong>Filter activity</strong><Button kind="ghost" size="sm" onClick={() => setFilters(initial)}>Clear</Button></div>
        <Search id="activity-search" size="lg" labelText="Search activity" placeholder="Search user, device, workspace, or rule" value={filters.q} onChange={(event) => update('q', event.currentTarget.value)} />
        <div className="filter-grid">
          <FacetSelect id="filter-decision" label="Decision" value={filters.decision} values={facets.decisions} onChange={(value) => update('decision', value)} />
          <FacetSelect id="filter-user" label="User" value={filters.user} values={facets.users} onChange={(value) => update('user', value)} />
          <FacetSelect id="filter-event" label="Control point" value={filters.event} values={facets.events} onChange={(value) => update('event', value)} />
          <FacetSelect id="filter-rule" label="Rule" value={filters.rule} values={facets.rules} onChange={(value) => update('rule', value)} />
          <FacetSelect id="filter-severity" label="Severity" value={filters.severity} values={facets.severities} onChange={(value) => update('severity', value)} />
        </div>
      </section>
      <section className="panel activity-panel">
        <div className="panel__header"><div><p className="eyebrow">Records</p><h2>{events.length.toLocaleString()} decisions</h2></div></div>
        {detailError && <p className="inline-error" role="alert">Investigation content unavailable: {detailError}</p>}
        <EventTable events={visible} onSelect={openEvent} />
        <Pagination page={page} pageSize={pageSize} pageSizes={[10, 25, 50, 100]} totalItems={events.length} onChange={({ page: nextPage, pageSize: nextSize }) => { setPage(nextPage); setPageSize(nextSize); }} />
      </section>
      {selected && <EventDetail event={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function FacetSelect({ id, label, value, values, onChange }: { id: string; label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return <Select id={id} labelText={label} value={value} onChange={(event) => onChange(event.currentTarget.value)}><SelectItem value="" text="All" />{values.map((item) => <SelectItem value={item} text={item} key={item} />)}</Select>;
}
