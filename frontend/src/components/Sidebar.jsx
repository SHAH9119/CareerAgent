import { Button } from "./Button";
import { Icon } from "./icons";
import "./Sidebar.css";

const navItems = [
  { id: "pipeline", label: "Dashboard", icon: "pipeline" },
  { id: "intelligence", label: "Agent Run", icon: "brain" },
  { id: "resumes", label: "Tailoring", icon: "doc" },
  { id: "settings", label: "Settings", icon: "gear" },
];

export function Sidebar({
  candidate,
  activeNav = "pipeline",
  onNav,
  onProfileClick,
  onNewRun,
  onLogout,
}) {
  const initials = candidate?.initials || "CA";

  return (
    <header className="app-bar">
      <div className="app-bar-brand">
        <span className="app-bar-logo" aria-hidden>
          <Icon name="sparkle" size={15} />
        </span>
        <span className="app-bar-name">CareerAgent</span>
      </div>

      <nav className="app-bar-nav" aria-label="Main">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onNav?.(item.id)}
            className={`app-bar-tab ${activeNav === item.id ? "app-bar-tab-active" : ""}`}
          >
            <Icon name={item.icon} size={15} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="app-bar-actions">
        <Button
          variant="primary"
          size="sm"
          icon={<Icon name="plus" size={13} />}
          onClick={onNewRun}
        >
          New Run
        </Button>
        <button
          type="button"
          className="app-bar-avatar"
          onClick={onProfileClick}
          title={candidate?.name || "Profile"}
          aria-label="Open profile"
        >
          {initials}
        </button>
        <button type="button" className="app-bar-logout" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}
