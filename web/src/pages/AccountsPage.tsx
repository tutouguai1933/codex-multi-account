// 这个页面用于查看账户列表、状态和标签，并支持关键手动操作。

import { useEffect, useState } from "react";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import {
  cancelLogin,
  deleteAccount,
  disableAccount,
  enableAccount,
  exportCodexBatch,
  importCodexBatch,
  importCurrent,
  listAccounts,
  listLoginStates,
  probeAccount,
  startLogin,
  submitLoginInput,
  switchAccount,
} from "../lib/api";
import type { AccountRecord, LoginSessionState } from "../lib/types";
import type { StatusBadgeProps } from "../components/StatusBadge";

function resolveHealthTone(state: string): StatusBadgeProps["tone"] {
  if (state === "healthy") return "success";
  if (state === "manual-disabled" || state === "quota-unknown") return "warning";
  if (state === "auth-invalid" || state === "plan-unavailable") return "danger";
  return "neutral";
}

function formatQuota(value: number | null) {
  if (value == null) return "unknown";
  return `${(100 - value).toFixed(1)}% left`;
}

function resolveLoginTone(state: LoginSessionState["status"]): StatusBadgeProps["tone"] {
  if (state === "running") return "warning";
  if (state === "imported") return "success";
  if (state === "failed" || state === "unavailable") return "danger";
  if (state === "interrupted") return "warning";
  return "neutral";
}

function resolveLoginLabel(target: "openclaw" | "codex") {
  return target === "openclaw" ? "OpenClaw 登录" : "Codex 登录";
}

function formatLoginTime(value: number | null) {
  if (!value) return "未记录时间";
  return new Date(value * 1000).toLocaleString();
}

