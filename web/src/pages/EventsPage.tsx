// 这个页面展示事件流和时间顺序信息，适合做审计和排障入口。

import { useEffect, useState } from "react";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import { listEvents } from "../lib/api";
import type { EventRecord } from "../lib/types";
import type { StatusBadgeProps } from "../components/StatusBadge";

function resolveTone(level: string): StatusBadgeProps["tone"] {
  if (level === "warning") return "warning";
  if (level === "danger" || level === "critical") return "danger";
  if (level === "info") return "neutral";
  return "success";
}

// 渲染事件列表页面。
export function EventsPage() {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [message, setMessage] = useState("加载中");

  useEffect(() => {
    let active = true;
    listEvents()
      .then((payload) => {
        if (!active) return;
        setEvents(payload);
        setMessage(`最近 ${payload.length} 条事件`);
      })
      .catch((cause) => {
        if (!active) return;
        setMessage(cause instanceof Error ? cause.message : "load-failed");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="page-stack">
      <Panel title="事件流" description={message}>
        <div className="event-list">
          {events.map((event) => (
            <article key={`${event.created_at}-${event.reason}`} className="event-row">
              <div className="event-time">
                {new Date(event.created_at * 1000).toLocaleTimeString()}
              </div>
              <div className="event-body">
                <div className="event-head">
                  <strong>{event.target ?? event.type}</strong>
                  <StatusBadge label={event.reason} tone={resolveTone(event.level)} />
                </div>
                <p>{event.message}</p>
              </div>
            </article>
          ))}
          {events.length === 0 ? (
            <article className="event-row">
              <div className="event-time">--:--</div>
              <div className="event-body">
                <div className="event-head">
                  <strong>暂无事件</strong>
                  <StatusBadge label="empty" tone="neutral" />
                </div>
                <p>服务还没有写入事件流，后续调度或手动操作后会出现在这里。</p>
              </div>
            </article>
          ) : null}
        </div>
      </Panel>
    </div>
  );
}
