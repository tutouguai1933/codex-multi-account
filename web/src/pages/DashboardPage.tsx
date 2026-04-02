// 这个页面负责把所有账号第一时间铺到首页，并提供调度和快速操作入口。

import { useEffect, useMemo, useRef, useState } from "react";
import { AccountCard } from "../components/AccountCard";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import {
  deleteAccount,
  disableAccount,
  enableAccount,
  getOverview,
  probeAccount,
  refreshAllQuotas,
  runScheduler,
  switchAccount,
} from "../lib/api";
import type { AccountRecord, OverviewResponse } from "../lib/types";
import type { StatusBadgeProps } from "../components/StatusBadge";

export interface DashboardPageProps {
  onOverviewChange?: (overview: OverviewResponse) => void;
}

function eventTone(level: string): StatusBadgeProps["tone"] {
  if (level === "warning") return "warning";
  if (level === "danger" || level === "critical") return "danger";
  if (level === "info") return "neutral";
  return "success";
}

function resolveAllocationLabel(mode: OverviewResponse["summary"]["allocationMode"]): string {
  if (mode === "unassigned") return "未分配";
  if (mode === "partial") return "部分分配";
  if (mode === "separated") return "已分流";
  return "共用中";
}

function resolveSchedulerLabel(enabled: boolean, running: boolean): string {
  if (!enabled) return "自动刷新已关闭";
  if (running) return "后台自动刷新运行中";
  return "自动刷新已开启";
}

function resolveAssignmentScore(account: AccountRecord): number {
  if (account.assignment.openclaw && account.assignment.codex) return 3;
  if (account.assignment.openclaw || account.assignment.codex) return 2;
  if (account.status.manual_disabled) return 0;
  return 1;
}

function accountDisplayName(account: AccountRecord): string {
  return account.email ?? account.label;
}

