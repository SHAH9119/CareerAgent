import { Badge, VerdictBadge } from "./Badge";
import { Button } from "./Button";
import { Icon } from "./icons";
import "./JobCard.css";

const verdictAccent = {
  APPLY: "card-accent-apply",
  MAYBE: "card-accent-maybe",
  SKIP: "card-accent-skip",
  STRETCH: "card-accent-stretch",
};

const scoreColor = (verdict) => {
  if (verdict === "APPLY") return "score-good";
  if (verdict === "MAYBE") return "score-warn";
  if (verdict === "SKIP") return "score-bad";
  return "score-neutral";
};

const quoteTone = {
  APPLY: "quote-good",
  MAYBE: "quote-warn",
  SKIP: "quote-bad",
};

export function JobCard({ job, selected, onSelect, onTailor }) {
  const matched = job.matched_skills || [];
  const missing = job.missing_skills || [];

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
            <span>
              <Icon name="pin" size={11} /> {job.location}
            </span>
            <span>
              <Icon name="money" size={11} /> {job.salary}
            </span>
            <span>
              <Icon name="clock" size={11} /> {job.posted}
            </span>
          </div>
        </div>
        <div className="job-card-aside">
          <VerdictBadge verdict={job.verdict} />
          <div className={`job-score ${scoreColor(job.verdict)}`}>
            {job.final_score}%
          </div>
        </div>
      </header>

      <div className="skill-row">
        {matched.slice(0, 5).map((skill, i) => (
          <span key={`m-${i}-${skill}`} className="skill-chip skill-have">
            {skill}
            <Icon name="check" size={10} />
          </span>
        ))}
        {missing.slice(0, 3).map((skill, i) => (
          <span key={`x-${i}-${skill}`} className="skill-chip skill-miss">
            {skill}
            <Icon name="x" size={10} />
          </span>
        ))}
        {job.gap_source === "fallback" && (
          <Badge tone="prototype" size="sm">Fallback gap</Badge>
        )}
      </div>

      <div className={`job-quote ${quoteTone[job.verdict] || "quote-warn"}`}>
        <Icon
          name={job.verdict === "MAYBE" || job.verdict === "SKIP" ? "warning" : "sparkle"}
          size={14}
        />
        <span>"{job.ai_reason}"</span>
      </div>

      <footer className="job-actions">
        {job.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
          >
            <Button variant="ghost" size="sm" icon={<Icon name="arrow-up-right" size={13} />}>
              View
            </Button>
          </a>
        )}
        <Button
          variant="ghost"
          size="sm"
          icon={<Icon name="wand" size={13} />}
          onClick={(event) => {
            event.stopPropagation();
            onTailor?.(job);
          }}
        >
          Tailor
        </Button>
        <Button
          variant="soft"
          size="sm"
          iconRight={<Icon name="arrow-up-right" size={13} />}
          onClick={(event) => {
            event.stopPropagation();
            onSelect?.();
          }}
        >
          Review
        </Button>
      </footer>
    </article>
  );
}
