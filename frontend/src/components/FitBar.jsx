import "./FitBar.css";

export function FitBar({ label, value }) {
  const tone =
    value >= 80 ? "fit-good" : value >= 60 ? "fit-warn" : "fit-bad";

  return (
    <div className="fit-bar">
      <div className="fit-bar-header">
        <span className="fit-bar-label">{label}</span>
        <span className="fit-bar-value">{value}</span>
      </div>
      <div className="fit-bar-track">
        <div
          className={`fit-bar-fill ${tone}`}
          style={{ width: `${Math.max(2, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}
