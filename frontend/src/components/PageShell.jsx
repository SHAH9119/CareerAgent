import { Sidebar } from "./Sidebar";
import "./PageShell.css";

export function PageShell({
  activeNav,
  candidate,
  onNav,
  onProfileClick,
  onNewRun,
  onLogout,
  children,
}) {
  return (
    <div className="shell">
      <Sidebar
        candidate={candidate}
        activeNav={activeNav}
        onNav={onNav}
        onProfileClick={onProfileClick}
        onNewRun={onNewRun}
        onLogout={onLogout}
      />
      <div className="shell-body">{children}</div>
    </div>
  );
}
