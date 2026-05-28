import "./Card.css";

export function Card({ title, subtitle, icon, action, children, padded = true, className = "" }) {
  return (
    <section className={`card ${padded ? "card-padded" : ""} ${className}`}>
      {(title || action) && (
        <header className="card-header">
          {(title || subtitle) && (
            <div className="card-heading">
              {title && (
                <h3 className="card-title">
                  {icon && <span className="card-icon">{icon}</span>}
                  {title}
                </h3>
              )}
              {subtitle && <p className="card-subtitle">{subtitle}</p>}
            </div>
          )}
          {action && <div className="card-action">{action}</div>}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}
