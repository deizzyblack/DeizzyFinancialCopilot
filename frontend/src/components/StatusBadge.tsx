const DOT_COLORS: Record<string, string> = {
  FLAG: "var(--red)",
  REVIEW_REQUIRED: "var(--amber)",
  AUTO_READY: "var(--green)",
  APPROVED: "var(--green)",
  REJECTED: "var(--red)",
  PENDING: "var(--text-muted)",
};

const TEXT_COLORS: Record<string, string> = {
  FLAG: "var(--red-text)",
  REVIEW_REQUIRED: "var(--amber-text)",
  AUTO_READY: "var(--green-text)",
  APPROVED: "var(--green-text)",
  REJECTED: "var(--red-text)",
  PENDING: "var(--text-secondary)",
};

interface Props {
  label: string;
}

export function StatusBadge({ label }: Props) {
  const dot = DOT_COLORS[label] ?? "var(--text-muted)";
  const text = TEXT_COLORS[label] ?? "var(--text-secondary)";

  return (
    <span className="status-badge" style={{ color: text }}>
      <span className="sev-dot" style={{ background: dot }} />
      {label.replace("_", " ")}
    </span>
  );
}
