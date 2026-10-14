import { Renew } from '@carbon/icons-react';
import { Button, Tag } from '@carbon/react';
import { api } from '../api';
import { NumberTable, type Column } from '../components/NumberTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { count, shortTime } from '../format';
import { useApi } from '../hooks';
import type { RuleSummary } from '../types';

const columns: Column<RuleSummary>[] = [
  { key: 'id', header: 'Rule', render: (row) => <code className="rule-id">{row.rule_id}</code> },
  { key: 'name', header: 'Name', render: (row) => <strong>{row.name}</strong> },
  { key: 'checks', header: 'What it checks', render: (row) => <span className="rule-checks">{row.checks}</span> },
  { key: 'where', header: 'Where it runs', render: (row) => row.control_point },
  { key: 'action', header: 'Action', render: (row) => <Tag size="sm" type={row.action === 'blocked' ? 'red' : 'purple'}>{row.action === 'blocked' ? 'Blocks' : 'Flags'}</Tag> },
  { key: 'fired', header: 'Times fired', numeric: true, render: (row) => count(row.blocked + row.observed) },
  { key: 'last', header: 'Last fired', render: (row) => shortTime(row.last_fired) },
];

export function RulesPage() {
  const state = useApi(api.rules, []);
  if (state.loading && !state.data) return <PageLoading />;
  if (state.error || !state.data) return <PageError error={state.error || new Error('No rules returned')} retry={state.reload} />;
  return (
    <>
      <PageHeader title="Rules" actions={<Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>} />
      <section className="panel table-panel">
        <div className="panel__header"><h2>Rules ({state.data.count})</h2></div>
        {state.data.rules.length ? <NumberTable label="Rules" columns={columns} rows={state.data.rules} rowKey={(row) => row.rule_id} /> : <EmptyState title="No rules" detail="The rule catalog is empty." />}
      </section>
    </>
  );
}
