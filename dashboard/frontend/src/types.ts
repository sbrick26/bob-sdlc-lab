export type Decision = 'allowed' | 'blocked' | 'observed' | 'error';

export interface GovernanceEvent {
  event_id: string;
  occurred_at: string;
  user_name: string;
  team?: string | null;
  device_name?: string;
  hook_event: string;
  decision: Decision;
  rule_id?: string | null;
  rule_name?: string | null;
  severity?: string;
  tool_name?: string | null;
  lab_ticket?: string | null;
  lab_role?: string | null;
  lab_cost?: number | null;
  [key: string]: unknown;
}

export interface DetailField { label: string; value: string; href?: string }
export interface EventDetails {
  kind: 'prompt' | 'tool' | 'stop' | 'session' | 'ci' | 'pr';
  text?: string; chars?: number;
  tool?: string; tool_name?: string; command?: string; path?: string; content?: string; output?: string; run_time?: string;
  fields?: Array<{ label: string; value: string }>;
  message?: string; bobcoins?: number; turns?: number; tokens?: number;
  source?: string; workspace?: string;
  verdict?: string; criteria?: string; tests?: string; findings?: number; findings_list?: string[]; blocking?: number; duration?: string;
  pr_url?: string; run_url?: string; pr?: number; title?: string; approver?: string; lines_changed?: number; review_rounds?: number;
}
export interface SessionSummary {
  session_id: string; short_id: string; user: string | null; team: string | null; ticket: string | null;
  started_at: string | null; ended_at: string | null; duration_minutes: number | null; turns: number | null;
  bobcoins: number | null; usd: number | null; tokens: number | null; blocks: number; events: number;
  per_turn: Array<{ index: number; occurred_at: string; bobcoins: number | null; turns: number | null; tokens: number | null }>;
}
export interface EventView {
  title: string;
  status: string;
  decision: Decision;
  sentence: string;
  attempted?: string;
  details?: EventDetails;
  why?: string;
  remediation?: string;
  rule_id?: string;
  rule_url?: string;
  context?: DetailField[];
  technical?: DetailField[];
}

export interface Facets { users: string[]; decisions: string[]; events: string[]; tickets?: string[]; teams?: string[] }

export interface TopN<T> { items: Array<T & { other?: boolean; count?: number }>; total: number; truncated: boolean; unranked?: number; min_actions?: number; min_prs?: number }
export type Granularity = 'day' | 'week' | 'month';

export interface Kpi { value: number | null; prior: number | null; delta_pct: number | null }

export interface TeamRow {
  team: string; users: number; bobcoins: number | null; usd: number | null; budget: number | null;
  budget_used_pct: number | null; budget_bobcoins: number | null; budget_level: string | null; prs_merged: number;
  median_minutes_to_merge: number | null; blocked: number; first_try_pass_rate_pct: number | null;
}

export interface Common {
  usd_rate: number | null;
  usd_rate_basis: string | null;
  teams: string[];
  period_days: number | null;
  ci_label: string;
  jira_base_url?: string | null;
  kpis: Record<string, Kpi>;
  by_team?: TeamRow[];
}

export interface OverviewSummary extends Common {
  days: string[];
  granularity: Granularity;
  spend_by_team: Array<{ day: string; team: string; bobcoins: number }>;
  daily_active: Array<{ day: string; people: number }>;
  violations_by_team: TopN<{ team: string; blocked: number }>;
  merge_median_per_day: Array<{ day: string; minutes: number | null; merged: number }>;
  violations_by_rule: TopN<{ rule_id: string; rule_name: string | null; severity?: string | null; blocked: number; observed: number }>;
}

export interface BudgetEntry { kind: 'team' | 'person'; name: string; team: string | null; bobcoins: number; budget: number | null; pct: number | null; left: number | null; level: string | null; usd: number | null }

