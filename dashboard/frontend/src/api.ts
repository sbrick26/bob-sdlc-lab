import type { Analytics, Facets, FleetDevice, GovernanceEvent, PolicyCatalog, PolicyDraft, Rollout } from './types';
import { policyConfig } from './policyWorkflow';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  analytics: (days = 30) => request<Analytics>(`/api/v1/analytics?days=${days}&granularity=auto`),
  events: (params = new URLSearchParams()) => request<{ count: number; events: GovernanceEvent[] }>(`/api/v1/events?${params}`),
  event: async (eventId: string) => (await request<{ event: GovernanceEvent }>(`/api/v1/events/${encodeURIComponent(eventId)}`)).event,
  facets: () => request<Facets>('/api/v1/facets'),
  fleet: () => request<{ count: number; devices: FleetDevice[] }>('/api/v1/fleet'),
  policies: () => request<PolicyCatalog>('/api/v1/policies'),
  policyDraft: () => request<PolicyDraft>('/api/v1/policy/draft'),
  saveDraft: (draft: PolicyDraft) => request<PolicyDraft>('/api/v1/policy/draft', {
    method: 'PUT',
    body: JSON.stringify({ expected_revision: draft.revision, config: policyConfig(draft) }),
  }),
  validatePolicy: (draft: PolicyDraft) => request<{ valid: boolean; errors?: Array<string | { path: string; message: string }> }>('/api/v1/policy/validate', {
    method: 'POST',
    body: JSON.stringify({ expected_revision: draft.revision, config: policyConfig(draft) }),
  }),
  publishPolicy: async (revision: string) => {
    const result = await request<{ rollout: Rollout }>('/api/v1/policy/publish', {
      method: 'POST', body: JSON.stringify({ expected_revision: revision }),
    });
    return result.rollout;
  },
  latestRollout: async () => (await request<{ rollout: Rollout | null }>('/api/v1/rollouts/latest')).rollout ?? { status: 'not_started' as const },
};
