import "./Button.css";

export function Button({
  variant = "ghost",
  size = "md",
  icon,
  iconRight,
  children,
  ...rest
}) {
  return (
    <button className={`btn btn-${variant} btn-${size}`} {...rest}>
      {icon && <span className="btn-ico">{icon}</span>}
      <span>{children}</span>
      {iconRight && <span className="btn-ico">{iconRight}</span>}
    </button>
  );
}
