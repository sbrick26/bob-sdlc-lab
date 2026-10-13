import type { PolicyDraft, Rollout } from './types';

export interface PolicyWorkflowState {
  savedFingerprint: string;
  savedRevision: string;
  validatedFingerprint: string | null;
  validatedRevision: string | null;
}

export interface PolicyReadiness {
  dirty: boolean;
  validated: boolean;
  canSave: boolean;
  canValidate: boolean;
  canPublish: boolean;
}

export function policyFingerprint(draft: PolicyDraft): string {
  return stableStringify(policyConfig(draft));
}

export function policyConfig(draft: PolicyDraft) {
  return {
    name: 'Bob Governance',
    rules: draft.rules.map(({ rule_id, enabled = true, configuration }) => ({
      rule_id, enabled, ...(configuration ? { configuration } : {}),
    })),
    offline: draft.offline,
    content: draft.content,
  };
}

export function initialWorkflow(draft: PolicyDraft): PolicyWorkflowState {
  return {
    savedFingerprint: policyFingerprint(draft),
    savedRevision: draft.revision,
    validatedFingerprint: null,
    validatedRevision: null,
  };
}

export function policyReadiness(draft: PolicyDraft, workflow: PolicyWorkflowState): PolicyReadiness {
  const fingerprint = policyFingerprint(draft);
  const dirty = fingerprint !== workflow.savedFingerprint;
  const validated = !dirty
    && workflow.validatedFingerprint === fingerprint
    && workflow.validatedRevision === workflow.savedRevision
    && draft.revision === workflow.savedRevision;
  return {
    dirty,
    validated,
    canSave: dirty,
    canValidate: !dirty && draft.revision === workflow.savedRevision,
    canPublish: validated,
  };
}

/** Apply server-owned metadata without replacing edits made while the save was in flight. */
export function applySavedMetadata(current: PolicyDraft, saved: PolicyDraft): PolicyDraft {
  return {
    ...current,
    revision: saved.revision,
    updated_at: saved.updated_at,
    updated_by: saved.updated_by,
  };
}

export function rolloutPresentation(rollout: Rollout): { label: string; detail: string } {
  const detail = rollout.error || rollout.message;
  switch (rollout.status) {
    case 'not_started':
      return { label: 'No rollout yet', detail: 'Publish a validated draft' };
    case 'pending':
      return { label: 'Publish queued', detail: detail || 'Waiting to submit the managed profile' };
    case 'validating':
      return { label: 'Validating publish', detail: detail || 'Checking the saved policy revision' };
    case 'publishing':
      return { label: 'Sync requested', detail: detail || 'Submitting the profile update to device management' };
    case 'succeeded':
      return { label: 'Profile submitted', detail: detail || 'Device management accepted the update; installation is not yet confirmed' };
    case 'deployed':
      return { label: 'Deployed', detail: detail || 'Managed devices confirmed the policy version' };
    case 'configuration_required':
      return { label: 'Setup required', detail: detail || 'Complete the device-management configuration before publishing' };
    case 'failed':
      return { label: 'Rollout failed', detail: detail || 'The profile update was not accepted' };
  }
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => left.localeCompare(right));
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${stableStringify(item)}`).join(',')}}`;
  }
  return JSON.stringify(value);
}
