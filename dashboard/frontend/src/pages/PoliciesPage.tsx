import { Add, CheckmarkFilled, CloudUpload, Renew, Save, WarningAltFilled } from '@carbon/icons-react';
import { Button, InlineNotification, Tag, TextInput, Toggle } from '@carbon/react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { PageHeader } from '../components/PageHeader';
import { PageError, PageLoading } from '../components/States';
import { useApi } from '../hooks';
import {
  applySavedMetadata,
  initialWorkflow,
  policyFingerprint,
  policyReadiness,
  rolloutPresentation,
  type PolicyWorkflowState,
} from '../policyWorkflow';
import type { PolicyDraft, PolicyRule, Rollout } from '../types';

type Notice = { kind: 'success' | 'error' | 'info'; title: string; subtitle: string } | null;

export function PoliciesPage() {
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [editorDraft, setEditorDraft] = useState<PolicyDraft | null>(null);
  const [workflow, setWorkflow] = useState<PolicyWorkflowState | null>(null);
  const state = useApi(async () => {
    const catalog = await api.policies();
    const [draft, rollout] = await Promise.all([
      api.policyDraft().catch((): PolicyDraft => ({ ...catalog, revision: '1', rules: catalog.rules.map((rule) => ({ ...rule, enabled: rule.enabled ?? true })) })),
      api.latestRollout().catch(() => ({ status: 'not_started' as const })),
    ]);
    return { catalog, draft, rollout };
  }, []);

  useEffect(() => {
    if (state.loading || !state.data || editorDraft) return;
    setEditorDraft(state.data.draft);
    setWorkflow(initialWorkflow(state.data.draft));
  }, [editorDraft, state.data, state.loading]);

  const readiness = useMemo(
    () => editorDraft && workflow ? policyReadiness(editorDraft, workflow) : null,
    [editorDraft, workflow],
  );

  useEffect(() => {
    if (!readiness?.dirty) return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [readiness?.dirty]);

  if (state.error) return <PageError error={state.error} retry={state.reload} />;
  if (state.loading || !editorDraft || !workflow || !readiness) return <PageLoading />;
  if (!state.data) return <PageError error={new Error('No policy catalog returned')} retry={state.reload} />;

  const { catalog, rollout } = state.data;
  const draft = editorDraft;
  const updateRule = (ruleId: string, update: Partial<PolicyRule>) => {
    setEditorDraft((current) => current ? { ...current, rules: current.rules.map((rule) => rule.rule_id === ruleId ? { ...rule, ...update } : rule) } : current);
    setNotice(null);
  };
  const updateAllowlist = (ecosystem: string, packages: string[]) => {
    const packageRule = draft.rules.find((rule) => rule.rule_id === 'GOV-PKG-001');
    if (!packageRule) return;
    const configuration = packageRule.configuration ?? {};
    const allowlist = (configuration.allowlist as Record<string, string[]> | undefined) ?? {};
    updateRule(packageRule.rule_id, { configuration: { ...configuration, allowlist: { ...allowlist, [ecosystem]: packages } } });
  };
  const fail = (name: string, value: unknown) => setNotice({
    kind: 'error',
    title: `${name} failed`,
    subtitle: value instanceof Error ? value.message : 'The request could not be completed.',
  });
  const save = async () => {
    if (!readiness.canSave) return;
    const submitted = draft;
    const submittedFingerprint = policyFingerprint(submitted);
    setBusy('Save draft'); setNotice(null);
    try {
      const saved = await api.saveDraft(submitted);
      setEditorDraft((current) => current ? applySavedMetadata(current, saved) : current);
      setWorkflow({
        savedFingerprint: submittedFingerprint,
        savedRevision: saved.revision,
        validatedFingerprint: null,
        validatedRevision: null,
      });
      setNotice({ kind: 'success', title: 'Draft saved', subtitle: `Revision ${saved.revision} is ready for validation.` });
    } catch (value) { fail('Save draft', value); }
    finally { setBusy(null); }
  };
  const validate = async () => {
    if (!readiness.canValidate) return;
    const candidate = draft;
    const candidateFingerprint = policyFingerprint(candidate);
    const candidateRevision = workflow.savedRevision;
    setBusy('Validate'); setNotice(null);
    try {
      const result = await api.validatePolicy(candidate);
      if (!result.valid) throw new Error(result.errors?.map((error) => typeof error === 'string' ? error : `${error.path}: ${error.message}`).join(' ') || 'Validation failed.');
      setWorkflow((current) => current ? {
        ...current,
        validatedFingerprint: candidateFingerprint,
        validatedRevision: candidateRevision,
      } : current);
      setNotice({ kind: 'success', title: 'Policy valid', subtitle: `Saved revision ${candidateRevision} passed validation.` });
    } catch (value) { fail('Validate', value); }
    finally { setBusy(null); }
  };
  const publish = async () => {
    if (!readiness.canPublish) return;
    const revision = workflow.savedRevision;
    setBusy('Publish'); setNotice(null);
    try {
      const nextRollout = await api.publishPolicy(revision);
      state.setData((current) => current ? { ...current, rollout: nextRollout } : current);
      const presentation = rolloutPresentation(nextRollout);
      setNotice({ kind: nextRollout.status === 'failed' || nextRollout.status === 'configuration_required' ? 'error' : 'success', title: presentation.label, subtitle: presentation.detail });
    } catch (value) { fail('Publish', value); }
    finally { setBusy(null); }
  };
  const refresh = () => {
    if (readiness.dirty || busy) return;
    setEditorDraft(null); setWorkflow(null); setNotice(null);
    void state.reload();
  };

  return (
    <>
      <PageHeader eyebrow="Policy administration" title="Policies" description="Manage enforcement rules as a draft, validate changes, and publish a controlled policy version." actions={<Button kind="ghost" size="sm" renderIcon={Renew} disabled={readiness.dirty || busy !== null} onClick={refresh}>Refresh</Button>} />
      {notice && <InlineNotification className="policy-notice" kind={notice.kind} title={notice.title} subtitle={notice.subtitle} onClose={() => setNotice(null)} lowContrast />}
      <section className="policy-status">
        <div><p className="eyebrow">Active version</p><strong>{catalog.policy_version}</strong><span>Current policy is active</span></div>
        <div><p className="eyebrow">Draft revision</p><strong>{workflow.savedRevision}</strong><span>{readiness.dirty ? 'Unsaved changes' : draft.updated_at ? `Saved ${new Date(draft.updated_at).toLocaleString()}` : 'Saved'}</span></div>
        <RolloutStatus rollout={rollout} />
        <div className="policy-status__actions">
          <Button size="sm" kind="tertiary" renderIcon={Save} disabled={busy !== null || !readiness.canSave} onClick={save}>Save draft</Button>
          <Button size="sm" kind="secondary" renderIcon={CheckmarkFilled} disabled={busy !== null || !readiness.canValidate} onClick={validate}>Validate</Button>
          <Button size="sm" kind="primary" renderIcon={CloudUpload} disabled={busy !== null || !readiness.canPublish} onClick={publish}>Publish</Button>
        </div>
      </section>
      <div className="policy-layout">
        <section className="policy-editor">
          <header className="policy-editor__header"><div><p className="eyebrow">Draft controls</p><h2>{draft.rules.length} rules</h2></div><span>{readiness.dirty ? 'Unsaved changes' : readiness.validated ? `Revision ${workflow.savedRevision} validated` : `Revision ${workflow.savedRevision} saved · validation required`}</span></header>
          {draft.rules.map((rule) => <RuleEditor key={rule.rule_id} rule={rule} onChange={(update) => updateRule(rule.rule_id, update)} onAllowlistChange={updateAllowlist} />)}
        </section>
        <aside className="publish-checklist">
          <p className="eyebrow">Publish readiness</p><h2>Change review</h2>
          <ChecklistItem label="Draft" value={readiness.dirty ? 'Save required' : `Revision ${workflow.savedRevision}`} ready={!readiness.dirty} />
          <ChecklistItem label="Validation" value={readiness.validated ? 'Passed' : 'Required'} ready={readiness.validated} />
          <ChecklistItem label="Package controls" value={draft.rules.some((rule) => rule.rule_id === 'GOV-PKG-001' && rule.enabled !== false) ? 'Enabled' : 'Disabled'} ready={draft.rules.some((rule) => rule.rule_id === 'GOV-PKG-001' && rule.enabled !== false)} />
          <ChecklistItem label="Active baseline" value={`Version ${catalog.policy_version}`} ready />
          <p className="publish-note">Publish uses the exact saved revision shown here. Any edit requires a new save and validation.</p>
        </aside>
      </div>
    </>
  );
}

function RuleEditor({ rule, onChange, onAllowlistChange }: { rule: PolicyRule; onChange: (update: Partial<PolicyRule>) => void; onAllowlistChange: (ecosystem: string, packages: string[]) => void }) {
  const allowlist = useMemo(() => (rule.configuration?.allowlist as Record<string, string[]> | undefined) ?? {}, [rule.configuration]);
  return (
    <article className={`rule-editor${rule.enabled === false ? ' rule-editor--disabled' : ''}`}>
      <div className="rule-editor__identity"><Tag type="blue" size="sm">{rule.rule_id}</Tag><div><h3>{rule.name}</h3><p>{rule.description}</p></div></div>
      <div className="rule-editor__control"><Tag type={rule.decision === 'blocked' ? 'red' : 'purple'} size="sm">{rule.decision}</Tag><Toggle id={`toggle-${rule.rule_id}`} size="sm" labelText={`Enable ${rule.name}`} labelA="Off" labelB="On" toggled={rule.enabled !== false} onToggle={(enabled) => onChange({ enabled })} hideLabel /></div>
      <dl className="rule-editor__metadata"><div><dt>Control points</dt><dd>{rule.events.join(', ')}</dd></div><div><dt>Enforcement</dt><dd>{humanize(rule.enforcement)}</dd></div><div><dt>Severity</dt><dd>{rule.severity}</dd></div></dl>
      {rule.rule_id === 'GOV-PKG-001' && <div className="allowlists"><AllowlistEditor label="Python packages" ecosystem="python" packages={allowlist.python ?? []} onChange={onAllowlistChange} /><AllowlistEditor label="Node.js packages" ecosystem="node" packages={allowlist.node ?? []} onChange={onAllowlistChange} /></div>}
    </article>
  );
}

function AllowlistEditor({ label, ecosystem, packages, onChange }: { label: string; ecosystem: string; packages: string[]; onChange: (ecosystem: string, packages: string[]) => void }) {
  const [value, setValue] = useState('');
  const add = () => { const item = value.trim().toLowerCase(); if (item && !packages.includes(item)) onChange(ecosystem, [...packages, item].sort()); setValue(''); };
  return <div className="allowlist"><label>{label}</label><div className="tag-field">{packages.map((item) => <Tag key={item} type="gray" size="sm" filter onClose={() => onChange(ecosystem, packages.filter((value) => value !== item))}>{item}</Tag>)}</div><div className="allowlist__add"><TextInput id={`add-${ecosystem}`} size="sm" labelText={`Add ${ecosystem} package`} hideLabel placeholder="Package name" value={value} onChange={(event) => setValue(event.currentTarget.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); add(); } }} /><Button kind="ghost" size="sm" hasIconOnly renderIcon={Add} iconDescription={`Add ${ecosystem} package`} onClick={add} /></div></div>;
}

function RolloutStatus({ rollout }: { rollout: Rollout }) {
  const presentation = rolloutPresentation(rollout);
  return <div><p className="eyebrow">Latest rollout</p><strong className={`rollout rollout--${rollout.status}`}><span />{presentation.label}</strong><span>{rollout.policy_version ? `Version ${rollout.policy_version} · ${presentation.detail}` : presentation.detail}</span></div>;
}

function ChecklistItem({ label, value, ready }: { label: string; value: string; ready: boolean }) { const Icon = ready ? CheckmarkFilled : WarningAltFilled; return <div className={`checklist-item${ready ? '' : ' checklist-item--pending'}`}><Icon size={18} /><span>{label}</span><strong>{value}</strong></div>; }
function humanize(value: string) { return value.replace('exit 2', 'Block').replace('before model', 'before model processing').replace('before tool', 'before tool execution').replace('record only', 'Observe').replace('next-turn context', 'Add finding to next turn'); }
