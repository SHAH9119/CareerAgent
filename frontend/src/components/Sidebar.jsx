import { Button } from "./Button";
import { Icon } from "./icons";
import "./Sidebar.css";

const navItems = [
  { id: "pipeline", label: "Dashboard", icon: "pipeline", hint: "Jobs, scores, and tailoring queue." },
  { id: "intelligence", label: "Agent Run", icon: "brain", hint: "Pipeline progress and logs." },
  { id: "resumes", label: "Tailoring", icon: "doc", hint: "Tailored resume drafts." },
  { id: "settings", label: "Settings", icon: "gear", hint: "Domain rules and scoring weights." },
];

export function Sidebar({
  candidate,
  activeNav = "pipeline",
  onNav,
  onProfileClick,
  onNewRun,
  onLogout,
}) {
  const displayCandidate = candidate || {
    name: "Candidate",
    initials: "CA",
    title: "Profile not loaded",
    location: "Run the agent",
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="brand">
          <div className="brand-mark">
            <Icon name="sparkle" size={16} />
          </div>
          <div>
            <div className="brand-name">CareerAgent</div>
            <div className="brand-sub">AI Intelligence</div>
          </div>
        </div>

        <button
          type="button"
          className="profile-card"
          onClick={onProfileClick}
          title="Edit profile"
        >
          <div className="profile-avatar">{displayCandidate.initials}</div>
          <div className="profile-body">
            <div className="profile-name">{displayCandidate.name}</div>
            <div className="profile-meta">{displayCandidate.title}</div>
            <div className="profile-meta light">
              <Icon name="pin" size={11} /> {displayCandidate.location}
            </div>
          </div>
        </button>

        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onNav?.(item.id)}
              title={item.hint}
              className={`nav-item ${activeNav === item.id ? "nav-item-active" : ""}`}
            >
              <Icon name={item.icon} size={16} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="sidebar-bottom">
        <Button
          variant="primary"
          size="md"
          icon={<Icon name="plus" size={14} />}
          onClick={onNewRun}
        >
          New Run
        </Button>
        <button type="button" className="logout" onClick={onLogout}>
          <Icon name="x" size={13} />
          Logout
        </button>
      </div>
    </aside>
  );
}