export interface CostSummary extends Common {
  budgets: { period: string; month_start: string; month_end: string; teams: BudgetEntry[]; people: BudgetEntry[]; near_limit: BudgetEntry[]; used_pct: number | null; used_bobcoins: number | null; total_budget: number | null; daily_pace: number | null; thresholds: number[] };
  equation: Record<'active_people' | 'sessions_per_person' | 'turns_per_session' | 'bobcoins_per_turn' | 'people_bobcoins' | 'ci_bobcoins' | 'total_bobcoins' | 'bobcoins_per_user', Kpi>;
  people: Array<{ user: string; team: string; sessions: number; turns: number | null; bobcoins: number | null; usd: number | null; tokens: number | null; budget_pct: number | null; budget?: number | null; budget_bobcoins?: number | null }>;
  automation: { label: string; sessions: number; turns: number | null; bobcoins: number | null; usd: number | null; tokens: number | null } | null;
  outliers: Array<{ session: string; session_id: string; user: string; ticket: string | null; team: string; bobcoins: number; usd: number | null; tokens: number; turns: number; flags: string[] }>;
  outlier_thresholds: { tokens: number; turns: number; bobcoins: number };
  daily: Array<{ day: string; teams: Record<string, number>; total: number; month_to_date: number }>;
  granularity: Granularity;
}

export interface TicketRow {
  ticket: string; user: string | null; team: string; status: string;
  started_at: string | null; pr_opened_at: string | null; merged_at: string | null;
  minutes_to_pr: number | null; minutes_to_merge: number | null; hands_on_hours: number | null;
  bobcoins: number | null; usd: number | null; verdict: string | null; findings: number | null;
}

export interface DeliverySummary extends Common {
  tickets: TicketRow[];
  granularity: Granularity;
  merge_by_team: TopN<{ team: string; minutes: number; merged: number }>;
  cost_per_pr_by_team: TopN<{ team: string; bobcoins_per_pr: number; usd_per_pr: number | null; merged: number }>;
  prs_per_day: Array<{ day: string; opened: number; merged: number }>;
  merge_distribution: Array<{ bucket: string; count: number }>;
  roi: {
    merged: number; opened: number; avg_minutes_to_pr: number | null; avg_minutes_to_merge: number | null;
    bobcoins_per_merged_pr: number | null; usd_per_merged_pr: number | null; bobcoins_per_merged_pr_direct: number | null;
    ci_with_result: number; ci_first_try_passed: number; first_try_pass_rate_pct: number | null;
  };
}

export interface PerformanceSummary extends Common {
  tools: Array<{ tool: string; calls: number; p50_s: number | null; p95_s: number | null; failures: number }>;
  series: Array<{ day: string; turn_p95_s: number | null; tool_failure_rate_pct: number | null }>;
  granularity: Granularity;
  failures: Array<{ tool: string; at: string; user: string; ticket: string | null }>;
  samples: { tool_calls: number; turns: number; checks: number };
}

export interface ViolationRow {
  event_id: string; occurred_at: string; user: string; team: string; ticket: string | null;
  rule_id: string; rule_name: string | null; rule_url?: string | null; control_point: string; excerpt: string; decision: Decision;
}

export interface ViolationsSummary extends Common {
  granularity: Granularity;
  by_rule: TopN<{ rule_id: string; rule_name: string | null; severity?: string | null; blocked: number }>;
  by_user: TopN<{ user: string; blocked: number }>;
  blocks_by_team: TopN<{ team: string; blocked: number }>;
  block_rate_by_user: TopN<{ user: string; blocks: number; actions: number; block_rate: number }>;
  over_time: Array<{ day: string; blocked: number }>;
  rows: ViolationRow[];
}

export interface RuleSummary {
  rule_id: string; name: string; checks: string; control_point: string; action: string; enabled: boolean;
  blocked: number; observed: number; last_fired: string | null; url?: string | null;
}
export interface RulesSummary { count: number; rules: RuleSummary[]; source?: { url: string; ref?: string | null; loaded_at?: string | null; last_error?: string | null; path?: string | null } }
