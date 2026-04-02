// 这个组件用于把状态信息压缩成可扫读的标签。

export interface StatusBadgeProps {
  label: string;
  tone?: "neutral" | "success" | "warning" | "danger";
}

// 渲染状态标签。
export function StatusBadge({ label, tone = "neutral" }: StatusBadgeProps) {
  return <span className={`status-badge status-${tone}`}>{label}</span>;
}
