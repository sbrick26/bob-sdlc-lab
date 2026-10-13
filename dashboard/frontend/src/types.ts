export type Decision = 'allowed' | 'blocked' | 'observed' | 'error';

export interface GovernanceEvent {
  event_id: string;
  occurred_at: string;
  user_name: string;
  device_name: string;
  device_id?: string | null;
  profile_name: string;
  profile_id?: string | null;
  policy_version: string;
  bob_version?: string | null;
  bob_channel?: string | null;
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
  finding_count?: number | null;
  hook_status?: string | null;
  detail?: string | null;
  evidence?: string | null;
  prompt_content?: string | null;
  tool_input_content?: string | null;
  tool_output_content?: string | null;
  response_content?: string | null;
  source?: string | null;
}

export interface Analytics {
  generated_at: string;
  window: { requested_days: number; effective_days: number; since: string; granularity: string };
  overall: {
    total: number;
    enforceable_total: number;
    allowed: number;
    blocked: number;
    observed: number;
    errors: number;
    blocked_rate_pct: number;
    reporting_users: number;
    users_with_blocks: number;
    highest_user_block_rate_pct: number;
    reporting_devices: number;
    active_rules: number;
    avg_policy_duration_ms: number | null;
    policy_duration_samples: number;
    avg_tool_duration_ms: number | null;
    tool_duration_samples: number;
    last_event?: string | null;
  };
  timeline: Array<{ bucket: string; total: number; allowed: number; blocked: number; observed: number; errors: number }>;
  top_users: Array<{ user_name: string; total: number; enforceable_total: number; allowed: number; blocked: number; observed: number; errors: number; blocked_rate_pct: number | null; last_seen: string }>;
  hook_events: Array<{ hook_event: string; total: number; allowed: number; blocked: number; observed: number; errors: number; avg_policy_duration_ms: number | null }>;
  rules: Array<{ rule_id: string; rule_name: string; severity: string; total: number; blocked: number; observed: number; affected_users: number; last_seen: string }>;
  tools: Array<{ tool_name: string; event_count: number; tool_uses: number; blocked: number; observed: number; avg_tool_duration_ms: number | null; duration_samples: number; last_seen: string }>;
}

export interface Facets {
  users: string[];
  devices: string[];
  profiles: string[];
  sources: string[];
  decisions: string[];
  rules: string[];
  severities: string[];
  events: string[];
  tools: string[];
}

export interface FleetDevice {
  device_name: string;
  user_name: string;
  profile_name: string;
  policy_version: string;
  bob_version?: string | null;
  last_seen: string;
  event_count: number;
  blocked_count: number;
}

export interface PolicyRule {
  rule_id: string;
  name: string;
  description: string;
  events: string[];
  decision: Decision;
  severity: string;
  enforcement: string;
  enabled?: boolean;
  configuration?: Record<string, unknown>;
}

export interface PolicyCatalog {
  policy_version: string;
  status?: string;
  config?: Record<string, unknown>;
  rules: PolicyRule[];
}

export interface PolicyDraft extends PolicyCatalog {
  revision: string;
  updated_at?: string;
  updated_by?: string;
  offline?: Record<string, unknown>;
  content?: Record<string, unknown>;
}

export interface Rollout {
  status: 'pending' | 'validating' | 'publishing' | 'succeeded' | 'deployed' | 'failed' | 'configuration_required' | 'not_started';
  policy_version?: string;
  started_at?: string;
  completed_at?: string;
  targeted_devices?: number;
  reporting_devices?: number;
  message?: string;
  error?: string | null;
}
