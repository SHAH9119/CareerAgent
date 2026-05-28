import "./Toggle.css";

export function Toggle({ checked, onChange, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange?.(!checked)}
      className={`toggle ${checked ? "toggle-on" : ""}`}
    >
      <span className="toggle-knob" />
    </button>
  );
}
