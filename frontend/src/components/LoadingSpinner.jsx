import "./LoadingSpinner.css";

export function LoadingSpinner({ label = "Loading..." }) {
  return (
    <div className="loading-screen">
      <div className="loading-spinner" aria-hidden />
      <p>{label}</p>
    </div>
  );
}
