import { Close, Copy } from '@carbon/icons-react';
import { Button } from '@carbon/react';
import type { GovernanceEvent } from '../types';
import { DecisionTag } from './DecisionTag';

const sections = [
  ['Prompt', 'prompt_content'],
  ['Tool input', 'tool_input_content'],
  ['Tool output', 'tool_output_content'],
  ['Response', 'response_content'],
] as const;

export function EventDetail({ event, onClose }: { event: GovernanceEvent; onClose: () => void }) {
  const copyEvent = () => navigator.clipboard.writeText(JSON.stringify(event, null, 2));
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="event-drawer" role="dialog" aria-modal="true" aria-labelledby="event-drawer-title">
        <header className="event-drawer__header">
          <div>
            <p className="eyebrow">Decision record</p>
            <h2 id="event-drawer-title">{event.rule_name || event.hook_event}</h2>
          </div>
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Close} iconDescription="Close details" onClick={onClose} />
        </header>
        <div className="event-drawer__body">
          <div className="event-drawer__decision"><DecisionTag decision={event.decision} /><span>{new Date(event.occurred_at).toLocaleString()}</span></div>
          <dl className="metadata-grid">
            <div><dt>Rule</dt><dd>{event.rule_id || 'No finding'}</dd></div>
            <div><dt>Severity</dt><dd>{event.severity}</dd></div>
            <div><dt>User</dt><dd>{event.user_name}</dd></div>
            <div><dt>Device</dt><dd>{event.device_name}</dd></div>
            <div><dt>Workspace</dt><dd>{event.workspace || '—'}</dd></div>
            <div><dt>Hook</dt><dd>{event.hook_event}</dd></div>
            <div><dt>Tool</dt><dd>{event.tool_name || '—'}</dd></div>
            <div><dt>Evaluation time</dt><dd>{event.duration_ms == null ? 'Not measured' : `${event.duration_ms} ms`}</dd></div>
            <div><dt>Observed tool duration</dt><dd>{event.tool_duration_ms == null ? 'Not measured' : `${event.tool_duration_ms} ms`}</dd></div>
            {event.lab_ticket && <div><dt>Ticket</dt><dd>{event.lab_ticket}</dd></div>}
            {event.lab_role && <div><dt>Lab role</dt><dd>{event.lab_role}</dd></div>}
            {event.lab_branch && <div><dt>Branch</dt><dd>{event.lab_branch}</dd></div>}
            {event.lab_path && <div><dt>File</dt><dd>{event.lab_path}</dd></div>}
            {event.lab_pr != null && <div><dt>Pull request</dt><dd>#{event.lab_pr}</dd></div>}
            <div><dt>Outcome</dt><dd>{event.outcome?.replaceAll('_', ' ') || '—'}</dd></div>
          </dl>
          {(event.detail || event.evidence) && <section className="detail-block"><h3>Finding</h3><p>{event.detail || event.evidence}</p></section>}
          {sections.map(([label, key]) => event[key] ? (
            <section className="detail-block" key={key}><h3>{label}</h3><pre>{event[key]}</pre></section>
          ) : null)}
        </div>
        <footer className="event-drawer__footer">
          <Button kind="tertiary" size="sm" renderIcon={Copy} onClick={copyEvent}>Copy record</Button>
          <Button kind="primary" size="sm" onClick={onClose}>Done</Button>
        </footer>
      </aside>
    </div>
  );
}
