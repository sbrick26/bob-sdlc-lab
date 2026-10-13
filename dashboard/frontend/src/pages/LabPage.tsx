import { Renew } from '@carbon/icons-react';
import { Button, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow, Tag } from '@carbon/react';
import { api } from '../api';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, PageError, PageLoading } from '../components/States';
import { StatCard } from '../components/StatCard';
import { useApi } from '../hooks';
import type { LabStatus, LabTicket } from '../types';

const BASELINE_MINUTES = 240;

const statusTag: Record<LabStatus, { label: string; type: 'gray' | 'blue' | 'purple' | 'green' }> = {
  planning: { label: 'Planning', type: 'gray' },
  building: { label: 'Building', type: 'blue' },
  pr_open: { label: 'PR open', type: 'purple' },
  merged: { label: 'Merged', type: 'green' },
};

export function LabPage() {
  const state = useApi(async () => {
    const [board, roi] = await Promise.all([api.labBoard(), api.labRoi(BASELINE_MINUTES)]);
    return { tickets: board.tickets, roi };
  }, []);

  if (state.loading && !state.data) return <PageLoading />;
  if (state.error || !state.data) return <PageError error={state.error || new Error('No lab data returned')} retry={state.reload} />;
  const { tickets, roi } = state.data;
  const { totals, review } = roi;

  return (
    <>
      <PageHeader eyebrow="Bob SDLC lab" title="Lab run" description="Each participant's ticket from plan to merge, with the controls that fired along the way." actions={<Button kind="ghost" size="sm" renderIcon={Renew} onClick={state.reload}>Refresh</Button>} />
      <p className="lab-headline">{roi.headline}</p>

      <section className="kpi-grid" aria-label="Lab outcome summary">
        <StatCard label="Tickets merged" value={`${totals.tickets_merged} / ${totals.tickets}`} detail="Tickets with a merged pull request" signal={totals.tickets_merged ? 'positive' : 'neutral'} />
        <StatCard label="Minutes saved" value={formatNumber(totals.minutes_saved)} detail={`Against a ${roi.baseline_minutes} min manual baseline per ticket${totals.pct_faster == null ? '' : ` (${totals.pct_faster}% faster)`}`} signal={totals.minutes_saved > 0 ? 'positive' : 'neutral'} />
        <StatCard label="Blocks before merge" value={totals.blocks_before_merge} detail="Risky actions stopped before the code reached main" signal={totals.blocks_before_merge ? 'negative' : 'neutral'} />
        <StatCard label="Cost per merged PR" value={totals.cost_per_merged_pr == null ? 'n/a' : `${formatNumber(totals.cost_per_merged_pr)} credits`} detail="Reported usage credits divided by merged pull requests" />
      </section>

      <h2 className="lab-section-title">Review</h2>
      <section className="kpi-grid kpi-grid--three" aria-label="Review summary">
        <StatCard label="First-try pass rate" value={review.first_try_pass_rate_pct == null ? 'n/a' : `${review.first_try_pass_rate_pct}%`} detail={`${review.first_try_passes} of ${review.prs_with_ci} pull requests passed their first CI review`} signal={review.first_try_pass_rate_pct == null ? 'neutral' : review.first_try_pass_rate_pct >= 50 ? 'positive' : 'negative'} />
        <StatCard label="Findings per PR" value={review.findings_per_pr == null ? 'n/a' : review.findings_per_pr} detail="Review findings on the latest CI run, averaged" />
        <StatCard label="PRs reviewed" value={review.prs_with_ci} detail="Pull requests with at least one CI review result" />
      </section>

      <section className="panel lab-people">
        <div className="panel__header"><div><p className="eyebrow">People</p><h2>Participants</h2></div><Tag size="sm" type="blue">{tickets.length} tickets</Tag></div>
        {tickets.length ? <PeopleTable tickets={tickets} /> : <EmptyState title="No lab activity yet" detail="Rows appear when a participant sends the first prompt with a ticket header." />}
      </section>
    </>
  );
}

function PeopleTable({ tickets }: { tickets: LabTicket[] }) {
  return (
    <TableContainer>
      <Table size="md" aria-label="Lab participants">
        <TableHead>
          <TableRow>
            <TableHeader>Name</TableHeader>
            <TableHeader>Ticket</TableHeader>
            <TableHeader>Status</TableHeader>
            <TableHeader className="lab-num">Minutes</TableHeader>
            <TableHeader className="lab-num">Prompts</TableHeader>
            <TableHeader className="lab-num">Blocks</TableHeader>
            <TableHeader>CI first try</TableHeader>
            <TableHeader>Merged</TableHeader>
          </TableRow>
        </TableHead>
        <TableBody>
          {tickets.map((row) => {
            const tag = statusTag[row.status] ?? statusTag.planning;
            return (
              <TableRow key={row.ticket}>
                <TableCell><span className="lab-person"><span className="avatar">{initials(row.user || '?')}</span>{row.user || 'Unknown'}</span></TableCell>
                <TableCell>{row.ticket}{row.pr != null ? ` · PR #${row.pr}` : ''}</TableCell>
                <TableCell><Tag size="sm" type={tag.type}>{tag.label}</Tag></TableCell>
                <TableCell className="lab-num">{row.minutes == null ? '—' : formatNumber(row.minutes)}</TableCell>
                <TableCell className="lab-num">{row.prompts}</TableCell>
                <TableCell className="lab-num">{row.blocks}</TableCell>
                <TableCell>{row.ci.first_try_pass == null ? '—' : <Tag size="sm" type={row.ci.first_try_pass ? 'green' : 'red'}>{row.ci.first_try_pass ? 'Pass' : 'Fail'}</Tag>}</TableCell>
                <TableCell>{row.merged_at ? new Date(row.merged_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function initials(name: string) {
  return name.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'U';
}
