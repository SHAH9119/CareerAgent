import { Link } from "react-router-dom";
import { Button } from "../components/Button";
import { Icon } from "../components/icons";
import "./Landing.css";

const FEATURES = [
  {
    icon: "doc",
    title: "Resume Intelligence",
    desc: "Upload a PDF and extract skills, experience, and target roles with Groq LLMs.",
  },
  {
    icon: "pipeline",
    title: "Multi-Source Jobs",
    desc: "Collect from Remotive, RemoteOK, Arbeitnow, Adzuna, and JSearch in one run.",
  },
  {
    icon: "brain",
    title: "Semantic Matching",
    desc: "Sentence-transformer embeddings plus domain rules rank every job by fit.",
  },
  {
    icon: "sparkle",
    title: "Tailored Drafts",
    desc: "Generate per-job resume drafts with a review workflow before you apply.",
  },
];

const STEPS = [
  { num: "01", title: "Create account", desc: "Sign up and add your Groq API key in Settings." },
  { num: "02", title: "Upload resume", desc: "Parse your profile and pick a domain preset." },
  { num: "03", title: "Run the agent", desc: "Scrape, match, and get Apply / Maybe / Skip verdicts." },
];

export function Landing() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="landing-brand">
          <span className="landing-logo" aria-hidden>
            <Icon name="sparkle" size={16} />
          </span>
          <span>CareerAgent</span>
        </div>
        <nav className="landing-nav-links">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <Link to="/login" className="landing-link-muted">Log in</Link>
          <Link to="/signup">
            <Button variant="primary" size="sm">Get started free</Button>
          </Link>
        </nav>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-copy">
          <span className="landing-badge">AI-powered job search</span>
          <h1>
            Find roles that fit.
            <br />
            <span className="landing-gradient">Apply with confidence.</span>
          </h1>
          <p>
            CareerAgent parses your resume, collects jobs from public APIs, scores fit with
            semantic matching, and drafts tailored applications — all from one dashboard.
          </p>
          <div className="landing-hero-actions">
            <Link to="/signup">
              <Button variant="primary" size="lg" icon={<Icon name="sparkle" size={15} />}>
                Start for free
              </Button>
            </Link>
            <Link to="/login">
              <Button variant="ghost" size="lg">Sign in</Button>
            </Link>
          </div>
          <div className="landing-trust">
            <span><Icon name="check" size={12} /> Bring your own API keys</span>
            <span><Icon name="check" size={12} /> No LinkedIn scraping</span>
            <span><Icon name="check" size={12} /> Per-user data isolation</span>
          </div>
        </div>

        <div className="landing-hero-visual" aria-hidden>
          <div className="landing-mock">
            <div className="mock-bar">
              <span className="mock-dot" />
              <span className="mock-dot" />
              <span className="mock-dot" />
            </div>
            <div className="mock-body">
              <div className="mock-sidebar">
                <div className="mock-line mock-line-short" />
                <div className="mock-line" />
                <div className="mock-line" />
                <div className="mock-line mock-line-active" />
              </div>
              <div className="mock-main">
                <div className="mock-card mock-card-apply">
                  <span className="mock-badge mock-badge-good">Apply</span>
                  <div className="mock-line mock-line-title" />
                  <div className="mock-line mock-line-sub" />
                  <div className="mock-score">92</div>
                </div>
                <div className="mock-card">
                  <span className="mock-badge mock-badge-warn">Maybe</span>
                  <div className="mock-line mock-line-title" />
                  <div className="mock-line mock-line-sub" />
                  <div className="mock-score mock-score-muted">74</div>
                </div>
                <div className="mock-card">
                  <span className="mock-badge">Skip</span>
                  <div className="mock-line mock-line-title" />
                  <div className="mock-line mock-line-sub" />
                  <div className="mock-score mock-score-muted">41</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="landing-section">
        <h2>Everything you need to job hunt smarter</h2>
        <p className="landing-section-sub">Built for engineers who want signal, not noise.</p>
        <div className="landing-features">
          {FEATURES.map((feature) => (
            <article key={feature.title} className="landing-feature">
              <div className="landing-feature-icon">
                <Icon name={feature.icon} size={18} />
              </div>
              <h3>{feature.title}</h3>
              <p>{feature.desc}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="how" className="landing-section landing-section-alt">
        <h2>How it works</h2>
        <div className="landing-steps">
          {STEPS.map((step) => (
            <article key={step.num} className="landing-step">
              <span className="landing-step-num">{step.num}</span>
              <h3>{step.title}</h3>
              <p>{step.desc}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-cta">
        <h2>Ready to show employers what you built?</h2>
        <p>Create a free account and run your first agent in minutes.</p>
        <Link to="/signup">
          <Button variant="primary" size="lg" icon={<Icon name="plus" size={15} />}>
            Create free account
          </Button>
        </Link>
      </section>

      <footer className="landing-footer">
        <span>CareerAgent — AI job intelligence by Syed Haider Ali</span>
        <span>FastAPI · React · Groq · Sentence Transformers</span>
      </footer>
    </div>
  );
}
