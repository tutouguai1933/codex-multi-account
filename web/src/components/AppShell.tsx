// 这个组件提供统一的控制台外壳，包括标题栏、导航和内容容器。

import type { ReactNode } from "react";

export interface AppShellProps {
  title: string;
  subtitle: string;
  endpoint?: string;
  statusNote?: string;
  counts?: {
    accounts: number;
    events: number;
  };
  navigation: Array<{
    key: string;
    label: string;
    active: boolean;
  }>;
  onNavigate: (key: string) => void;
  children: ReactNode;
}

// 渲染统一的应用框架，页面内容在这里切换。
export function AppShell({
  title,
  subtitle,
  endpoint = "127.0.0.1:9001",
  statusNote = "等待连接",
  counts = { accounts: 0, events: 0 },
  navigation,
  onNavigate,
  children,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="eyebrow">multi-account console</p>
          <h1>{title}</h1>
          <p className="brand-copy">{subtitle}</p>
          <div className="brand-meta-row">
            <span className="mini-tag brand-endpoint">{endpoint}</span>
            <span className="mini-tag">{statusNote}</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="主导航">
          {navigation.map((item) => (
            <button
              key={item.key}
              className={`nav-item${item.active ? " is-active" : ""}`}
              type="button"
              onClick={() => onNavigate(item.key)}
            >
              <span>{item.label}</span>
              <span className="nav-arrow">→</span>
            </button>
          ))}
        </nav>

        <section className="sidebar-panel">
          <p className="panel-label">运行状态</p>
          <div className="sidebar-stat">
            <strong>账号池</strong>
            <span>{counts.accounts} 个</span>
          </div>
          <div className="sidebar-stat">
            <strong>事件</strong>
            <span>{counts.events} 条</span>
          </div>
        </section>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <p className="eyebrow">ops workspace</p>
            <h2>{title}</h2>
          </div>
          <div className="topbar-meta">
            <span>{statusNote}</span>
            <span>{endpoint}</span>
          </div>
        </header>

        <section className="content-frame">{children}</section>
      </main>
    </div>
  );
}