function formatRunTime(value: number | null): string {
  if (!value) return "尚未执行";
  return new Date(value * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatCompactDateTime(value: number | null): string {
  if (!value) return "尚未执行";
  return new Date(value * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatEventTime(value: number): string {
  return new Date(value * 1000).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function remainingPercent(value: number | null): number | null {
  if (value == null) return null;
  return Math.max(0, Math.min(100, 100 - value));
}

function isQuotaTight(account: AccountRecord): boolean {
  const five = remainingPercent(account.quota.five_hour_used_pct);
  const week = remainingPercent(account.quota.weekly_used_pct);
  return (five !== null && five <= 25) || (week !== null && week <= 25);
}

function isProblemAccount(account: AccountRecord): boolean {
  return account.status.health !== "healthy" || account.status.manual_disabled;
}

// 渲染首页总览。
export function DashboardPage({ onOverviewChange }: DashboardPageProps) {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("等待调度");
  const [busyAction, setBusyAction] = useState<null | "scheduler" | "refresh-all" | "account">(null);
  const statusNoteRef = useRef<HTMLSpanElement | null>(null);

  function pushStatusMessage(message: string) {
    setStatusMessage(message);
    if (statusNoteRef.current) {
      statusNoteRef.current.textContent = message;
    }
  }

  async function refreshDashboard() {
    try {
      const payload = await getOverview();
      setOverview(payload);
      onOverviewChange?.(payload);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "overview-load-failed");
    }
  }

  function refreshDashboardLater() {
    void refreshDashboard();
  }

  useEffect(() => {
    let active = true;
    getOverview().then((payload) => {
      if (!active) return;
      setOverview(payload);
      onOverviewChange?.(payload);
      setError(null);
    }).catch((cause) => {
      if (!active) return;
      setError(cause instanceof Error ? cause.message : "overview-load-failed");
    });
    return () => {
      active = false;
    };
  }, [onOverviewChange]);

  const accounts = useMemo(() => {
    const rows = overview?.accounts ?? [];
    return [...rows].sort((left, right) => {
      const scoreDiff = resolveAssignmentScore(right) - resolveAssignmentScore(left);
      if (scoreDiff !== 0) return scoreDiff;
      return left.label.localeCompare(right.label, "zh-Hans-CN");
    });
  }, [overview]);

  const recentEvents = overview?.recentEvents ?? [];
  const tightQuotaCount = accounts.filter(isQuotaTight).length;
  const problemCount = accounts.filter(isProblemAccount).length;
  const activeCount = accounts.filter(
    (account) => account.assignment.openclaw || account.assignment.codex,
  ).length;
  const unassignedCount = accounts.filter(
    (account) => !account.assignment.openclaw && !account.assignment.codex,
  ).length;
  const schedulerSummary =
    overview?.scheduler.last_error ??
    overview?.scheduler.last_reason ??
    resolveSchedulerLabel(overview?.scheduler.enabled ?? false, overview?.scheduler.running ?? false);

  async function runWithFeedback(label: string, action: () => Promise<unknown>) {
    setBusyAction("account");
    pushStatusMessage(`正在${label}...`);
    try {
      await action();
      pushStatusMessage(`已完成：${label}`);
      refreshDashboardLater();
    } catch (cause) {
      pushStatusMessage(cause instanceof Error ? cause.message : `${label} 失败`);
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRunScheduler() {
    setBusyAction("scheduler");
    pushStatusMessage("正在调度...");
    try {
      const result = await runScheduler();
      pushStatusMessage(`调度完成：${result.reason}`);
      refreshDashboardLater();
    } catch (cause) {
      pushStatusMessage(cause instanceof Error ? cause.message : "scheduler-failed");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRefreshAllQuotas() {
    setBusyAction("refresh-all");
    pushStatusMessage("正在检测全部额度...");
    try {
      await refreshAllQuotas();
      pushStatusMessage("已开始：后台检测所有额度");
      window.setTimeout(() => {
        refreshDashboardLater();
      }, 1200);
      window.setTimeout(() => {
        refreshDashboardLater();
      }, 5000);
    } catch (cause) {
      pushStatusMessage(cause instanceof Error ? cause.message : "refresh-all-failed");
    } finally {
      setBusyAction(null);
    }
  }

  function handleDelete(account: AccountRecord) {
    const confirmed = window.confirm(`确认删除 ${accountDisplayName(account)} 吗？`);
    if (!confirmed) {
      pushStatusMessage("已取消删除");
      return;
    }
    void runWithFeedback(`删除 ${accountDisplayName(account)}`, async () => {
      await deleteAccount(account.id);
    });
  }

  return (
    <div className="dashboard-page">
      <section className="dashboard-command-grid">
        <article className="dashboard-command-card dashboard-command-card-accent dashboard-runtime-card">
          <div className="dashboard-command-head">
            <p className="dashboard-kicker">当前分配</p>
            <h3>运行面板</h3>
          </div>
          <div className="dashboard-runtime-grid">
            <div className="dashboard-runtime-stack">
              <div className="dashboard-runtime-row">
                <span className="runtime-target-mark">O</span>
                <div className="dashboard-runtime-copy">
                  <span className="check-label">OpenClaw</span>
                  <strong>{overview?.summary.openclawAccountEmail ?? "未分配"}</strong>
                </div>
              </div>
              <div className="dashboard-runtime-row">
                <span className="runtime-target-mark">C</span>
                <div className="dashboard-runtime-copy">
                  <span className="check-label">Codex</span>
                  <strong>{overview?.summary.codexAccountEmail ?? "未分配"}</strong>
                </div>
              </div>
            </div>

            <div className="dashboard-runtime-side">
              <div className="dashboard-runtime-mode">
                <span className="check-label">模式</span>
                <strong>{resolveAllocationLabel(overview?.summary.allocationMode ?? "unassigned")}</strong>
              </div>
              <div className="dashboard-runtime-side-meta">
                <div className="dashboard-runtime-mini">
                  <span className="check-label">自动刷新</span>
                  <strong>{overview?.scheduler.enabled ? "开启" : "关闭"}</strong>
                </div>
                <div className="dashboard-runtime-mini">
                  <span className="check-label">最近执行</span>
                  <strong>{formatCompactDateTime(overview?.scheduler.last_run_at ?? null)}</strong>
                </div>
              </div>
            </div>
          </div>
        </article>

        <article className="dashboard-command-card">
          <div className="dashboard-command-head">
            <p className="dashboard-kicker">风险概览</p>
            <h3>异常与余量</h3>
          </div>
          <div className="dashboard-metric-grid">
            <div className="dashboard-metric-tile">
              <span className="check-label">异常账号</span>
              <strong>{problemCount}</strong>
            </div>
            <div className="dashboard-metric-tile">
              <span className="check-label">紧张额度</span>
              <strong>{tightQuotaCount}</strong>
            </div>
            <div className="dashboard-metric-tile">
              <span className="check-label">当前占用</span>
              <strong>{activeCount}</strong>
            </div>
            <div className="dashboard-metric-tile">
              <span className="check-label">待命账号</span>
              <strong>{unassignedCount}</strong>
            </div>
          </div>
        </article>

        <article className="dashboard-command-card">
          <div className="dashboard-command-head">
            <p className="dashboard-kicker">全局动作</p>
            <h3>刷新与调度</h3>
          </div>
          <div className="dashboard-command-actions">
            <button
              type="button"
              className="action-button dashboard-secondary-button"
              disabled={busyAction !== null}
              onClick={() => void handleRefreshAllQuotas()}
            >
              {busyAction === "refresh-all" ? "检测中..." : "检测全部额度"}
            </button>
            <button
              type="button"
              className="action-button dashboard-run-button"
              disabled={busyAction !== null}
              onClick={() => void handleRunScheduler()}
            >
              {busyAction === "scheduler" ? "调度中..." : "立即调度"}
            </button>
          </div>
          <span ref={statusNoteRef} className="toolbar-note">{statusMessage}</span>
        </article>

        <article className="dashboard-command-card">
          <div className="dashboard-command-head">
            <p className="dashboard-kicker">最近结果</p>
            <h3>调度回执</h3>
          </div>
          <div className="dashboard-result-stack">
            <div className="dashboard-result-row">
              <span className="check-label">状态</span>
              <strong>{schedulerSummary}</strong>
            </div>
            <div className="dashboard-result-row">
              <span className="check-label">执行时间</span>
              <strong>{formatRunTime(overview?.scheduler.last_run_at ?? null)}</strong>
            </div>
            <div className="dashboard-result-row">
              <span className="check-label">自动刷新</span>
              <strong>{resolveSchedulerLabel(overview?.scheduler.enabled ?? false, overview?.scheduler.running ?? false)}</strong>
            </div>
          </div>
        </article>
      </section>

      {error ? <p className="inline-error">总览读取失败：{error}</p> : null}

      <div className="dashboard-section-head">
        <div>
          <p className="dashboard-kicker">账号池</p>
          <h3>全部账号</h3>
        </div>
        <div className="dashboard-section-meta">
          <span>{accounts.length} 个账号</span>
          <span>{activeCount} 个正在使用</span>
        </div>
      </div>

      <section className="account-wall" aria-label="账号卡片墙">
        {accounts.map((account) => (
          <AccountCard
            key={account.id}
            account={account}
            busy={busyAction !== null}
            onSwitch={(target) =>
              void runWithFeedback(`切换 ${accountDisplayName(account)} / ${target === "openclaw" ? "OpenClaw" : "Codex"}`, async () => {
                await switchAccount(account.id, { target });
              })
            }
            onProbe={() =>
              void runWithFeedback(`检测 ${accountDisplayName(account)}`, async () => {
                await probeAccount(account.id);
              })
            }
            onToggleDisabled={() =>
              void runWithFeedback(account.status.manual_disabled ? `启用 ${accountDisplayName(account)}` : `禁用 ${accountDisplayName(account)}`, async () => {
                if (account.status.manual_disabled) {
                  await enableAccount(account.id);
                  return;
                }
                await disableAccount(account.id);
              })
            }
            onDelete={() =>
              handleDelete(account)
            }
          />
        ))}
      </section>

      <div className="split-grid dashboard-bottom">
        <Panel title="最近信号">
          <div className="signal-list">
            {recentEvents.map((item) => (
              <div key={`${item.created_at}-${item.reason}`} className="signal-row">
                <span className="signal-time">
                  {formatEventTime(item.created_at)}
                </span>
                <p>{item.message}</p>
                <StatusBadge label={item.reason} tone={eventTone(item.level)} />
              </div>
            ))}
            {overview && recentEvents.length === 0 ? (
              <div className="signal-row">
                <span className="signal-time">--:--</span>
                <p>当前还没有事件记录。</p>
                <StatusBadge label="empty" tone="neutral" />
              </div>
            ) : null}
          </div>
        </Panel>

        <Panel title="运行摘要" tone="accent">
          <div className="dashboard-snapshot">
            <div>
              <span className="check-label">OpenClaw 当前账号</span>
              <strong>{overview?.summary.openclawAccountEmail ?? "未分配"}</strong>
            </div>
            <div>
              <span className="check-label">Codex 当前账号</span>
              <strong>{overview?.summary.codexAccountEmail ?? "未分配"}</strong>
            </div>
            <div>
              <span className="check-label">当前分配</span>
              <strong>{resolveAllocationLabel(overview?.summary.allocationMode ?? "unassigned")}</strong>
            </div>
            <div>
              <span className="check-label">后台自动刷新</span>
              <strong>{overview?.scheduler.enabled ? "开启" : "关闭"}</strong>
            </div>
            <div>
              <span className="check-label">最近一次执行</span>
              <strong>
                {overview?.scheduler.last_run_at
                  ? formatCompactDateTime(overview.scheduler.last_run_at)
                  : "尚未执行"}
              </strong>
            </div>
            <div>
              <span className="check-label">最近结果</span>
              <strong>{overview?.scheduler.last_error ?? overview?.scheduler.last_reason ?? "等待首次调度"}</strong>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
