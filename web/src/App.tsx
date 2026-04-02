// 这个文件负责串联四个页面，并管理最小可用的本地视图切换。

import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { getOverview } from "./lib/api";
import type { OverviewResponse } from "./lib/types";
import { AccountsPage } from "./pages/AccountsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EventsPage } from "./pages/EventsPage";
import { SettingsPage } from "./pages/SettingsPage";

type ViewKey = "dashboard" | "accounts" | "events" | "settings";

const navigation = [
  { key: "dashboard", label: "总览" },
  { key: "accounts", label: "账户" },
  { key: "events", label: "事件" },
  { key: "settings", label: "设置" },
] as const;

function resolveAllocationLabel(mode: "unassigned" | "partial" | "shared" | "separated") {
  if (mode === "unassigned") return "未分配";
  if (mode === "partial") return "部分分配";
  if (mode === "separated") return "已分流";
  return "共用中";
}

function resolvePage(view: ViewKey) {
  if (view === "accounts") return <AccountsPage />;
  if (view === "events") return <EventsPage />;
  if (view === "settings") return <SettingsPage />;
  return <DashboardPage />;
}

// 渲染应用根视图。
export default function App() {
  const [view, setView] = useState<ViewKey>("dashboard");
  const [counts, setCounts] = useState({ accounts: 0, events: 0 });
  const [statusNote, setStatusNote] = useState("加载中");

  useEffect(() => {
    let active = true;
    getOverview()
      .then((overview) => {
        if (!active) return;
        setCounts({
          accounts: overview.summary.totalAccounts,
          events: overview.recentEvents.length,
        });
        setStatusNote(resolveAllocationLabel(overview.summary.allocationMode));
      })
      .catch(() => {
        if (!active) return;
        setStatusNote("未连接");
      });
    return () => {
      active = false;
    };
  }, [view]);

  function handleOverviewChange(overview: OverviewResponse) {
    setCounts({
      accounts: overview.summary.totalAccounts,
      events: overview.recentEvents.length,
    });
    setStatusNote(resolveAllocationLabel(overview.summary.allocationMode));
  }

  return (
    <AppShell
      title="Codex Multi Account"
      subtitle="OpenClaw / Codex 账号调度台"
      endpoint="127.0.0.1:9001"
      statusNote={statusNote}
      counts={counts}
      navigation={navigation.map((item) => ({
        ...item,
        active: item.key === view,
      }))}
      onNavigate={(key) => setView(key as ViewKey)}
    >
      {view === "dashboard" ? <DashboardPage onOverviewChange={handleOverviewChange} /> : resolvePage(view)}
    </AppShell>
  );
}
