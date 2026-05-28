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
    .replace(/[<>{}$`\\;|&!#%()\[\]]/g, "")
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
  const queries = config.custom_queries || "";

  const toggleSource = (sourceId) => {
    const next = selectedSources.includes(sourceId)
      ? selectedSources.filter((id) => id !== sourceId)
      : [...selectedSources, sourceId];
    update({ sources: next.length ? next : ["remotive"] });
  };

  return (
    <aside className="params">
      <h2 className="params-heading">Search Parameters</h2>

      {/* --- Section 1: Resume --- */}
      <section className="param-section">
        <h3 className="section-title">Resume</h3>
        <label className="file-control">
          <input
            type="file"
            accept=".pdf"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload?.(file);
            }}
          />
          <Icon name="doc" size={13} />
          <span>{config.resume_path || "Upload PDF resume"}</span>
        </label>
      </section>

      {/* --- Section 2: Workplace Type --- */}
      <section className="param-section">
        <h3 className="section-title">Workplace Type</h3>
        <p className="section-hint">Pick one. This filters how the role is structured.</p>
        <div className="radio-group">
          {WORKPLACE_OPTIONS.map((opt) => (
            <label key={opt.id} className={`radio-pill ${config.mode === opt.id ? "radio-pill-active" : ""}`}>
              <input
                type="radio"
                name="workplace"
                value={opt.id}
                checked={config.mode === opt.id}
                onChange={() =>
                  update({
                    mode: opt.id,
                    remote: opt.id === "remote",
                    workplace_type: opt.id === "remote" ? "" : opt.id === "hybrid" ? "Hybrid" : "On-site",
                  })
                }
              />
              <span>{opt.label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* --- Section 3: Location --- */}
      <section className="param-section">
        <h3 className="section-title">Location</h3>
        <p className="section-hint">City or country. Leave empty for worldwide remote.</p>
        <input
          className="param-input"
          value={config.location || ""}
          onChange={(event) => update({ location: event.target.value })}
          placeholder="e.g. Karachi, Pakistan"
        />
      </section>

      {/* --- Section 4: Custom Queries --- */}
      <section className="param-section param-section-highlight">
        <h3 className="section-title">Custom Search Queries</h3>
        <p className="section-hint">
          Comma-separated job titles you want to search for.
          Leave empty and the agent will auto-generate queries from your resume.
        </p>
        <textarea
          className="param-textarea"
          rows={3}
          value={queries}
          onChange={(event) => update({ custom_queries: sanitizeQuery(event.target.value) })}
          placeholder="Machine Learning Engineer, Computer Vision, Python Developer"
          maxLength={500}
        />
      </section>

      {/* --- Section 5: Target Jobs --- */}
      <section className="param-section">
        <h3 className="section-title">How Many Jobs</h3>
        <p className="section-hint">Max jobs to collect and score per run.</p>
        <input
          className="param-input param-input-sm"
          type="number"
          min={5}
          max={100}
          value={config.target_jobs}
          onChange={(event) => update({ target_jobs: Number(event.target.value) })}
        />
        {selectedSources.includes("adzuna") && (
          <div className="adzuna-row">
            <label className="param-field">
              <span className="field-label">Adzuna Country Code</span>
              <input
                className="param-input param-input-sm"
                value={config.adzuna_country || "us"}
                onChange={(event) => update({ adzuna_country: event.target.value.replace(/[^a-z]/g, "").slice(0, 2) })}
                placeholder="us"
                maxLength={2}
              />
            </label>
          </div>
        )}
      </section>

      {/* --- Section 6: Data Sources --- */}
      <section className="param-section">
        <h3 className="section-title">Data Sources</h3>
        <p className="section-hint">Where to pull jobs from. Tick multiple if you want.</p>
        <div className="sources">
          {sources.filter((s) => s.status !== "prototype").map((source) => (
            <label key={source.id} className="source-row">
              <input
                type="checkbox"
                checked={selectedSources.includes(source.id)}
                onChange={() => toggleSource(source.id)}
              />
              <span className="source-info">
                <span className="source-label">{source.label}</span>
                {source.needs_api_key && <Badge tone="info" size="sm">Needs key</Badge>}
              </span>
            </label>
          ))}
        </div>
      </section>

      {/* --- Section 7: Advanced options --- */}
      <section className="param-section param-section-muted">
        <details>
          <summary className="section-title">Advanced</summary>
          <div className="advanced-body">
            <label className="param-check">
              <input
                type="checkbox"
                checked={Boolean(config.skip_parse)}
                onChange={(event) => update({ skip_parse: event.target.checked })}
              />
              Skip resume parsing (use saved profile)
            </label>
            <label className="param-check">
              <input
                type="checkbox"
                checked={Boolean(config.skip_scrape)}
                onChange={(event) => update({ skip_scrape: event.target.checked })}
              />
              Skip scraping (re-score saved jobs)
            </label>
          </div>
        </details>
      </section>

      {/* --- Run Button --- */}
      {status?.message && (
        <div className={`run-status run-status-${status.stage}`}>
          {status.message}
        </div>
      )}

      <Button
        variant="primary"
        size="md"
        icon={<Icon name="play" size={13} />}
        onClick={onRun}
        disabled={running}
      >
        {running ? "Running agent..." : "+ New Run"}
      </Button>
    </aside>
  );
}
