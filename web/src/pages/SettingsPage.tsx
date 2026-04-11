// 这个页面负责读取和保存调度设置。

import { useEffect, useState } from "react";
import { Panel } from "../components/Panel";
import {
  getCodexRuntimeFiles,
  getSettings,
  saveCodexQuickSettings,
  saveCodexRuntimeFiles,
  saveSettings,
} from "../lib/api";
import type { CodexRuntimeFiles, SchedulerSettings } from "../lib/types";

const DEFAULT_CONTEXT_WINDOW = 400_000;
const DEFAULT_AUTO_COMPACT_TOKEN_LIMIT = 300_000;

function withCodexDefaults(payload: CodexRuntimeFiles): CodexRuntimeFiles {
  return {
    ...payload,
    quick_settings: {
      ...payload.quick_settings,
      model_context_window:
        payload.quick_settings.model_context_window ?? DEFAULT_CONTEXT_WINDOW,
      model_auto_compact_token_limit:
        payload.quick_settings.model_auto_compact_token_limit ??
        DEFAULT_AUTO_COMPACT_TOKEN_LIMIT,
    },
  };
}

function toKUnit(value: number | null | undefined, fallback: number): string {
  return String(Math.trunc((value ?? fallback) / 1000));
}

// 渲染设置页面。
export function SettingsPage() {
  const [settings, setSettings] = useState<SchedulerSettings | null>(null);
  const [message, setMessage] = useState("加载中");
  const [codexFiles, setCodexFiles] = useState<CodexRuntimeFiles | null>(null);
  const [codexMessage, setCodexMessage] = useState("读取 Codex 文件中");

  useEffect(() => {
    let active = true;
    getSettings()
      .then((payload) => {
        if (!active) return;
        setSettings(payload);
        setMessage("已读取当前设置");
      })
      .catch((cause) => {
        if (!active) return;
        setMessage(cause instanceof Error ? cause.message : "load-failed");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getCodexRuntimeFiles()
      .then((payload) => {
        if (!active) return;
        setCodexFiles(withCodexDefaults(payload));
        setCodexMessage("已读取 Codex 配置");
      })
      .catch((cause) => {
        if (!active) return;
        setCodexMessage(cause instanceof Error ? cause.message : "codex-runtime-load-failed");
      });
    return () => {
      active = false;
    };
  }, []);

  async function persist() {
    if (!settings) return;
    try {
      const result = await saveSettings(settings);
      setSettings(result);
      setMessage("设置已保存");
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "save-failed");
    }
  }

  async function refreshCodexRuntime() {
    try {
      const payload = await getCodexRuntimeFiles();
      setCodexFiles(withCodexDefaults(payload));
      setCodexMessage("已刷新 Codex 文件");
    } catch (cause) {
      setCodexMessage(cause instanceof Error ? cause.message : "codex-runtime-refresh-failed");
    }
  }

  async function persistCodexRuntime() {
    if (!codexFiles) return;
    try {
      const payload = await saveCodexRuntimeFiles({
        config_text: codexFiles.config_text,
        auth_text: codexFiles.auth_text,
      });
      setCodexFiles(withCodexDefaults(payload));
      setCodexMessage("Codex 文件已保存");
    } catch (cause) {
      setCodexMessage(cause instanceof Error ? cause.message : "codex-runtime-save-failed");
    }
  }

  async function persistQuickSettings() {
    if (!codexFiles) return;
    try {
      const payload = await saveCodexQuickSettings(codexFiles.quick_settings);
      setCodexFiles(withCodexDefaults(payload));
      setCodexMessage("基础设置已写入 config.toml");
    } catch (cause) {
      setCodexMessage(cause instanceof Error ? cause.message : "codex-quick-save-failed");
    }
  }

  return (
    <div className="page-stack">
      <Panel title="基础配置" description="第一版先开放自动刷新、分流策略和阈值。">
        <div className="settings-grid">
          <label className="settings-row">
            <span className="settings-label">自动刷新</span>
            <input
              type="checkbox"
              checked={settings?.auto_refresh_enabled ?? false}
              onChange={(event) =>
                settings
                  ? setSettings({ ...settings, auto_refresh_enabled: event.target.checked })
                  : null
              }
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">刷新间隔（秒）</span>
            <input
              type="number"
              value={settings?.refresh_interval_seconds ?? 600}
              onChange={(event) =>
                settings
                  ? setSettings({
                      ...settings,
                      refresh_interval_seconds: Number(event.target.value),
                    })
                  : null
              }
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">优先分流</span>
            <input
              type="checkbox"
              checked={settings?.prefer_separation ?? true}
              onChange={(event) =>
                settings
                  ? setSettings({ ...settings, prefer_separation: event.target.checked })
                  : null
              }
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">软阈值 5h</span>
            <input
              type="number"
              value={settings?.thresholds.five_hour_switch_at ?? 80}
              onChange={(event) =>
                settings
                  ? setSettings({
                      ...settings,
                      thresholds: {
                        ...settings.thresholds,
                        five_hour_switch_at: Number(event.target.value),
                      },
                    })
                  : null
              }
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">硬阈值 5h</span>
            <input
              type="number"
              value={settings?.thresholds.hard_five_hour_switch_at ?? 90}
              onChange={(event) =>
                settings
                  ? setSettings({
                      ...settings,
                      thresholds: {
                        ...settings.thresholds,
                        hard_five_hour_switch_at: Number(event.target.value),
                      },
                    })
                  : null
              }
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">软阈值 Week</span>
            <input
              type="number"
              value={settings?.thresholds.weekly_switch_at ?? 90}
              onChange={(event) =>
                settings
                  ? setSettings({
                      ...settings,
                      thresholds: {
                        ...settings.thresholds,
                        weekly_switch_at: Number(event.target.value),
                      },
                    })
                  : null
              }
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">硬阈值 Week</span>
            <input
              type="number"
              value={settings?.thresholds.hard_weekly_switch_at ?? 95}
              onChange={(event) =>
                settings
                  ? setSettings({
                      ...settings,
                      thresholds: {
                        ...settings.thresholds,
                        hard_weekly_switch_at: Number(event.target.value),
                      },
                    })
                  : null
              }
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">静默分钟数</span>
            <input
              type="number"
              value={settings?.inactive_minutes ?? 3}
              onChange={(event) =>
                settings
                  ? setSettings({
                      ...settings,
                      inactive_minutes: Number(event.target.value),
                    })
                  : null
              }
            />
          </label>
        </div>
        <div className="toolbar-row">
          <button type="button" className="action-button" onClick={() => void persist()}>
            保存设置
          </button>
          <span className="toolbar-note">{message}</span>
        </div>
      </Panel>

      <Panel title="当前策略" description="这里只保留最关键的自动调度说明。">
        <div className="maintenance-card">
          <p>先分流，再按剩余额度排序</p>
          <span>没有其他候选账号时允许共用同一个账号</span>
        </div>
      </Panel>

      <Panel
        title="Codex 文件"
        description="这里可以直接查看、修改并保存 ~/.codex/config.toml 和 ~/.codex/auth.json。"
      >
        <div className="form-grid codex-quick-grid">
          <label className="form-field">
            <span>基础地址</span>
            <input
              value={codexFiles?.quick_settings.openai_base_url ?? ""}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      quick_settings: {
                        ...codexFiles.quick_settings,
                        openai_base_url: event.target.value || null,
                      },
                    })
                  : null
              }
              placeholder="https://www.ananapi.com"
            />
          </label>
          <label className="form-field">
            <span>模型</span>
            <input
              value={codexFiles?.quick_settings.model ?? ""}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      quick_settings: {
                        ...codexFiles.quick_settings,
                        model: event.target.value || null,
                      },
                    })
                  : null
              }
              placeholder="gpt-5.4"
            />
          </label>
          <label className="form-field">
            <span>评审模型</span>
            <input
              value={codexFiles?.quick_settings.review_model ?? ""}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      quick_settings: {
                        ...codexFiles.quick_settings,
                        review_model: event.target.value || null,
                      },
                    })
                  : null
              }
              placeholder="gpt-5.4"
            />
          </label>
          <label className="form-field">
            <span>推理强度</span>
            <input
              value={codexFiles?.quick_settings.model_reasoning_effort ?? ""}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      quick_settings: {
                        ...codexFiles.quick_settings,
                        model_reasoning_effort: event.target.value || null,
                      },
                    })
                  : null
              }
              placeholder="xhigh"
            />
          </label>
          <label className="settings-row form-field-wide codex-toggle-row">
            <div className="codex-toggle-copy">
              <span className="settings-label">Fast 模式</span>
              <span className="toolbar-note">
                勾上后写入 `service_tier = "fast"`，取消后改成 `flex`。
              </span>
            </div>
            <input
              type="checkbox"
              checked={codexFiles?.quick_settings.fast_mode_enabled ?? false}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      quick_settings: {
                        ...codexFiles.quick_settings,
                        fast_mode_enabled: event.target.checked,
                      },
                    })
                  : null
              }
            />
          </label>
          <label className="form-field">
            <span>上下文窗口（k）</span>
            <input
              inputMode="numeric"
              value={codexFiles ? toKUnit(codexFiles.quick_settings.model_context_window, DEFAULT_CONTEXT_WINDOW) : ""}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      quick_settings: {
                        ...codexFiles.quick_settings,
                        model_context_window: event.target.value
                          ? Number(event.target.value) * 1000
                          : DEFAULT_CONTEXT_WINDOW,
                      },
                    })
                  : null
              }
              placeholder="400"
            />
          </label>
          <label className="form-field">
            <span>自动压缩阈值（k）</span>
            <input
              inputMode="numeric"
              value={
                codexFiles
                  ? toKUnit(
                      codexFiles.quick_settings.model_auto_compact_token_limit,
                      DEFAULT_AUTO_COMPACT_TOKEN_LIMIT,
                    )
                  : ""
              }
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      quick_settings: {
                        ...codexFiles.quick_settings,
                        model_auto_compact_token_limit: event.target.value
                          ? Number(event.target.value) * 1000
                          : DEFAULT_AUTO_COMPACT_TOKEN_LIMIT,
                      },
                    })
                  : null
              }
              placeholder="300"
            />
          </label>
        </div>
        <div className="toolbar-row">
          <button type="button" className="action-button" onClick={() => void persistQuickSettings()}>
            应用基础设置
          </button>
          <button type="button" className="action-button" onClick={() => void refreshCodexRuntime()}>
            重新读取文件
          </button>
          <span className="toolbar-note">{codexMessage}</span>
        </div>

        <div className="codex-editor-grid">
          <label className="form-field">
            <span>config.toml 原文</span>
            <textarea
              rows={16}
              value={codexFiles?.config_text ?? ""}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      config_text: event.target.value,
                    })
                  : null
              }
              placeholder='model = "gpt-5.4"'
            />
          </label>
          <label className="form-field">
            <span>auth.json 原文</span>
            <textarea
              rows={16}
              value={codexFiles?.auth_text ?? ""}
              onChange={(event) =>
                codexFiles
                  ? setCodexFiles({
                      ...codexFiles,
                      auth_text: event.target.value,
                    })
                  : null
              }
              placeholder='{\n  "auth_mode": "chatgpt"\n}'
            />
          </label>
        </div>
        <div className="toolbar-row">
          <button type="button" className="action-button action-button-primary" onClick={() => void persistCodexRuntime()}>
            保存文件
          </button>
          <span className="toolbar-note">保存后会立刻回读文件内容，页面会同步显示最新结果。</span>
        </div>
      </Panel>
    </div>
  );
}
