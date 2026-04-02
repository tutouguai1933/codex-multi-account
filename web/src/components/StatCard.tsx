// 这个组件用于在控制台里呈现高密度的关键指标。

export interface StatCardProps {
  label: string;
  value: string;
  note: string;
}

// 渲染单个指标卡片。
export function StatCard({ label, value, note }: StatCardProps) {
  return (
    <article className="stat-card">
      <p className="stat-label">{label}</p>
      <strong className="stat-value">{value}</strong>
      <p className="stat-note">{note}</p>
    </article>
  );
}
