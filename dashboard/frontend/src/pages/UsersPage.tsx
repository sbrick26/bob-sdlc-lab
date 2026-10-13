import { SimpleBarChart } from '@carbon/charts-react';
import { DataTable, ProgressBar, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow, Tag } from '@carbon/react';
import { useMemo } from 'react';
import { api } from '../api';
import { PageHeader } from '../components/PageHeader';
import { PageError, PageLoading, EmptyState } from '../components/States';
import { StatCard } from '../components/StatCard';
import { useApi } from '../hooks';

export function UsersPage() {
  const state = useApi(async () => {
    const [analytics, fleet] = await Promise.all([api.analytics(30), api.fleet()]);
    return { analytics, fleet: fleet.devices };
  }, []);
  const chartData = useMemo(() => state.data?.analytics.top_users.slice(0, 8).map((user) => ({ group: 'Blocked', key: user.user_name, value: user.blocked })) ?? [], [state.data]);
  if (state.loading) return <PageLoading />;
  if (state.error || !state.data) return <PageError error={state.error || new Error('No user data returned')} retry={state.reload} />;
  const { analytics, fleet } = state.data;
  const headers = [
    { key: 'user_name', header: 'User' }, { key: 'device_name', header: 'Device' }, { key: 'policy_version', header: 'Policy' },
    { key: 'bob_version', header: 'Bob version' }, { key: 'event_count', header: 'Decisions' }, { key: 'blocked_count', header: 'Blocked' }, { key: 'last_seen', header: 'Last active' },
  ];
  const rows = fleet.map((device, index) => ({ ...device, id: `${device.device_name}-${index}`, bob_version: device.bob_version || '—', last_seen: new Date(device.last_seen).toLocaleString() }));
  return (
    <>
      <PageHeader eyebrow="People and coverage" title="Users" description="Compare policy exposure by user and confirm managed devices are reporting current controls." />
      <section className="kpi-grid kpi-grid--three">
        <StatCard label="Active users" value={analytics.overall.reporting_users} detail="Users reporting decisions in the last 30 days" />
        <StatCard label="Users with blocks" value={analytics.overall.users_with_blocks} detail="Users affected by at least one enforced rule" signal={analytics.overall.users_with_blocks ? 'negative' : 'positive'} />
        <StatCard label="Highest user block rate" value={`${analytics.overall.highest_user_block_rate_pct}%`} detail="Highest individual rate across evaluated actions" />
      </section>
      <section className="overview-grid users-grid">
        <article className="panel">
          <div className="panel__header"><div><p className="eyebrow">Exposure</p><h2>Blocked actions by user</h2></div></div>
          {chartData.some((item) => item.value > 0) ? <SimpleBarChart data={chartData} options={{ height: '360px', theme: 'g10', axes: { left: { mapsTo: 'key', scaleType: 'labels' }, bottom: { mapsTo: 'value', scaleType: 'linear' } }, legend: { enabled: false }, toolbar: { enabled: false }, animations: false } as never} /> : <EmptyState title="No blocked actions" detail="No users were affected during this period." />}
        </article>
        <article className="panel">
          <div className="panel__header"><div><p className="eyebrow">User posture</p><h2>Activity and block rate</h2></div></div>
          <div className="user-list">
            {analytics.top_users.map((user) => (
              <div className="user-card" key={user.user_name}>
                <div className="user-card__heading"><div className="avatar">{initials(user.user_name)}</div><div><strong>{user.user_name}</strong><span>{user.total} recorded decisions</span></div><Tag size="sm" type={user.blocked ? 'red' : 'green'}>{user.blocked ? `${user.blocked} blocked` : 'Clear'}</Tag></div>
                <div className="user-card__rate"><span>Block rate</span><strong>{user.blocked_rate_pct ?? 0}%</strong></div>
                <ProgressBar value={user.blocked_rate_pct ?? 0} max={100} size="small" label={`${user.user_name} block rate`} hideLabel />
              </div>
            ))}
          </div>
        </article>
      </section>
      <section className="panel fleet-panel">
        <div className="panel__header"><div><p className="eyebrow">Coverage</p><h2>Reporting devices</h2></div><Tag size="sm" type="blue">{fleet.length} devices</Tag></div>
        <DataTable rows={rows} headers={headers} isSortable>
          {({ rows: tableRows, headers: tableHeaders, getHeaderProps, getRowProps, getTableProps }) => <TableContainer><Table {...getTableProps()} size="md"><TableHead><TableRow>{tableHeaders.map((header) => <TableHeader {...getHeaderProps({ header })} key={header.key}>{header.header}</TableHeader>)}</TableRow></TableHead><TableBody>{tableRows.map((row) => <TableRow {...getRowProps({ row })} key={row.id}>{row.cells.map((cell) => <TableCell key={cell.id}>{String(cell.value)}</TableCell>)}</TableRow>)}</TableBody></Table></TableContainer>}
        </DataTable>
      </section>
    </>
  );
}

function initials(name: string) {
  return name.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'U';
}
