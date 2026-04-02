// 这个组件负责在首页用卡片展示单个账号的核心状态，并直接承载常用操作。

import { StatusBadge } from "./StatusBadge";
import type { AccountRecord } from "../lib/types";
import type { StatusBadgeProps } from "./StatusBadge";

interface AccountOverviewCardProps {
  account: AccountRecord;
  busyActionKey: string | null;
  onAction: (
    account: AccountRecord,
    action: "switch-openclaw" | "switch-codex" | "probe" | "toggle" | "delete",
  ) => void;
}

function resolveHealthTone(state: string): StatusBadgeProps["tone"] {
  if (state === "healthy") return "success";
  if (state === "manual-disabled" || state === "quota-unknown") return "warning";
  if (state === "auth-invalid" || state === "plan-unavailable") return "danger";
  return "neutral";
}

function quotaLeft(value: number | null): number | null {
  if (value == null) return null;
  return Math.max(0, Math.min(100, 100 - value));
}

function resolveQuotaTone(left: number | null): "success" | "warning" | "danger" | "neutral" {
  if (left == null) return "neutral";
  if (left <= 20) return "danger";
  if (left <= 50) return "warning";
  return "success";
}

function formatResetAt(timestamp: number | null): string {
  if (!timestamp) return "未拿到重置时间";
  const now = Date.now();
  const diffMs = timestamp * 1000 - now;
  if (diffMs <= 0) return "即将重置";
  const totalMinutes = Math.floor(diffMs / 60000);
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function firstString(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function readNestedString(
  root: Record<string, unknown> | undefined,
  keys: string[],
): string | null {
  let current: unknown = root;
  for (const key of keys) {
    if (!current || typeof current !== "object") return null;
    current = (current as Record<string, unknown>)[key];
  }
  return firstString(current);
}

function resolveAccountName(account: AccountRecord): string | null {
  return (
    readNestedString(account.metadata, ["codex_export", "account_name"]) ??
    readNestedString(account.metadata, ["identity", "account_id"])
  );
}

function resolvePlanType(account: AccountRecord): string | null {
  return (
    readNestedString(account.metadata, ["identity", "plan_type"]) ??
    readNestedString(account.metadata, ["codex_export", "plan_type"])
  );
}

function resolveAuthMode(account: AccountRecord): string | null {
  return (
    readNestedString(account.metadata, ["identity", "auth_mode"]) ??
    readNestedString(account.metadata, ["codex_export", "auth_mode"])
  );
}

function quotaLabel(title: string, left: number | null): string {
  if (left == null) return `${title} 未知`;
  return `${title} ${left.toFixed(0)}%`;
}

// 渲染单个账号卡片。
export function AccountOverviewCard({
  account,
  busyActionKey,
  onAction,
}: AccountOverviewCardProps) {
  const fiveHourLeft = quotaLeft(account.quota.five_hour_used_pct);
  const weeklyLeft = quotaLeft(account.quota.weekly_used_pct);
  const accountName = resolveAccountName(account);
  const planType = resolvePlanType(account);
  const authMode = resolveAuthMode(account);

  return (
    <article className="account-card">
      <div className="account-card-head">
        <div className="account-card-title">
          <label className="account-card-check">
            <input type="checkbox" checked readOnly aria-label={`${account.label} 已选中`} />
            <span>{account.email ?? account.label}</span>
          </label>
          <div className="tag-row">
            {account.assignment.openclaw || account.assignment.codex ? (
              <span className="mini-tag mini-tag-current">当前</span>
            ) : null}
            {planType ? <span className="mini-tag mini-tag-plan">{planType.toUpperCase()}</span> : null}
          </div>
        </div>
      </div>

      <div className="account-card-meta">
        <span>显示名：{account.label}</span>
        <span>工作区：{accountName ?? "未识别"}</span>
        <span>
          登录方式：
          {authMode ?? "未知"}
          {account.metadata && readNestedString(account.metadata, ["identity", "user_id"])
            ? ` / 用户 ID: ${readNestedString(account.metadata, ["identity", "user_id"])}`
            : ""}
        </span>
      </div>

      <div className="account-card-quotas">
        <div className="quota-block">
          <div className="quota-row">
            <span>{quotaLabel("5h", fiveHourLeft)}</span>
            <strong>{fiveHourLeft == null ? "--" : `${fiveHourLeft.toFixed(0)}%`}</strong>
          </div>
          <div className="quota-track">
            <div
              className={`quota-fill quota-fill-${resolveQuotaTone(fiveHourLeft)}`}
              style={{ width: `${fiveHourLeft ?? 0}%` }}
            />
          </div>
          <span className="quota-reset">{formatResetAt(account.quota.reset_at_five_hour)}</span>
        </div>

        <div className="quota-block">
          <div className="quota-row">
            <span>{quotaLabel("Weekly", weeklyLeft)}</span>
            <strong>{weeklyLeft == null ? "--" : `${weeklyLeft.toFixed(0)}%`}</strong>
          </div>
          <div className="quota-track">
            <div
              className={`quota-fill quota-fill-${resolveQuotaTone(weeklyLeft)}`}
              style={{ width: `${weeklyLeft ?? 0}%` }}
            />
          </div>
          <span className="quota-reset">{formatResetAt(account.quota.reset_at_weekly)}</span>
        </div>
      </div>

      <div className="account-card-footer">
        <div className="tag-row">
          <StatusBadge label={account.status.health} tone={resolveHealthTone(account.status.health)} />
          {account.assignment.openclaw ? <span className="mini-tag">OpenClaw</span> : null}
          {account.assignment.codex ? <span className="mini-tag">Codex</span> : null}
          {!account.assignment.openclaw && !account.assignment.codex ? (
            <span className="mini-tag">未分配</span>
          ) : null}
          {account.status.manual_disabled ? <span className="mini-tag">已禁用</span> : null}
        </div>

        <div className="account-card-actions">
          <button
            type="button"
            className="icon-action"
            disabled={busyActionKey === `${account.id}:switch-openclaw`}
            onClick={() => onAction(account, "switch-openclaw")}
            title="切 OpenClaw"
          >
            O
          </button>
          <button
            type="button"
            className="icon-action"
            disabled={busyActionKey === `${account.id}:switch-codex`}
            onClick={() => onAction(account, "switch-codex")}
            title="切 Codex"
          >
            C
          </button>
          <button
            type="button"
            className="icon-action"
            disabled={busyActionKey === `${account.id}:probe`}
            onClick={() => onAction(account, "probe")}
            title="检测"
          >
            刷
          </button>
          <button
            type="button"
            className="icon-action"
            disabled={busyActionKey === `${account.id}:toggle`}
            onClick={() => onAction(account, "toggle")}
            title={account.status.manual_disabled ? "启用" : "禁用"}
          >
            {account.status.manual_disabled ? "启" : "停"}
          </button>
          <button
            type="button"
            className="icon-action icon-action-danger"
            disabled={busyActionKey === `${account.id}:delete`}
            onClick={() => onAction(account, "delete")}
            title="删除"
          >
            删
          </button>
        </div>
      </div>
    </article>
  );
}
