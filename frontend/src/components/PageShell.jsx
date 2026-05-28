import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import "./PageShell.css";

export function PageShell({
  activeNav,
  candidate,
  onNav,
  onProfileClick,
  onNewRun,
  showTopBar = true,
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
      />
      <div className="shell-body">
        {showTopBar && <TopBar candidate={candidate} />}
        <main className="shell-main">{children}</main>
      </div>
    </div>
  );
}
