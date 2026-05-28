import { useMemo, useState } from "react";
import { JobCard } from "./JobCard";
import "./JobQueue.css";

const TABS = [
  { id: "all", label: "All" },
  { id: "apply", label: "Apply" },
  { id: "maybe", label: "Maybe" },
  { id: "skip", label: "Skip" },
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
      <header className="queue-head">
        <div className="queue-stats">
          <Stat label="Scanned" value={stats?.scanned ?? jobs.length} />
          <Stat label="Shortlist" value={stats?.filtered ?? tabCounts.apply + tabCounts.maybe} />
          <Stat label="Avg fit" value={`${stats?.avgMatch ?? 0}%`} accent />
        </div>
        <div className="queue-tabs" role="tablist">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
              className={`queue-tab queue-tab-${item.id} ${tab === item.id ? "queue-tab-active" : ""}`}
            >
              {item.label}
              <span className="queue-tab-count">{tabCounts[item.id] || 0}</span>
            </button>
          ))}
        </div>
      </header>

      <div className="queue-list">
        {loading ? (
          <div className="queue-empty">Loading pipeline results…</div>
        ) : error ? (
          <div className="queue-empty queue-error">{error}</div>
        ) : visibleJobs.length === 0 ? (
          <div className="queue-empty">No jobs in this view. Run the agent or switch tabs.</div>
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
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${accent ? "stat-accent" : ""}`}>{value}</span>
    </div>
  );
}
