import type { SessionSummary, CostSummary, DeliverySummary, EventView, Facets, GovernanceEvent, OverviewSummary, PerformanceSummary, RulesSummary, ViolationsSummary } from './types';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

const tz = () => String(new Date().getTimezoneOffset());

export const api = {
  overview: (params: URLSearchParams) => request<OverviewSummary>(`/api/v1/overview/summary?${params}`),
  cost: (params: URLSearchParams) => request<CostSummary>(`/api/v1/cost/summary?${params}`),
  delivery: (params: URLSearchParams) => request<DeliverySummary>(`/api/v1/delivery/summary?${params}`),
  performance: (params: URLSearchParams) => request<PerformanceSummary>(`/api/v1/performance/summary?${params}`),
  violations: (params: URLSearchParams) => request<ViolationsSummary>(`/api/v1/violations/summary?${params}`),
  rules: (params: URLSearchParams) => request<RulesSummary>(`/api/v1/rules/summary?${params}`),
  events: (params: URLSearchParams) => request<{ count: number; events: GovernanceEvent[] }>(`/api/v1/events?${params}`),
  event: (eventId: string) => request<{ event: GovernanceEvent; view: EventView }>(`/api/v1/events/${encodeURIComponent(eventId)}?tz_offset=${tz()}`),
  session: (id: string) => request<SessionSummary>(`/api/v1/sessions/${encodeURIComponent(id)}?tz_offset=${tz()}`),
  facets: () => request<Facets>('/api/v1/facets'),
  exportUrl: (format: 'csv' | 'jsonl', params: URLSearchParams) => `/api/v1/events.${format}?${params}`,
};
