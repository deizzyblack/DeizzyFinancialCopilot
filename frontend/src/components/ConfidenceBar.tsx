interface Props {
  value: number;
  label?: string;
  showValue?: boolean;
}

export function ConfidenceBar({ value, label, showValue = true }: Props) {
  const pct = Math.round(value * 100);
  const color = value >= 0.85 ? "var(--green)" : value >= 0.5 ? "var(--amber)" : "var(--red)";

  return (
    <div className="confidence-bar">
      {label && <span className="confidence-label">{label}</span>}
      <div className="confidence-track">
        <div
          className="confidence-fill"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      {showValue && <span className="confidence-value">{value.toFixed(2)}</span>}
    </div>
  );
}
