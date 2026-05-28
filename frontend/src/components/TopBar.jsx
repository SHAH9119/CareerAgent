import { Button } from "./Button";
import { Icon } from "./icons";
import "./TopBar.css";

export function TopBar({
  candidate,
  search = "",
  onSearch,
  onRun,
  onRerun,
  running = false,
  status,
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="search-box">
          <Icon name="search" size={14} />
          <input
            value={search}
            onChange={(event) => onSearch?.(event.target.value)}
            placeholder="Search jobs, companies, skills..."
          />
          <kbd>Ctrl K</kbd>
        </div>
      </div>

      <div className="topbar-right">
        {status?.stage && (
          <span className={`topbar-status topbar-status-${status.stage}`}>
            {status.stage}
          </span>
        )}
        <Button
          variant="outline"
          size="md"
          icon={<Icon name="refresh" size={14} />}
          onClick={onRerun}
          disabled={running}
        >
          Re-run
        </Button>
        <Button
          variant="primary"
          size="md"
          icon={<Icon name="play" size={13} />}
          onClick={onRun}
          disabled={running}
        >
          {running ? "Running" : "Run agent"}
        </Button>
        <button type="button" className="icon-btn" aria-label="Settings">
          <Icon name="settings-dot" size={16} />
        </button>
        <button type="button" className="icon-btn" aria-label="Notifications">
          <Icon name="bell" size={16} />
          <span className="dot" />
        </button>
        <div className="avatar">{candidate?.initials || "CA"}</div>
      </div>
    </header>
  );
}
