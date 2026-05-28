import { VerdictBadge } from "./Badge";
import { Button } from "./Button";
import { Icon } from "./icons";
import "./JobCard.css";

const verdictAccent = {
  APPLY: "card-accent-apply",
  MAYBE: "card-accent-maybe",
  SKIP: "card-accent-skip",
  STRETCH: "card-accent-stretch",
};

function oneLineReason(text = "") {
  const clean = String(text).replace(/\s+/g, " ").trim();
  if (clean.length <= 120) return clean;
  return `${clean.slice(0, 117)}…`;
}

export function JobCard({ job, selected, onSelect, onTailor }) {
  const matched = (job.matched_skills || []).slice(0, 4);
  const missing = (job.missing_skills || []).slice(0, 3);
  const reason = oneLineReason(job.ai_reason || job.detail_reason || "");

  return (
    <article
      onClick={onSelect}
      className={`job-card ${verdictAccent[job.verdict] || ""} ${selected ? "job-card-selected" : ""}`}
    >
      <header className="job-card-top">
        <div className="job-card-headline">
          <h3 className="job-title">{job.title}</h3>
          <div className="job-company">{job.company}</div>
          <div className="job-meta">
            {job.location && (
              <span>
                <Icon name="pin" size={11} /> {job.location}
              </span>
            )}
            {job.source && <span className="job-source">{job.source}</span>}
          </div>
        </div>
        <div className="job-card-aside">
          <VerdictBadge verdict={job.verdict} />
          <div className="job-score-wrap">
            <span className="job-score-label">Fit</span>
            <span className={`job-score job-score-${(job.verdict || "").toLowerCase()}`}>
              {job.final_score}%
            </span>
          </div>
        </div>
      </header>

      {(matched.length > 0 || missing.length > 0) && (
        <div className="skill-row">
          {matched.map((skill, i) => (
            <span key={`m-${i}-${skill}`} className="skill-chip skill-have">
              {skill}
            </span>
          ))}
          {missing.map((skill, i) => (
            <span key={`x-${i}-${skill}`} className="skill-chip skill-miss">
              {skill}
            </span>
          ))}
        </div>
      )}

      {reason && <p className="job-reason">{reason}</p>}

      <footer className="job-actions">
        <Button
          variant="soft"
          size="sm"
          onClick={(event) => {
            event.stopPropagation();
            onSelect?.();
          }}
        >
          Review
        </Button>
        <Button
          variant="ghost"
          size="sm"
          icon={<Icon name="wand" size={12} />}
          onClick={(event) => {
            event.stopPropagation();
            onTailor?.(job);
          }}
        >
          Tailor
        </Button>
        {job.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
            className="job-view-link"
          >
            <Button variant="ghost" size="sm" icon={<Icon name="arrow-up-right" size={12} />}>
              View
            </Button>
          </a>
        )}
      </footer>
    </article>
  );
}
