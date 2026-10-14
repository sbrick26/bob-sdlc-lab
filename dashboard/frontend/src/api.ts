import type { Facets, GovernanceEvent, OverviewSummary, RuleSummary, UsageSummary, ViolationsSummary } from './types';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

/** Minutes behind UTC, so the server buckets days on the viewer's local clock. */
const tzOffset = () => new Date().getTimezoneOffset();

export const api = {
  overview: () => request<OverviewSummary>(`/api/v1/overview/summary?tz_offset=${tzOffset()}`),
  violations: () => request<ViolationsSummary>(`/api/v1/violations/summary?tz_offset=${tzOffset()}`),
  usage: () => request<UsageSummary>('/api/v1/usage/summary'),
  rules: () => request<{ count: number; rules: RuleSummary[] }>('/api/v1/rules/summary'),
  events: (params = new URLSearchParams()) => request<{ count: number; events: GovernanceEvent[] }>(`/api/v1/events?${params}`),
  event: async (eventId: string) => (await request<{ event: GovernanceEvent }>(`/api/v1/events/${encodeURIComponent(eventId)}`)).event,
  facets: () => request<Facets>('/api/v1/facets'),
  csvUrl: (params: URLSearchParams) => `/api/v1/events.csv?${params}`,
};
