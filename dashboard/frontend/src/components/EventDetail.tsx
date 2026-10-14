import { Close, Copy } from '@carbon/icons-react';
import { Accordion, AccordionItem, Button, InlineLoading, Tag } from '@carbon/react';
import { useState, type ReactNode } from 'react';
import { bobcoins, count } from '../format';
import type { DetailField, EventDetails, EventView, GovernanceEvent } from '../types';
import { Markdown } from './Markdown';

const TONE: Record<string, 'red' | 'purple' | 'green' | 'gray'> = { blocked: 'red', observed: 'purple', allowed: 'green', error: 'gray' };
const LINES = 40;

function copy(text: string) { void navigator.clipboard?.writeText(text); }

function Fields({ items }: { items?: DetailField[] }) {
  if (!items?.length) return null;
  return (
    <dl className="context-list">
      {items.map((item) => (
        <div key={item.label}><dt>{item.label}</dt><dd>{item.href ? <a href={item.href} target={item.href.startsWith('#') ? undefined : '_blank'} rel="noreferrer">{item.value}{item.href.startsWith('#/audit?session') ? ' · View session' : ''}</a> : item.value}</dd></div>
      ))}
    </dl>
  );
}

/** A monospace block with a copy icon; long text shows 40 lines and a "Show all" toggle. */
function Block({ label, text, mono = true, children }: { label: string; text: string; mono?: boolean; children?: ReactNode }) {
  const [all, setAll] = useState(false);
  const lines = text.split('\n');
  const long = lines.length > LINES;
  const shown = long && !all ? lines.slice(0, LINES).join('\n') : text;
  return (
    <div className="detail-content">
      <div className="detail-content__head"><span>{label}</span><Button kind="ghost" size="sm" hasIconOnly renderIcon={Copy} iconDescription={`Copy ${label.toLowerCase()}`} onClick={() => copy(text)} /></div>
      {children ?? (mono ? <pre>{shown}</pre> : <p className="detail-text">{shown}</p>)}
      {long && <button type="button" className="link-button" onClick={() => setAll((value) => !value)}>{all ? 'Show less' : `Show all ${lines.length} lines`}</button>}
    </div>
  );
}

function Pairs({ items }: { items: Array<[string, ReactNode]> }) {
  const shown = items.filter(([, value]) => value !== undefined && value !== null && value !== '');
  return shown.length ? <dl className="context-list">{shown.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl> : null;
}

function Details({ details }: { details: EventDetails }) {
  switch (details.kind) {
    case 'prompt':
      return details.text ? <Block label={`Prompt · ${count(details.chars)} characters`} text={details.text} mono={false} /> : null;
    case 'tool':
      return (
        <>
          <Pairs items={[['Tool', details.tool], ['Tool run time', details.run_time], ['File', details.path]]} />
          {details.command && <Block label="Command" text={details.command} />}
          {details.content && <Block label={details.path ? 'Written content' : 'Input'} text={details.content} />}
          {details.fields && <Pairs items={details.fields.map((field) => [field.label, <code key={field.label}>{field.value}</code>])} />}
          {details.output && <Block label="Tool output" text={details.output} />}
        </>
      );
    case 'stop':
      return (
        <>
          {details.message && <Block label="Bob's answer" text={details.message}><Markdown text={details.message} /></Block>}
          <Pairs items={[['Session Bobcoins so far', details.bobcoins == null ? undefined : bobcoins(details.bobcoins)], ['Turns', details.turns == null ? undefined : count(details.turns)], ['Context tokens', details.tokens == null ? undefined : count(details.tokens)]]} />
        </>
      );
    case 'session':
      return <Pairs items={[['Started by', details.source], ['Workspace', details.workspace]]} />;
    case 'ci':
      return (
        <>
          <Pairs items={[
            ['Verdict', details.verdict ? <Tag size="sm" type={details.verdict === 'PASS' ? 'green' : 'red'}>{details.verdict}</Tag> : undefined],
            ['Criteria met', details.criteria], ['Tests passed', details.tests], ['Findings', details.findings == null ? undefined : count(details.findings)],
            ['Blocking', details.blocking == null ? undefined : count(details.blocking)], ['Duration', details.duration],
          ]} />
          {details.findings_list?.length ? <Block label="Findings" text={details.findings_list.join('\n')}><ul className="findings">{details.findings_list.map((line, index) => <li key={index}>{line}</li>)}</ul></Block> : null}
          <Links pr={details.pr_url} run={details.run_url} />
        </>
      );
    case 'pr':
      return (
        <>
          <Pairs items={[['Title', details.title], ['Pull request', details.pr == null ? undefined : `#${details.pr}`], ['Approver', details.approver], ['Lines changed', details.lines_changed == null ? undefined : count(details.lines_changed)], ['Review rounds', details.review_rounds == null ? undefined : count(details.review_rounds)]]} />
          <Links pr={details.pr_url} />
        </>
      );
    default:
      return null;
  }
}

function Links({ pr, run }: { pr?: string; run?: string }) {
  if (!pr && !run) return null;
  return <p className="detail-links">{pr && <a href={pr} target="_blank" rel="noreferrer">View PR</a>}{run && <a href={run} target="_blank" rel="noreferrer">View CI run</a>}</p>;
}

/** Reviewer view of one event: what happened, the details, why, what to do, then context and technical details. */
export function EventDetail({ event, view, loading, error, onClose }: { event: GovernanceEvent | null; view: EventView | null; loading: boolean; error: string | null; onClose: () => void }) {
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="event-drawer" role="dialog" aria-modal="true" aria-labelledby="event-drawer-title">
        <header className="event-drawer__header">
          <div>
            <h2 id="event-drawer-title">{view?.title ?? 'Event'}</h2>
            {view && <Tag size="sm" type={TONE[view.decision] ?? 'gray'}>{view.status}</Tag>}
          </div>
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Close} iconDescription="Close" onClick={onClose} />
        </header>
        <div className="event-drawer__body">
          {loading && !view && <div className="detail-block"><InlineLoading description="Loading event" /></div>}
          {error && <p className="inline-error" role="alert">{error}</p>}
          {view && (
            <>
              <p className="detail-sentence">{view.sentence}</p>
              {view.details && <section className="detail-block"><h3>Details</h3><Details details={view.details} /></section>}
              {view.attempted && !view.details && <section className="detail-block"><h3>What was attempted</h3><pre>{view.attempted}</pre></section>}
              {view.why && (
                <section className="detail-block">
                  <h3>Why it was stopped</h3>
                  <p>{view.why}</p>
                  {view.rule_id && <p className="rule-ref">{view.rule_url ? <a href={view.rule_url} target="_blank" rel="noreferrer">{view.rule_id}</a> : view.rule_id}</p>}
                </section>
              )}
              {view.remediation && <section className="detail-block"><h3>What to do instead</h3><p>{view.remediation}</p></section>}
              {view.context?.length ? <section className="detail-block"><h3>Context</h3><Fields items={view.context} /></section> : null}
              {view.technical?.length ? (
                <Accordion className="detail-technical"><AccordionItem title="Technical details"><Fields items={view.technical} /></AccordionItem></Accordion>
              ) : null}
            </>
          )}
        </div>
        <footer className="event-drawer__footer">
          <Button kind="tertiary" size="sm" renderIcon={Copy} onClick={() => event && copy(JSON.stringify(event, null, 2))} disabled={!event}>Copy record</Button>
          <Button kind="primary" size="sm" onClick={onClose}>Done</Button>
        </footer>
      </aside>
    </div>
  );
}
