// 这个组件承载账户新增入口，把 OAuth、Token 和 API Key 三种方式收拢到同一块。

import { useState } from "react";
import type { ApiAccountPayload } from "../lib/types";
import { StatusBadge } from "./StatusBadge";

type AddMode = "oauth" | "token" | "api";

export interface AddAccountPanelProps {
  message: string;
  onMessage: (message: string) => void;
  onOAuthLogin: (target: "openclaw" | "codex") => Promise<void>;
  onImportCurrent: (target: "openclaw" | "codex") => Promise<void>;
  onImportToken: (value: string, label?: string) => Promise<void>;
  onCreateApiAccount: (payload: ApiAccountPayload) => Promise<void>;
}

function buildDefaultApiPayload(): ApiAccountPayload {
  return {
    base_url: "",
    api_key: "",
  };
}

// 渲染账户新增面板。
export function AddAccountPanel({
  message,
  onMessage,
  onOAuthLogin,
  onImportCurrent,
  onImportToken,
  onCreateApiAccount,
}: AddAccountPanelProps) {
  const [mode, setMode] = useState<AddMode>("oauth");
  const [tokenLabel, setTokenLabel] = useState("");
  const [tokenText, setTokenText] = useState("");
  const [apiPayload, setApiPayload] = useState<ApiAccountPayload>(buildDefaultApiPayload);
  const [busy, setBusy] = useState<AddMode | null>(null);

  async function run(modeName: AddMode, action: () => Promise<void>) {
    setBusy(modeName);
    try {
      await action();
    } catch (cause) {
      onMessage(cause instanceof Error ? cause.message : "添加账户失败");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="add-account-panel">
      <div className="panel-switcher" role="tablist" aria-label="添加账户方式">
        <button
          type="button"
          className={`panel-switcher-item${mode === "oauth" ? " is-active" : ""}`}
          onClick={() => setMode("oauth")}
        >
          OAuth 登录
        </button>
        <button
          type="button"
          className={`panel-switcher-item${mode === "token" ? " is-active" : ""}`}
          onClick={() => setMode("token")}
        >
          Token 导入
        </button>
        <button
          type="button"
          className={`panel-switcher-item${mode === "api" ? " is-active" : ""}`}
          onClick={() => setMode("api")}
        >
          API Key
        </button>
      </div>

      {mode === "oauth" ? (
        <div className="add-account-grid">
          <div className="add-account-card">
            <div className="event-head">
              <strong>网页登录</strong>
              <StatusBadge label="交互式" tone="neutral" />
            </div>
            <p>发起网页登录后，完成回调就会自动收编到账号池。</p>
            <div className="action-grid">
              <button
                type="button"
                className="action-button action-button-primary"
                disabled={busy === "oauth"}
                onClick={() => void run("oauth", () => onOAuthLogin("openclaw"))}
              >
                发起 OpenClaw 登录
              </button>
              <button
                type="button"
                className="action-button action-button-primary"
                disabled={busy === "oauth"}
                onClick={() => void run("oauth", () => onOAuthLogin("codex"))}
              >
                发起 Codex 登录
              </button>
            </div>
          </div>

          <div className="add-account-card">
            <div className="event-head">
              <strong>当前登录态</strong>
              <StatusBadge label="一键收编" tone="success" />
            </div>
            <p>把浏览器里已登录的账号直接导入，不需要重新授权。</p>
            <div className="action-grid">
              <button
                type="button"
                className="action-button"
                disabled={busy === "oauth"}
                onClick={() => void run("oauth", () => onImportCurrent("openclaw"))}
              >
                导入当前 OpenClaw
              </button>
              <button
                type="button"
                className="action-button"
                disabled={busy === "oauth"}
                onClick={() => void run("oauth", () => onImportCurrent("codex"))}
              >
                导入当前 Codex
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {mode === "token" ? (
        <div className="add-account-grid">
          <div className="add-account-card add-account-span-2">
            <div className="event-head">
              <strong>Token / JSON 导入</strong>
              <StatusBadge label="粘贴即可" tone="neutral" />
            </div>
            <p>支持粘贴 `auth.json` 内容，也支持 cockpit 导出的账号 JSON 数组。</p>
            <input
              value={tokenLabel}
              onChange={(event) => setTokenLabel(event.target.value)}
              placeholder="可选：显示名称"
            />
            <textarea
              rows={10}
              value={tokenText}
              onChange={(event) => setTokenText(event.target.value)}
              placeholder="把 auth.json 内容或账号 JSON 粘贴到这里"
            />
            <button
              type="button"
              className="action-button action-button-primary"
              disabled={busy === "token"}
              onClick={() =>
                void run("token", async () => {
                  await onImportToken(tokenText, tokenLabel || undefined);
                })
              }
            >
              导入 Token
            </button>
          </div>
        </div>
      ) : null}

      {mode === "api" ? (
        <div className="add-account-grid">
          <div className="add-account-card add-account-span-2">
            <div className="event-head">
              <strong>第三方 API 账号</strong>
              <StatusBadge label="手动锁定" tone="warning" />
            </div>
            <p>只需要基础地址和 API Key。添加后会进统一账号池，并可手动切到 OpenClaw 或 Codex。</p>
            <div className="form-grid">
              <label className="form-field form-field-wide">
                <span>基础地址</span>
                <input
                  value={apiPayload.base_url}
                  onChange={(event) =>
                    setApiPayload((current) => ({ ...current, base_url: event.target.value }))
                  }
                  placeholder="https://www.ananapi.com/"
                />
              </label>
              <label className="form-field form-field-wide">
                <span>API Key</span>
                <input
                  value={apiPayload.api_key}
                  onChange={(event) =>
                    setApiPayload((current) => ({ ...current, api_key: event.target.value }))
                  }
                  placeholder="sk-..."
                />
              </label>
            </div>
            <button
              type="button"
              className="action-button action-button-primary"
              disabled={busy === "api"}
              onClick={() => void run("api", () => onCreateApiAccount(apiPayload))}
            >
              添加 API 账号
            </button>
          </div>
        </div>
      ) : null}

      <div className="toolbar-row add-account-note-row">
        <span className="toolbar-note">{message}</span>
      </div>
    </div>
  );
}
