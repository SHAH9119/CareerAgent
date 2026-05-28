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
          <Icon name="sparkle" size={28} />
          <h2>Intelligence Brain</h2>
          <p>Select a job from the queue to see fit analysis and tailoring advice.</p>
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
        <div>
          <div className="inspector-eyebrow">Inspector</div>
          <h2 className="inspector-title">{job.title}</h2>
          <div className="inspector-company">{job.company}</div>
        </div>
        <button type="button" className="inspector-close" onClick={onClose} aria-label="Close inspector">
          <Icon name="x" size={16} />
        </button>
      </header>

      <div className="inspector-score">
        <ScoreRing value={job.final_score} tone={tone} label="Match" />
        <div className="inspector-score-side">
          <VerdictBadge verdict={job.verdict} />
          <div className="inspector-meta">
            <span title="Location"><Icon name="pin" size={11} /> {job.location}</span>
            <span title="Compensation"><Icon name="money" size={11} /> {job.salary}</span>
            <span title="Source" className="inspector-source"><Icon name="sparkle" size={11} /> {job.source}</span>
          </div>
        </div>
      </div>

      <Section title="Fit Breakdown">
        <FitBar label="Semantic Context" value={job.semantic} />
        <FitBar label="Domain Expertise" value={job.domain} />
        <FitBar label="Hard Skills" value={job.skills_fit} />
        <FitBar label="Seniority Match" value={job.seniority} />
      </Section>

      <Section title="AI Analysis" icon="sparkle">
        <p className="inspector-text">{job.detail_reason}</p>
        {job.gap_source === "fallback" && (
          <Badge tone="prototype" size="sm">Deterministic fallback used</Badge>
        )}
      </Section>

      {(blockers.length > 0 || missing.length > 0) && (
        <Section title="Gaps & Blockers">
          {blockers.length > 0 && (
            <div className="inspector-list">
              {blockers.map((item) => (
                <div key={item} className="inspector-row inspector-row-bad">
                  <Icon name="warning" size={13} />
                  <span>{item}</span>
                  <Badge tone="skip" size="sm">Blocker</Badge>
                </div>
              ))}
            </div>
          )}
          {missing.length > 0 && (
            <div className="inspector-list">
              {missing.map((item) => (
                <div key={item} className="inspector-row inspector-row-warn">
                  <Icon name="x" size={13} />
                  <span>{item}</span>
                  <Badge tone="maybe" size="sm">Gap</Badge>
                </div>
              ))}
            </div>
          )}
        </Section>
      )}

      {tailoring.length > 0 && (
        <Section title="Tailoring Suggestions" icon="wand">
          <ul className="inspector-bullets">
            {tailoring.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </Section>
      )}

      {skillsToLearn.length > 0 && (
        <Section title="Skills To Learn">
          <div className="chip-row">
            {skillsToLearn.map((skill, i) => (
              <span key={`${skill}-${i}`} className="learn-chip">{skill}</span>
            ))}
          </div>
        </Section>
      )}

      <Section title="Next Best Action">
        <div className="next-action">
          <Icon name="arrow-up-right" size={14} />
          <span>{job.next_action}</span>
        </div>
      </Section>

      <footer className="inspector-footer">
        <Button variant="primary" size="md" icon={<Icon name="wand" size={14} />} onClick={() => onTailor?.(job)}>
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

function Section({ title, icon, children }) {
  return (
    <section className="inspector-section">
      <div className="inspector-section-title">
        {icon && <Icon name={icon} size={13} />}
        {title}
      </div>
      <div className="inspector-section-body">{children}</div>
    </section>
  );
}
