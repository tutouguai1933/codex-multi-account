// 这个页面负责读取和保存调度设置。

import { useEffect, useState } from "react";
import { Panel } from "../components/Panel";
import { getSettings, saveSettings } from "../lib/api";
import type { SchedulerSettings } from "../lib/types";

// 渲染设置页面。
export function SettingsPage() {
  const [settings, setSettings] = useState<SchedulerSettings | null>(null);
  const [message, setMessage] = useState("加载中");

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
    </div>
  );
}
