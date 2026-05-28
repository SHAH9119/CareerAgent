import { Badge } from "./Badge";
import { Button } from "./Button";
import { Icon } from "./icons";
import "./SearchParameters.css";

const WORKPLACE_OPTIONS = [
  { id: "remote", label: "Remote" },
  { id: "hybrid", label: "Hybrid" },
  { id: "on-site", label: "On-site" },
];

function sanitizeQuery(value) {
  return value
    .replace(/[<>{}$`\\;|&!#%()[\]]/g, "")
    .slice(0, 500);
}

export function SearchParameters({
  config,
  sources = [],
  running = false,
  status,
  onConfigChange,
  onUpload,
  onRun,
}) {
  const update = (patch) => onConfigChange?.({ ...config, ...patch });
  const selectedSources = config.sources || [];
  const selectedWorkplaces = config.workplace_types?.length
    ? config.workplace_types
    : ["remote", "hybrid", "on-site"];
  const queries = config.custom_queries || "";

  const toggleSource = (sourceId) => {
    const next = selectedSources.includes(sourceId)
      ? selectedSources.filter((id) => id !== sourceId)
      : [...selectedSources, sourceId];
    update({ sources: next.length ? next : ["remotive"] });
  };

  const toggleWorkplace = (workplaceId) => {
    const next = selectedWorkplaces.includes(workplaceId)
      ? selectedWorkplaces.filter((id) => id !== workplaceId)
      : [...selectedWorkplaces, workplaceId];
    const safeNext = next.length ? next : ["remote", "hybrid", "on-site"];
    update({
      workplace_types: safeNext,
      mode: safeNext.length === 3 ? "all" : safeNext.join(","),
      remote: safeNext.length === 1 && safeNext[0] === "remote",
      workplace_type: safeNext.length === 1 ? safeNext[0] : "",
    });
  };

  return (
    <aside className="params">
      <h2 className="params-heading">Search</h2>

      <section className="param-block">
        <label className="param-label">Resume</label>
        <label className="file-control">
          <input
            type="file"
            accept=".pdf"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload?.(file);
            }}
          />
          <Icon name="doc" size={12} />
          <span className="file-name">{config.resume_path || "Upload PDF"}</span>
        </label>
      </section>

      <section className="param-block">
        <label className="param-label">Workplace</label>
        <div className="chip-group">
          {WORKPLACE_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={`chip ${selectedWorkplaces.includes(opt.id) ? "chip-active" : ""}`}
              onClick={() => toggleWorkplace(opt.id)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </section>

      <section className="param-block">
        <label className="param-label" htmlFor="param-location">
          Location
        </label>
        <input
          id="param-location"
          className="param-input"
          value={config.location || ""}
          onChange={(event) => update({ location: event.target.value })}
          placeholder="City or country"
        />
      </section>

      <section className="param-block">
        <label className="param-label" htmlFor="param-queries">
          Custom queries
        </label>
        <textarea
          id="param-queries"
          className="param-textarea"
          rows={2}
          value={queries}
          onChange={(event) => update({ custom_queries: sanitizeQuery(event.target.value) })}
          placeholder="ML Engineer, Python Developer"
          maxLength={500}
        />
        <p className="param-hint">Comma-separated. Leave empty to auto-generate from resume.</p>
      </section>

      <section className="param-block param-block-inline">
        <label className="param-label" htmlFor="param-max-jobs">
          Max jobs
        </label>
        <input
          id="param-max-jobs"
          className="param-input param-input-narrow"
          type="number"
          min={5}
          max={100}
          value={config.target_jobs}
          onChange={(event) => update({ target_jobs: Number(event.target.value) })}
        />
      </section>

      {selectedSources.includes("adzuna") && (
        <section className="param-block param-block-inline">
          <label className="param-label" htmlFor="param-adzuna">
            Adzuna country
          </label>
          <input
            id="param-adzuna"
            className="param-input param-input-narrow"
            value={config.adzuna_country || "us"}
            onChange={(event) =>
              update({ adzuna_country: event.target.value.replace(/[^a-z]/g, "").slice(0, 2) })
            }
            placeholder="us"
            maxLength={2}
          />
        </section>
      )}

      <section className="param-block">
        <label className="param-label">Sources</label>
        <div className="sources">
          {sources
            .filter((s) => s.status !== "prototype")
            .map((source) => (
              <label key={source.id} className="source-row">
                <input
                  type="checkbox"
                  checked={selectedSources.includes(source.id)}
                  onChange={() => toggleSource(source.id)}
                />
                <span className="source-copy">
                  <span className="source-label">{source.label}</span>
                  {source.description && (
                    <span className="source-description">{source.description}</span>
                  )}
                </span>
                {source.needs_api_key && (
                  <Badge tone="info" size="sm">
                    Key
                  </Badge>
                )}
              </label>
            ))}
        </div>
      </section>

      <details className="param-advanced">
        <summary>Advanced</summary>
        <div className="param-advanced-body">
          <label className="param-check">
            <input
              type="checkbox"
              checked={Boolean(config.skip_parse)}
              onChange={(event) => update({ skip_parse: event.target.checked })}
            />
            Skip resume parsing
          </label>
          <label className="param-check">
            <input
              type="checkbox"
              checked={Boolean(config.skip_scrape)}
              onChange={(event) => update({ skip_scrape: event.target.checked })}
            />
            Re-score saved jobs only
          </label>
        </div>
      </details>

      {status?.message && (
        <div className={`run-status run-status-${status.stage}`}>{status.message}</div>
      )}

      <Button
        className="params-run-btn"
        variant="primary"
        size="md"
        icon={<Icon name="play" size={12} />}
        onClick={onRun}
        disabled={running}
      >
        {running ? "Running…" : "Run agent"}
      </Button>
    </aside>
  );
}
