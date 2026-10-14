export type Decision = 'allowed' | 'blocked' | 'observed' | 'error';

export interface GovernanceEvent {
  event_id: string;
  occurred_at: string;
  user_name: string;
  device_name: string;
  device_id?: string | null;
  profile_name: string;
  policy_version: string;
  hook_event: string;
  decision: Decision;
  rule_id?: string | null;
  rule_name?: string | null;
  severity: string;
  workspace?: string | null;
  tool_name?: string | null;
  outcome?: string | null;
  duration_ms?: number | null;
  tool_duration_ms?: number | null;
  detail?: string | null;
  evidence?: string | null;
  prompt_content?: string | null;
  tool_input_content?: string | null;
  tool_output_content?: string | null;
  response_content?: string | null;
  source?: string | null;
  session_id?: string | null;
  lab_ticket?: string | null;
  lab_role?: string | null;
  lab_branch?: string | null;
  lab_cost?: number | null;
  lab_tokens?: number | null;
  lab_turns?: number | null;
  lab_path?: string | null;
  lab_kind?: string | null;
  lab_pr?: number | null;
}

export interface Facets {
  users: string[];
  decisions: string[];
  events: string[];
  tickets?: string[];
}

export interface Rate { usd_rate: number | null; usd_rate_basis: string | null }

export interface OverviewSummary extends Rate {
  users: string[];
  granularity: 'hour' | 'day';
  kpis: {
    active_users: number;
    sessions: number;
    prompts: number;
    tool_calls: number;
    bobcoins: number | null;
    usd: number | null;
    tokens: number | null;
    blocked: number;
    prs_merged: number;
    median_minutes_to_merge: number | null;
    bobcoins_per_merged_pr: number | null;
    usd_per_merged_pr: number | null;
  };
  bobcoins_by_user: Array<{ bucket: string; user: string; bobcoins: number }>;
  activity: Array<{ bucket: string; prompts: number; tool_calls: number; blocks: number }>;
  time_to_merge: Array<{ ticket: string; user: string; minutes: number }>;
  violations_by_rule: Array<{ rule_id: string; rule_name: string | null; blocked: number; observed: number }>;
}

export interface ViolationRow {
  event_id: string;
  occurred_at: string;
  user: string;
  ticket: string | null;
  rule_id: string;
  rule_name: string | null;
  control_point: string;
  excerpt: string;
  decision: Decision;
}

export interface ViolationsSummary {
  granularity: 'hour' | 'day';
  totals: { violations: number; blocked: number; observed: number; users_affected: number; rules_fired: number };
  by_rule: Array<{ rule_id: string; rule_name: string | null; blocked: number }>;
  by_control_point: Array<{ control_point: string; blocked: number }>;
  by_user: Array<{ user: string; blocked: number }>;
  over_time: Array<{ bucket: string; blocked: number }>;
  rows: ViolationRow[];
}

export interface PersonUsage {
  user: string;
  sessions: number;
  turns: number | null;
  prompts: number;
  tool_calls: number;
  bobcoins: number | null;
  usd: number | null;
  tokens: number | null;
  blocks: number;
  prs_opened: number;
  prs_merged: number;
  ci_first_try_passed: number;
  ci_with_result: number;
}

export interface TicketUsage {
  ticket: string;
  user: string | null;
  status: string;
  started_at: string | null;
  pr_opened_at: string | null;
  merged_at: string | null;
  minutes_to_pr: number | null;
  minutes_to_merge: number | null;
  bobcoins: number | null;
  usd: number | null;
  tokens: number | null;
  verdict: string | null;
  findings: number | null;
  first_try_pass: boolean | null;
}

export interface UsageSummary extends Rate {
  users: string[];
  people: PersonUsage[];
  tickets: TicketUsage[];
  bobcoins_over_time: Array<{ time: string; bobcoins: number; usd: number | null }>;
  cost_per_merged_pr: Array<{ ticket: string; user: string | null; bobcoins: number; usd: number | null }>;
  roi: {
    tickets: number;
    merged: number;
    merged_minutes_total: number;
    bobcoins_total: number | null;
    usd_total: number | null;
    bobcoins_merged_total: number | null;
    bobcoins_per_merged_pr: number | null;
    usd_per_merged_pr: number | null;
    ci_with_result: number;
    ci_first_try_passed: number;
    first_try_pass_rate_pct: number | null;
  };
}

export interface RuleSummary {
  rule_id: string;
  name: string;
  checks: string;
  control_point: string;
  action: string;
  enabled: boolean;
  blocked: number;
  observed: number;
  last_fired: string | null;
}
