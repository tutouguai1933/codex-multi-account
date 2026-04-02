// 这个组件用于总览页的账号卡片，集中展示状态、额度和常用操作。

import type { ReactNode } from "react";
import type { AccountRecord } from "../lib/types";
import { StatusBadge } from "./StatusBadge";

export interface AccountCardProps {
  account: AccountRecord;
  busy?: boolean;
  onSwitch: (target: "openclaw" | "codex") => void;
  onProbe: () => void;
  onToggleDisabled: () => void;
  onDelete: () => void;
}

function resolveHealthTone(state: string) {
  if (state === "healthy") return "success";
  if (state === "manual-disabled" || state === "quota-unknown") return "warning";
  if (state === "auth-invalid" || state === "plan-unavailable") return "danger";
  return "neutral";
}

function getNestedValue(source: unknown, path: string[]): unknown {
  let current: unknown = source;
  for (const key of path) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

function getNestedString(source: unknown, path: string[]): string | null {
  const value = getNestedValue(source, path);
  return typeof value === "string" && value.trim() ? value : null;
}

function remainingPercent(value: number | null): number | null {
  if (value == null) return null;
  return Math.max(0, Math.min(100, 100 - value));
}

function formatPercent(value: number | null): string {
  if (value == null) return "未知";
  return `${Math.round(value)}%`;
}

function formatTime(value: number | null): string {
  if (!value) return "未刷新";
  return new Date(value * 1000).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatResetCountdown(resetAt: number | null): string {
  if (!resetAt) return "重置时间未知";
  const remainingSeconds = Math.max(0, resetAt - Math.floor(Date.now() / 1000));
  const hours = Math.floor(remainingSeconds / 3600);
  const minutes = Math.floor((remainingSeconds % 3600) / 60);
  const date = new Date(resetAt * 1000).toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
  const time = new Date(resetAt * 1000).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${hours}h ${minutes}m (${date} ${time})`;
}

function resolvePlanLabel(account: AccountRecord): string {
  const planType =
    getNestedString(account.metadata, ["identity", "plan_type"]) ??
    getNestedString(account.metadata, ["codex_export", "plan_type"]);
  if (typeof planType === "string" && planType.trim()) {
    return planType.toUpperCase();
  }
  return "ACCOUNT";
}

function resolveAuthLabel(account: AccountRecord): string {
  const authMode =
    getNestedString(account.metadata, ["identity", "auth_mode"]) ??
    getNestedString(account.metadata, ["codex_export", "auth_mode"]);
  if (authMode) {
    return authMode;
  }
  if (account.bindings.openclaw.available && account.bindings.codex.available) {
    return "shared";
  }
  if (account.bindings.openclaw.available) {
    return "openclaw";
  }
  if (account.bindings.codex.available) {
    return "codex";
  }
  return "unbound";
}

function resolveAssignmentLabel(account: AccountRecord): string {
  if (account.assignment.openclaw && account.assignment.codex) return "共用";
  if (account.assignment.openclaw) return "OpenClaw";
  if (account.assignment.codex) return "Codex";
  return "未分配";
}

function resolveAssignmentTone(account: AccountRecord) {
  if (account.assignment.openclaw && account.assignment.codex) return "success" as const;
  if (account.assignment.openclaw || account.assignment.codex) return "warning" as const;
  return "neutral" as const;
}

function isActivelyAssigned(account: AccountRecord): boolean {
  return account.assignment.openclaw || account.assignment.codex;
}

function resolveAccountName(account: AccountRecord): string {
  return (
    getNestedString(account.metadata, ["codex_export", "account_name"]) ??
    getNestedString(account.metadata, ["identity", "account_id"]) ??
    account.label
  );
}

function resolveUsageTone(value: number | null) {
  const remaining = remainingPercent(value);
  if (remaining == null) return "neutral";
  if (remaining <= 20) return "danger";
  if (remaining <= 45) return "warning";
  return "success";
}

function IconSwitchOpenClaw() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M6 6h8l-2.4 2.4 1.4 1.4L18 5l-5-4-1.4 1.4L14 4H6a4 4 0 0 0-4 4v3h2V8a2 2 0 0 1 2-2Zm12 7v3a2 2 0 0 1-2 2H8l2.4-2.4-1.4-1.4L4 19l5 4 1.4-1.4L8 20h8a4 4 0 0 0 4-4v-3h-2Z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconSwitchCodex() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5Zm2 0v14h12V5H6Zm2.7 3.2L12 11.5l-3.3 3.3 1.4 1.4 4.7-4.7-4.7-4.7-1.4 1.4Zm6.3 7.8h-4v2h4v-2Z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconProbe() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 5a7 7 0 1 1-6.4 4.2H3l3.5-4L10 9H7.7A5 5 0 1 0 12 7V5Z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconToggle(active: boolean) {
  if (active) {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 6h3v12H7V6Zm7 0h3v12h-3V6Z" fill="currentColor" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M11 3h2v8h-2V3Zm1 18a8 8 0 0 1-5.7-13.7l1.4 1.4A6 6 0 1 0 12 6V4a8 8 0 0 1 0 16Z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconDelete() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M9 3h6l1 2h4v2H4V5h4l1-2Zm1 6h2v8h-2V9Zm4 0h2v8h-2V9ZM7 9h2v8H7V9Zm-1 12a2 2 0 0 1-2-2V8h16v11a2 2 0 0 1-2 2H6Z"
        fill="currentColor"
      />
    </svg>
  );
}

interface IconButtonProps {
  label: string;
  danger?: boolean;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}

function IconButton({ label, danger = false, disabled, onClick, children }: IconButtonProps) {
  return (
    <button
      type="button"
      className={`icon-action${danger ? " icon-action-danger" : ""}`}
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      title={label}
      data-tip={label}
    >
      {children}
    </button>
  );
}

// 渲染单个账号卡片。
export function AccountCard({
  account,
  busy = false,
  onSwitch,
  onProbe,
  onToggleDisabled,
  onDelete,
}: AccountCardProps) {
  const fiveHourRemaining = remainingPercent(account.quota.five_hour_used_pct);
  const weeklyRemaining = remainingPercent(account.quota.weekly_used_pct);
  const isAssigned = isActivelyAssigned(account);
  const openclawUsing = account.assignment.openclaw;
  const codexUsing = account.assignment.codex;
  const lastUpdated = account.timestamps.last_detected_at;

  return (
    <article
      className={`account-card${account.status.manual_disabled ? " is-disabled" : ""}${
        isAssigned ? " is-assigned" : ""
      }`}
      data-busy={busy ? "true" : "false"}
    >
      <div className="account-card-top">
        <div className="account-title-group">
          <div className="account-title-row">
            <strong className="account-title">{account.email ?? account.label}</strong>
            {isAssigned ? <StatusBadge label="当前" tone="success" /> : null}
            <span className="plan-pill">{resolvePlanLabel(account)}</span>
          </div>
          <div className="account-subtitle">{resolveAccountName(account)}</div>
        </div>
        <div className="account-target-pills">
          <span className={`target-pill${openclawUsing ? " is-live" : ""}`}>O</span>
          <span className={`target-pill${codexUsing ? " is-live" : ""}`}>C</span>
        </div>
      </div>

      <div className="account-meta">
        <span>{account.email ?? account.label}</span>
        <span>登录方式 {resolveAuthLabel(account)}</span>
        <span>
          用户 {getNestedString(account.metadata, ["identity", "user_id"]) ??
            getNestedString(account.metadata, ["codex_export", "user_id"]) ??
            account.id}
        </span>
      </div>

      <div className="account-status-row">
        <StatusBadge label={account.status.health} tone={resolveHealthTone(account.status.health)} />
        <StatusBadge label={resolveAssignmentLabel(account)} tone={resolveAssignmentTone(account)} />
      </div>

      <div className="quota-stack">
        <div className="quota-group">
          <div className="quota-head">
            <span className="quota-label">5h</span>
            <strong className={`quota-value quota-value-${resolveUsageTone(account.quota.five_hour_used_pct)}`}>
              {formatPercent(fiveHourRemaining)}
            </strong>
          </div>
          <div className="quota-track" aria-hidden="true">
            <span
              className={`quota-fill${
                (fiveHourRemaining ?? 100) <= 20 ? " quota-fill-danger" : ""
              }`}
              style={{ width: `${Math.min(Math.max(fiveHourRemaining ?? 0, 0), 100)}%` }}
            />
          </div>
          <div className="quota-foot">{formatResetCountdown(account.quota.reset_at_five_hour)}</div>
        </div>

        <div className="quota-group">
          <div className="quota-head">
            <span className="quota-label">Weekly</span>
            <strong className={`quota-value quota-value-${resolveUsageTone(account.quota.weekly_used_pct)}`}>
              {formatPercent(weeklyRemaining)}
            </strong>
          </div>
          <div className="quota-track quota-track-weekly" aria-hidden="true">
            <span
              className={`quota-fill quota-fill-weekly${
                (weeklyRemaining ?? 100) <= 20 ? " quota-fill-danger" : ""
              }`}
              style={{ width: `${Math.min(Math.max(weeklyRemaining ?? 0, 0), 100)}%` }}
            />
          </div>
          <div className="quota-foot">{formatResetCountdown(account.quota.reset_at_weekly)}</div>
        </div>
      </div>

      <div className="account-card-footer">
        <div className="account-card-timestamp">更新 {formatTime(lastUpdated)}</div>
        <div className="account-action-grid">
          <IconButton
            label="切换到 OpenClaw"
            disabled={busy}
            onClick={() => onSwitch("openclaw")}
          >
            <IconSwitchOpenClaw />
          </IconButton>
          <IconButton
            label="切换到 Codex"
            disabled={busy}
            onClick={() => onSwitch("codex")}
          >
            <IconSwitchCodex />
          </IconButton>
          <IconButton label="检测额度" disabled={busy} onClick={onProbe}>
            <IconProbe />
          </IconButton>
          <IconButton
            label={account.status.manual_disabled ? "启用账号" : "禁用账号"}
            disabled={busy}
            onClick={onToggleDisabled}
          >
            <IconToggle active={account.status.manual_disabled} />
          </IconButton>
          <IconButton label="删除账号" danger disabled={busy} onClick={onDelete}>
            <IconDelete />
          </IconButton>
        </div>
      </div>
    </article>
  );
}
