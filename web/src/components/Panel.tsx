// 这个组件统一承载信息块，保持页面密度和视觉节奏一致。

import type { ReactNode } from "react";

export interface PanelProps {
  title: string;
  description?: string;
  children: ReactNode;
  tone?: "default" | "accent";
}

// 渲染一个通用内容面板。
export function Panel({ title, description, children, tone = "default" }: PanelProps) {
  return (
    <section className={`panel${tone === "accent" ? " panel-accent" : ""}`}>
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}
