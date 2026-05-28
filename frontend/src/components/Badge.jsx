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
    APPLY: { tone: "apply", label: "Apply" },
    MAYBE: { tone: "maybe", label: "Maybe" },
    SKIP: { tone: "skip", label: "Skip" },
    STRETCH: { tone: "stretch", label: "Stretch" },
  };
  const config = map[verdict] || map.MAYBE;
  return <Badge tone={config.tone}>{config.label}</Badge>;
}
