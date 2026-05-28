import { Badge, VerdictBadge } from "./Badge";
import { Button } from "./Button";
import { FitBar } from "./FitBar";
import { Icon } from "./icons";
import { ScoreRing } from "./ScoreRing";
import "./Inspector.css";

const toneFromVerdict = (verdict) =>
  verdict === "APPLY"
    ? "good"
    : verdict === "MAYBE"
      ? "warn"
      : verdict === "SKIP"
        ? "bad"
        : "brand";

export function Inspector({ job, skillAdvice, onClose, onTailor }) {
  if (!job) {
    return (
      <aside className="inspector inspector-empty">
        <div className="inspector-empty-body">
          <Icon name="sparkle" size={24} />
          <h2>Job details</h2>
          <p>Select a role from the queue to see fit analysis and tailoring options.</p>
        </div>
      </aside>
    );
  }

  const tone = toneFromVerdict(job.verdict);
  const blockers = job.blockers || [];
  const missing = job.missing_skills || [];
  const tailoring = job.tailoring_suggestions || [];
  const skillsToLearn = job.skills_to_learn?.length
    ? job.skills_to_learn
    : (skillAdvice?.top_skills_to_learn || []).map((item) => item.skill).slice(0, 4);

  return (
    <aside className="inspector">
      <header className="inspector-header">
        <div className="inspector-header-text">
          <h2 className="inspector-title">{job.title}</h2>
          <div className="inspector-company">{job.company}</div>
        </div>
        <button type="button" className="inspector-close" onClick={onClose} aria-label="Close inspector">
          <Icon name="x" size={16} />
        </button>
      </header>

      <div className="inspector-score">
        <ScoreRing value={job.final_score} size={108} tone={tone} label="Fit Score" />
        <div className="inspector-score-side">
          <VerdictBadge verdict={job.verdict} />
          <p className="inspector-estimate">AI-assisted estimate — not an official ATS score.</p>
          <div className="inspector-meta">
            {job.location && (
              <span>
                <Icon name="pin" size={11} /> {job.location}
              </span>
            )}
            {job.source && (
              <span className="inspector-source">
                <Icon name="sparkle" size={11} /> {job.source}
              </span>
            )}
          </div>
        </div>
      </div>

      <Section title="Why this fits">
        <FitBar label="Resume Context" value={job.semantic} />
        <FitBar label="Role Domain" value={job.domain} />
        <FitBar label="Skill Coverage" value={job.skills_fit} />
        <FitBar label="Experience Level" value={job.seniority} />
      </Section>

      {job.detail_reason && (
        <Section title="Summary">
          <p className="inspector-text">{job.detail_reason}</p>
        </Section>
      )}

      {(blockers.length > 0 || missing.length > 0) && (
        <Section title="Gaps">
          {blockers.slice(0, 3).map((item) => (
            <div key={item} className="inspector-row inspector-row-bad">
              <Icon name="warning" size={12} />
              <span>{item}</span>
            </div>
          ))}
          {missing.slice(0, 4).map((item) => (
            <div key={item} className="inspector-row inspector-row-warn">
              <Icon name="x" size={12} />
              <span>{item}</span>
            </div>
          ))}
        </Section>
      )}

      {tailoring.length > 0 && (
        <Section title="Tailoring tips">
          <ul className="inspector-bullets">
            {tailoring.slice(0, 4).map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </Section>
      )}

      {skillsToLearn.length > 0 && (
        <Section title="Skills to learn">
          <div className="chip-row">
            {skillsToLearn.map((skill, i) => (
              <span key={`${skill}-${i}`} className="learn-chip">
                {skill}
              </span>
            ))}
          </div>
        </Section>
      )}

      {job.next_action && (
        <div className="next-action">
          <Icon name="arrow-up-right" size={13} />
          <span>{job.next_action}</span>
        </div>
      )}

      <footer className="inspector-footer">
        <Button
          variant="primary"
          size="md"
          icon={<Icon name="wand" size={14} />}
          onClick={() => onTailor?.(job)}
        >
          Tailor Resume
        </Button>
        {job.url && (
          <a href={job.url} target="_blank" rel="noreferrer" className="inspector-link">
            <Button variant="outline" size="md" icon={<Icon name="arrow-up-right" size={14} />}>
              Open Job
            </Button>
          </a>
        )}
      </footer>
    </aside>
  );
}

function Section({ title, children }) {
  return (
    <section className="inspector-section">
      <h3 className="inspector-section-title">{title}</h3>
      <div className="inspector-section-body">{children}</div>
    </section>
  );
}
