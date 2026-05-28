import { Button } from "./Button";
import { Icon } from "./icons";
import "./TopBar.css";

export function TopBar({
  search = "",
  onSearch,
  onRun,
  onRerun,
  running = false,
  status,
}) {
  return (
    <div className="dashboard-toolbar">
      <div className="toolbar-search">
        <Icon name="search" size={14} />
        <input
          value={search}
          onChange={(event) => onSearch?.(event.target.value)}
          placeholder="Search jobs, companies, skills..."
          aria-label="Search jobs"
        />
      </div>

      <div className="toolbar-actions">
        {status?.stage && status.stage !== "idle" && (
          <span className={`toolbar-status toolbar-status-${status.stage}`}>
            {status.message || status.stage}
          </span>
        )}
        <Button
          variant="outline"
          size="sm"
          icon={<Icon name="refresh" size={13} />}
          onClick={onRerun}
          disabled={running}
        >
          Re-run
        </Button>
        <Button
          variant="primary"
          size="sm"
          icon={<Icon name="play" size={12} />}
          onClick={onRun}
          disabled={running}
        >
          {running ? "Running…" : "Run agent"}
        </Button>
      </div>
    </div>
  );
}
