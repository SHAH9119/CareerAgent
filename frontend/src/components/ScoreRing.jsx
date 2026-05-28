import "./ScoreRing.css";

export function ScoreRing({ value = 0, size = 130, label = "Match", tone = "good" }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  const colors = {
    good: "var(--good)",
    warn: "var(--warn)",
    bad: "var(--danger)",
    brand: "var(--brand)",
  };

  return (
    <div className="ring-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--bg-soft)"
          strokeWidth="6"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors[tone] || colors.good}
          strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="ring-text">
        <div className="ring-value">{value}</div>
        <div className="ring-label">{label}</div>
      </div>
    </div>
  );
}
