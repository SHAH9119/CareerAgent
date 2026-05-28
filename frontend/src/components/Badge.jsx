import "./Badge.css";

const tones = {
  apply: "badge-apply",
  maybe: "badge-maybe",
  skip: "badge-skip",
  stretch: "badge-stretch",
  info: "badge-info",
  neutral: "badge-neutral",
  prototype: "badge-prototype",
  soon: "badge-soon",
  active: "badge-active",
};

export function Badge({ tone = "neutral", children, size = "md" }) {
  return (
    <span className={`badge ${tones[tone] || tones.neutral} badge-${size}`}>
      {children}
    </span>
  );
}

export function VerdictBadge({ verdict }) {
  const map = {
    APPLY: { tone: "apply", label: "APPLY" },
    MAYBE: { tone: "maybe", label: "MAYBE" },
    SKIP: { tone: "skip", label: "SKIP" },
    STRETCH: { tone: "stretch", label: "STRETCH" },
  };
  const config = map[verdict] || map.MAYBE;
  return <Badge tone={config.tone}>{config.label}</Badge>;
}
