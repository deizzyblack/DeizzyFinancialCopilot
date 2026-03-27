const COLORS: Record<string, string> = {
  FLAG: "#ef4444",
  REVIEW_REQUIRED: "#eab308",
  AUTO_READY: "#22c55e",
  APPROVED: "#16a34a",
  REJECTED: "#dc2626",
  PENDING: "#6b7280",
};

interface Props {
  label: string;
}

export function StatusBadge({ label }: Props) {
  const bg = COLORS[label] ?? "#6b7280";

  return (
    <span className="status-badge" style={{ backgroundColor: bg }}>
      {label.replace("_", " ")}
    </span>
  );
}
