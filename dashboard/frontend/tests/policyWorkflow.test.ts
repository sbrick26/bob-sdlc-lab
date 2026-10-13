import assert from 'node:assert/strict';
import test from 'node:test';
import {
  applySavedMetadata,
  initialWorkflow,
  policyFingerprint,
  policyReadiness,
  rolloutPresentation,
} from '../src/policyWorkflow.ts';
import type { PolicyDraft } from '../src/types.ts';

function draft(): PolicyDraft {
  return {
    policy_version: '1.2.0',
    revision: '4',
    rules: [{
      rule_id: 'GOV-PKG-001',
      name: 'Package allowlist',
      description: 'Controls package installation.',
      events: ['PreToolUse'],
      decision: 'blocked',
      severity: 'high',
      enforcement: 'exit 2 before tool',
      enabled: true,
      configuration: { allowlist: { python: ['requests'] } },
    }],
  };
}

test('publish readiness belongs to the exact saved and validated revision', () => {
  const original = draft();
  const workflow = initialWorkflow(original);
  assert.deepEqual(policyReadiness(original, workflow), {
    dirty: false, validated: false, canSave: false, canValidate: true, canPublish: false,
  });

  const edited = structuredClone(original);
  edited.rules[0].enabled = false;
  assert.deepEqual(policyReadiness(edited, workflow), {
    dirty: true, validated: false, canSave: true, canValidate: false, canPublish: false,
  });

  const fingerprint = policyFingerprint(edited);
  const savedWorkflow = { ...workflow, savedFingerprint: fingerprint, savedRevision: '5' };
  const saved = { ...edited, revision: '5' };
  assert.equal(policyReadiness(saved, savedWorkflow).canValidate, true);

  const validatedWorkflow = { ...savedWorkflow, validatedFingerprint: fingerprint, validatedRevision: '5' };
  assert.equal(policyReadiness(saved, validatedWorkflow).canPublish, true);
  saved.rules[0].enabled = true;
  assert.equal(policyReadiness(saved, validatedWorkflow).canPublish, false);
});

test('save response updates server metadata without discarding newer editor changes', () => {
  const current = draft();
  current.rules[0].enabled = false;
  const server = { ...draft(), revision: '8', updated_at: '2026-08-25T08:00:00Z', updated_by: 'admin' };
  const merged = applySavedMetadata(current, server);
  assert.equal(merged.revision, '8');
  assert.equal(merged.rules[0].enabled, false);
  assert.equal(merged.updated_by, 'admin');
});

test('fingerprints are stable for configuration key ordering', () => {
  const left = draft();
  const right = draft();
  left.rules[0].configuration = { z: true, allowlist: { python: ['requests'] } };
  right.rules[0].configuration = { allowlist: { python: ['requests'] }, z: true };
  assert.equal(policyFingerprint(left), policyFingerprint(right));
});

test('rollout labels do not claim deployment before confirmation', () => {
  assert.equal(rolloutPresentation({ status: 'publishing' }).label, 'Sync requested');
  assert.equal(rolloutPresentation({ status: 'succeeded' }).label, 'Profile submitted');
  assert.equal(rolloutPresentation({ status: 'deployed' }).label, 'Deployed');
  assert.equal(rolloutPresentation({ status: 'configuration_required' }).label, 'Setup required');
  assert.equal(rolloutPresentation({ status: 'failed' }).label, 'Rollout failed');
});
