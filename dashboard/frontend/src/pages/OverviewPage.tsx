import { ArrowRight, Renew } from '@carbon/icons-react';
import { LineChart, SimpleBarChart } from '@carbon/charts-react';
import { Button, Dropdown, ProgressBar, Tag } from '@carbon/react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { EventDetail } from '../components/EventDetail';
import { EventTable } from '../components/EventTable';
import { PageHeader } from '../components/PageHeader';
import { PageError, PageLoading, EmptyState } from '../components/States';
import { StatCard } from '../components/StatCard';
import { useApi } from '../hooks';
import type { GovernanceEvent } from '../types';

const ranges = [7, 30, 90];

export function OverviewPage() {
  const [days, setDays] = useState(30);
  const [selected, setSelected] = useState<GovernanceEvent | null>(null);
  const navigate = useNavigate();
  const state = useApi(async () => {
    const [analytics, events] = await Promise.all([api.analytics(days), api.events(new URLSearchParams({ limit: '20' }))]);
    return { analytics, events: events.events };
  }, [days]);

  const decisionData = useMemo(() => state.data?.analytics.timeline.flatMap((bucket) => [
    { group: 'Blocked', date: new Date(bucket.bucket), value: bucket.blocked },
    { group: 'Allowed', date: new Date(bucket.bucket), value: bucket.allowed },
  ]) ?? [], [state.data]);
  const ruleData = useMemo(() => state.data?.analytics.rules.slice(0, 6).map((rule) => ({ group: 'Findings', key: rule.rule_name || rule.rule_id, value: rule.total })) ?? [], [state.data]);

  if (state.loading) return <PageLoading />;
  if (state.error || !state.data) return <PageError error={state.error || new Error('No analytics returned')} retry={state.reload} />;
  const { analytics, events } = state.data;
  const highSignal = events.filter((event) => event.decision !== 'allowed').slice(0, 8);
  const recent = highSignal.length ? highSignal : events.slice(0, 8);
  const toolLatency = analytics.overall.avg_tool_duration_ms;

  return (
    <>
      <PageHeader eyebrow="Governance posture" title="Decisions that need attention" description="Enforcement activity across people, tools, and managed policy controls." actions={
        <><Dropdown id="overview-range" label="Reporting period" titleText="Period" items={ranges} selectedItem={days} itemToString={(item) => item ? `Last ${item} days` : ''} onChange={({ selectedItem }) => setDays(selectedItem ?? 30)} size="sm" /><Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button></>
      } />

      <section className="kpi-grid" aria-label="Governance posture summary">
        <StatCard label="Evaluated actions" value={analytics.overall.enforceable_total.toLocaleString()} detail="Prompts and tool requests evaluated before execution" />
        <StatCard label="Blocked" value={analytics.overall.blocked.toLocaleString()} detail={`${analytics.overall.blocked_rate_pct}% of enforceable actions`} signal={analytics.overall.blocked > 0 ? 'negative' : 'positive'} />
        <StatCard label="Affected users" value={analytics.overall.users_with_blocks.toLocaleString()} detail={`${analytics.overall.reporting_users} active users · ${analytics.overall.reporting_devices} devices`} />
        <StatCard label="Evaluation time" value={analytics.overall.avg_policy_duration_ms == null ? '—' : `${analytics.overall.avg_policy_duration_ms} ms`} detail={`${analytics.overall.policy_duration_samples.toLocaleString()} measured evaluations`} />
      </section>

      <section className="overview-grid">
        <article className="panel panel--wide">
          <div className="panel__header"><div><p className="eyebrow">Decision volume</p><h2>Enforcement over time</h2></div><Tag size="sm" type="gray">{analytics.window.granularity}</Tag></div>
          {decisionData.length ? <LineChart data={decisionData} options={{ height: '310px', theme: 'g10', axes: { bottom: { mapsTo: 'date', scaleType: 'time' }, left: { mapsTo: 'value', scaleType: 'linear', title: 'Actions' } }, curve: 'curveMonotoneX', points: { enabled: false }, legend: { alignment: 'center' }, toolbar: { enabled: false }, animations: false } as never} /> : <EmptyState title="No decisions yet" detail="Activity appears after the first policy evaluation." />}
        </article>
        <article className="panel">
          <div className="panel__header"><div><p className="eyebrow">Control impact</p><h2>Top violated rules</h2></div></div>
          {ruleData.length ? <SimpleBarChart data={ruleData} options={{ height: '310px', theme: 'g10', axes: { left: { mapsTo: 'key', scaleType: 'labels' }, bottom: { mapsTo: 'value', scaleType: 'linear' } }, legend: { enabled: false }, toolbar: { enabled: false }, animations: false } as never} /> : <EmptyState title="No rule violations" detail="The selected period has no findings." />}
        </article>
      </section>

      <section className="overview-grid overview-grid--lower">
        <article className="panel">
          <div className="panel__header"><div><p className="eyebrow">People</p><h2>Users with highest exposure</h2></div><Button kind="ghost" size="sm" renderIcon={ArrowRight} onClick={() => navigate('/users')}>View users</Button></div>
          <div className="rank-list">
            {analytics.top_users.slice(0, 6).map((user) => (
              <div className="rank-row" key={user.user_name}>
                <div><strong>{user.user_name}</strong><span>{user.blocked} blocked of {user.enforceable_total} evaluated</span></div>
                <div className="rank-row__meter"><span>{user.blocked_rate_pct ?? 0}%</span><ProgressBar value={user.blocked_rate_pct ?? 0} max={100} size="small" label={`${user.user_name} block rate`} hideLabel /></div>
              </div>
            ))}
            {!analytics.top_users.length && <EmptyState title="No active users" detail="User activity will appear here." />}
          </div>
        </article>
        <article className="panel">
          <div className="panel__header"><div><p className="eyebrow">Tool performance</p><h2>Observed tool duration</h2></div></div>
          <div className="latency-hero"><strong>{toolLatency == null ? 'Not measured' : `${toolLatency} ms`}</strong><span>Average across {analytics.overall.tool_duration_samples.toLocaleString()} paired tool measurements</span></div>
          <div className="tool-list">
            {analytics.tools.filter((tool) => tool.duration_samples > 0).slice(0, 5).map((tool) => <div key={tool.tool_name}><span>{tool.tool_name}</span><strong>{tool.avg_tool_duration_ms} ms</strong><small>{tool.duration_samples} samples</small></div>)}
            {!analytics.tools.some((tool) => tool.duration_samples > 0) && <p className="muted">No paired tool measurements in this period.</p>}
          </div>
        </article>
      </section>

      <section className="panel activity-preview">
        <div className="panel__header"><div><p className="eyebrow">Recent activity</p><h2>{highSignal.length ? 'Findings and blocks' : 'Latest decisions'}</h2></div><Button kind="ghost" size="sm" renderIcon={ArrowRight} onClick={() => navigate('/activity')}>Open activity</Button></div>
        <EventTable events={recent} onSelect={setSelected} compact />
      </section>
      {selected && <EventDetail event={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
