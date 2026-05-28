import { useMemo, useState } from "react";
import { JobCard } from "./JobCard";
import "./JobQueue.css";

const TABS = [
  { id: "all", label: "All", hint: "Every job pulled from the selected sources." },
  { id: "apply", label: "Apply", hint: "Strong fit. Worth a tailored application." },
  { id: "maybe", label: "Maybe", hint: "Decent fit with gaps. Worth a quick review." },
  { id: "skip", label: "Skip", hint: "Weak fit or wrong domain. Skip unless strategic." },
];

export function JobQueue({
  jobs = [],
  selectedId,
  onSelect,
  stats,
  counts,
  loading = false,
  error = "",
  search = "",
  onTailor,
}) {
  const tabCounts = counts || {
    all: jobs.length,
    apply: jobs.filter((job) => job.verdict === "APPLY").length,
    maybe: jobs.filter((job) => job.verdict === "MAYBE").length,
    skip: jobs.filter((job) => job.verdict === "SKIP").length,
  };

  // userTab is null until the user explicitly clicks a tab. Until then we
  // derive the displayed tab from counts so the dashboard never opens to an
  // empty "Apply" view when there are Maybe roles to review.
  const [userTab, setUserTab] = useState(null);
  const tab = userTab ?? (
    tabCounts.apply > 0 ? "apply" : tabCounts.maybe > 0 ? "maybe" : "all"
  );
  const setTab = setUserTab;

  const visibleJobs = useMemo(() => {
    const term = search.trim().toLowerCase();
    return jobs.filter((job) => {
      const tabMatches = tab === "all" || job.verdict.toLowerCase() === tab;
      if (!tabMatches) return false;
      if (!term) return true;
      return [job.title, job.company, job.location, ...(job.matched_skills || []), ...(job.missing_skills || [])]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [jobs, search, tab]);

  return (
    <section className="queue">
      <header className="queue-stats">
        <Stat label="Scanned" value={stats?.scanned ?? jobs.length} />
        <Stat label="Shortlist" value={stats?.filtered ?? tabCounts.apply + tabCounts.maybe} />
        <Stat label="Avg Match" value={`${stats?.avgMatch ?? 0}%`} accent="brand" />
      </header>

      <div className="queue-tabs">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            title={item.hint}
            onClick={() => setTab(item.id)}
            className={`queue-tab ${tab === item.id ? "queue-tab-active" : ""}`}
          >
            {item.label}
            <span className="queue-tab-count">({tabCounts[item.id] || 0})</span>
          </button>
        ))}
      </div>

      <div className="queue-list">
        {loading ? (
          <div className="queue-empty">Loading real pipeline results...</div>
        ) : error ? (
          <div className="queue-empty queue-error">{error}</div>
        ) : visibleJobs.length === 0 ? (
          <div className="queue-empty">No jobs in this view yet.</div>
        ) : (
          visibleJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              selected={job.id === selectedId}
              onSelect={() => onSelect?.(job)}
              onTailor={onTailor}
            />
          ))
        )}
      </div>
    </section>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${accent === "brand" ? "stat-brand" : ""}`}>
        {value}
      </div>
    </div>
  );
}