// 渲染账户列表页面。
export function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountRecord[]>([]);
  const [loginStates, setLoginStates] = useState<Record<"openclaw" | "codex", LoginSessionState> | null>(null);
  const [loginInputs, setLoginInputs] = useState<Record<"openclaw" | "codex", string>>({
    openclaw: "",
    codex: "",
  });
  const [batchJson, setBatchJson] = useState("");
  const [message, setMessage] = useState("准备加载");
  const [loginMessage, setLoginMessage] = useState("登录状态加载中");

  async function refreshAccounts() {
    try {
      const rows = await listAccounts();
      setAccounts(rows);
      setMessage(`已加载 ${rows.length} 个账号`);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "load-failed");
    }
  }

  async function refreshLoginStates() {
    try {
      const payload = await listLoginStates();
      setLoginStates(payload.targets);
      setLoginMessage("已更新登录状态");
      if (
        payload.targets.openclaw.status === "imported" ||
        payload.targets.codex.status === "imported"
      ) {
        await refreshAccounts();
      }
    } catch (cause) {
      setLoginMessage(cause instanceof Error ? cause.message : "login-status-failed");
    }
  }

  async function handleRefreshLoginStates() {
    setLoginMessage("正在刷新登录状态");
    await refreshLoginStates();
  }

  useEffect(() => {
    void refreshAccounts();
    void refreshLoginStates();
  }, []);

  useEffect(() => {
    if (!loginStates) return;
    const hasRunning = Object.values(loginStates).some((item) => item.status === "running");
    if (!hasRunning) return;
    const timer = window.setInterval(() => {
      void refreshLoginStates();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loginStates]);

  async function runAction(action: () => Promise<unknown>, label: string) {
    try {
      await action();
      setMessage(label);
      await refreshAccounts();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : `${label} 失败`);
    }
  }

  async function handleImportCodexBatch() {
    try {
      const parsed = JSON.parse(batchJson);
      if (!Array.isArray(parsed)) {
        setMessage("批量导入失败：JSON 顶层必须是数组");
        return;
      }
      const result = await importCodexBatch(parsed as Array<Record<string, unknown>>);
      setMessage(`已批量导入 ${result.importedCount} 个账号`);
      await refreshAccounts();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "batch-import-failed");
    }
  }

  async function handleExportCodexBatch() {
    try {
      const result = await exportCodexBatch();
      const content = JSON.stringify(result.items, null, 2);
      setBatchJson(content);
      const blob = new Blob([content], { type: "application/json;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "codex-accounts.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setMessage(`已导出 ${result.items.length} 个账号`);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "batch-export-failed");
    }
  }

  return (
    <div className="page-stack">
      <Panel
        title="登录状态"
        description="第一版先把登录动作变成页面里可见、可追踪的状态流。"
      >
        <div className="toolbar-row">
          <button
            type="button"
            className="action-button"
            onClick={() => void handleRefreshLoginStates()}
          >
            刷新登录状态
          </button>
          <span className="toolbar-note">{loginMessage}</span>
        </div>
        <div className="settings-grid">
          {(loginStates
            ? [loginStates.openclaw, loginStates.codex]
            : [
                {
                  target: "openclaw",
                  status: "idle",
                  note: "未开始",
                  pid: null,
                  command: [],
                  started_at: null,
                  finished_at: null,
                  exit_code: null,
                  imported_account_id: null,
                  imported_label: null,
                  error: null,
                  auth_url: null,
                  awaiting_input: false,
                  output_lines: [],
                },
                {
                  target: "codex",
                  status: "idle",
                  note: "未开始",
                  pid: null,
                  command: [],
                  started_at: null,
                  finished_at: null,
                  exit_code: null,
                  imported_account_id: null,
                  imported_label: null,
                  error: null,
                  auth_url: null,
                  awaiting_input: false,
                  output_lines: [],
                },
              ]
          ).map((state) => (
            <div key={state.target} className="maintenance-card">
              <div className="event-head">
                <strong>{resolveLoginLabel(state.target)}</strong>
                <StatusBadge
                  label={state.status}
                  tone={resolveLoginTone(state.status)}
                />
              </div>
              <span>{state.note}</span>
              <span>
                {state.pid ? `PID ${state.pid}` : "当前没有运行中的登录命令"}
              </span>
              <span>{`开始时间：${formatLoginTime(state.started_at)}`}</span>
              {state.imported_label ? <span>{`已收编账号：${state.imported_label}`}</span> : null}
              {state.auth_url ? (
                <a href={state.auth_url} target="_blank" rel="noreferrer" className="account-email">
                  打开授权链接
                </a>
              ) : null}
              {state.output_lines.length > 0 ? (
                <div className="binding-stack">
                  {state.output_lines.slice(-3).map((line) => (
                    <span key={`${state.target}-${line}`}>{line}</span>
                  ))}
                </div>
              ) : null}
              {state.status === "running" && (state.awaiting_input || state.auth_url) ? (
                <div className="binding-stack">
                  <textarea
                    rows={3}
                    value={loginInputs[state.target]}
                    onChange={(event) =>
                      setLoginInputs((current) => ({
                        ...current,
                        [state.target]: event.target.value,
                      }))
                    }
                    placeholder="把完整回调地址或授权码粘贴到这里"
                  />
                  <button
                    type="button"
                    className="action-button"
                    onClick={() =>
                      void (async () => {
                        try {
                          const result = await submitLoginInput(
                            state.target,
                            loginInputs[state.target],
                          );
                          setLoginMessage(result.note);
                          setLoginInputs((current) => ({
                            ...current,
                            [state.target]: "",
                          }));
                          await refreshLoginStates();
                        } catch (cause) {
                          setLoginMessage(
                            cause instanceof Error ? cause.message : "login-input-failed",
                          );
                        }
                      })()
                    }
                  >
                    提交授权信息
                  </button>
                </div>
              ) : null}
              {state.status === "running" ? (
                <button
                  type="button"
                  className="action-button action-button-danger"
                  onClick={() =>
                    void (async () => {
                      const result = await cancelLogin(state.target);
                      setLoginMessage(result.note);
                      await refreshLoginStates();
                    })()
                  }
                >
                  取消登录
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="批量导入 / 导出"
        description="兼容 cockpit-tools 的 Codex JSON。导入后会同时补齐 Codex 和 OpenClaw 两侧快照。"
      >
        <div className="toolbar-row">
          <button
            type="button"
            className="action-button"
            onClick={() => void handleImportCodexBatch()}
          >
            批量导入 Codex JSON
          </button>
          <button
            type="button"
            className="action-button"
            onClick={() => void handleExportCodexBatch()}
          >
            导出为 Codex JSON
          </button>
          <span className="toolbar-note">{message}</span>
        </div>
        <div className="binding-stack">
          <textarea
            rows={10}
            value={batchJson}
            onChange={(event) => setBatchJson(event.target.value)}
            placeholder="把 cockpit-tools 导出的 JSON 数组粘贴到这里，或先点击导出。"
          />
        </div>
      </Panel>

      <Panel
        title="账户清单"
        description="这里直接接真实接口，可做导入、检测、切换、禁用和删除。"
      >
        <div className="toolbar-row">
          <button
            type="button"
            className="action-button"
            onClick={() => void runAction(() => importCurrent("openclaw"), "已导入当前 OpenClaw")}
          >
            导入当前 OpenClaw
          </button>
          <button
            type="button"
            className="action-button"
            onClick={() => void runAction(() => importCurrent("codex"), "已导入当前 Codex")}
          >
            导入当前 Codex
          </button>
          <button
            type="button"
            className="action-button"
            onClick={() =>
              void runAction(
                async () => {
                  const result = await startLogin("openclaw");
                  await refreshLoginStates();
                  setLoginMessage(result.note);
                },
                "已发起 OpenClaw 登录，请按页面引导完成",
              )
            }
          >
            开始 OpenClaw 登录
          </button>
          <button
            type="button"
            className="action-button"
            onClick={() =>
              void runAction(
                async () => {
                  const result = await startLogin("codex");
                  await refreshLoginStates();
                  setLoginMessage(result.note);
                },
                "已发起 Codex 登录，请按页面引导完成",
              )
            }
          >
            开始 Codex 登录
          </button>
          <span className="toolbar-note">{message}</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>账号</th>
                <th>绑定</th>
                <th>状态</th>
                <th>额度</th>
                <th>分配</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td>
                    <strong>{account.label}</strong>
                    <div className="subtle">{account.id}</div>
                    <div className="account-email">{account.email ?? "no-email"}</div>
                  </td>
                  <td>
                    <div className="binding-stack">
                      <span>OpenClaw: {account.bindings.openclaw.snapshot_id ?? "未绑定"}</span>
                      <span>Codex: {account.bindings.codex.snapshot_id ?? "未绑定"}</span>
                    </div>
                  </td>
                  <td>
                    <StatusBadge
                      label={account.status.health}
                      tone={resolveHealthTone(account.status.health)}
                    />
                    <div className="subtle">{account.status.reason}</div>
                  </td>
                  <td>
                    <div className="binding-stack">
                      <span>5h: {formatQuota(account.quota.five_hour_used_pct)}</span>
                      <span>week: {formatQuota(account.quota.weekly_used_pct)}</span>
                    </div>
                  </td>
                  <td>
                    <div className="tag-row">
                      {account.assignment.openclaw ? <span className="mini-tag">OpenClaw</span> : null}
                      {account.assignment.codex ? <span className="mini-tag">Codex</span> : null}
                      {!account.assignment.openclaw && !account.assignment.codex ? (
                        <span className="mini-tag">未分配</span>
                      ) : null}
                    </div>
                  </td>
                  <td>
                    <div className="action-grid">
                      <button
                        type="button"
                        className="action-button"
                        onClick={() =>
                          void runAction(
                            () => switchAccount(account.id, { target: "openclaw" }),
                            `已切到 ${account.label} / OpenClaw`,
                          )
                        }
                      >
                        切 OpenClaw
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() =>
                          void runAction(
                            () => switchAccount(account.id, { target: "codex" }),
                            `已切到 ${account.label} / Codex`,
                          )
                        }
                      >
                        切 Codex
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void runAction(() => probeAccount(account.id), `已检测 ${account.label}`)}
                      >
                        检测
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() =>
                          void runAction(
                            () =>
                              account.status.manual_disabled
                                ? enableAccount(account.id)
                                : disableAccount(account.id),
                            account.status.manual_disabled ? `已启用 ${account.label}` : `已禁用 ${account.label}`,
                          )
                        }
                      >
                        {account.status.manual_disabled ? "启用" : "禁用"}
                      </button>
                      <button
                        type="button"
                        className="action-button action-button-danger"
                        onClick={() =>
                          void runAction(() => deleteAccount(account.id), `已删除 ${account.label}`)
                        }
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
