// 这个文件集中定义前端和后端接口共用的数据结构。

export type HealthState =
  | "healthy"
  | "auth-invalid"
  | "plan-unavailable"
  | "quota-unknown"
  | "missing-binding"
  | "manual-disabled"
  | "stale";

export interface TargetBinding {
  snapshot_id: string | null;
  available: boolean;
}

export interface AccountRecord {
  id: string;
  label: string;
  email: string | null;
  tags: string[];
  bindings: {
    openclaw: TargetBinding;
    codex: TargetBinding;
  };
  status: {
    health: HealthState;
    reason: string;
    manual_disabled: boolean;
  };
  quota: {
    five_hour_used_pct: number | null;
    weekly_used_pct: number | null;
    reset_at_five_hour: number | null;
    reset_at_weekly: number | null;
  };
  assignment: {
    openclaw: boolean;
    codex: boolean;
  };
  timestamps: {
    last_detected_at: number | null;
    last_assigned_at: number | null;
  };
  metadata?: Record<string, unknown>;
}

export interface EventRecord {
  type: string;
  level: "info" | "warning" | "danger" | string;
  reason: string;
  message: string;
  target: string | null;
  account_id: string | null;
  created_at: number;
}

export interface OverviewResponse {
  status: string;
  summary: {
    totalAccounts: number;
    openclawAccountId: string | null;
    codexAccountId: string | null;
    openclawAccountEmail: string | null;
    codexAccountEmail: string | null;
    allocationMode: "unassigned" | "partial" | "shared" | "separated";
    separated: boolean;
  };
  scheduler: {
    running: boolean;
    enabled: boolean;
    refresh_interval_seconds: number;
    last_run_at: number | null;
    last_reason: string | null;
    last_error: string | null;
    last_source: string | null;
  };
  accounts: AccountRecord[];
  recentEvents: EventRecord[];
}

export interface SchedulerSettings {
  auto_refresh_enabled: boolean;
  refresh_interval_seconds: number;
  inactive_minutes: number;
  prefer_separation: boolean;
  thresholds: {
    five_hour_switch_at: number;
    hard_five_hour_switch_at: number;
    weekly_switch_at: number;
    hard_weekly_switch_at: number;
  };
}

export interface SwitchPayload {
  target: "openclaw" | "codex" | "both";
}

export interface LoginSessionState {
  target: "openclaw" | "codex";
  status:
    | "idle"
    | "running"
    | "imported"
    | "failed"
    | "completed"
    | "unavailable"
    | "interrupted"
    | "cancelled";
  note: string;
  pid: number | null;
  command: string[];
  started_at: number | null;
  finished_at: number | null;
  exit_code: number | null;
  imported_account_id: string | null;
  imported_label: string | null;
  error: string | null;
  auth_url: string | null;
  awaiting_input: boolean;
  output_lines: string[];
}
