import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login, signup } from "../api/careerAgent";
import { Button } from "../components/Button";
import { Icon } from "../components/icons";
import "./Auth.css";

export function Auth({ mode: initialMode = "login", onAuthed }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const update = (patch) => setForm((current) => ({ ...current, ...patch }));

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = mode === "signup" ? await signup(form) : await login(form);
      onAuthed?.(user);
      navigate("/dashboard");
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Could not continue.");
    } finally {
      setBusy(false);
    }
  };

  const switchMode = () => {
    const next = mode === "signup" ? "login" : "signup";
    setMode(next);
    setError("");
    navigate(next === "signup" ? "/signup" : "/login", { replace: true });
  };

  return (
    <main className="auth-page">
      <section className="auth-hero">
        <Link to="/" className="auth-brand">
          <div className="brand-mark auth-mark">
            <Icon name="sparkle" size={16} />
          </div>
          <div>
            <div className="brand-name">CareerAgent</div>
            <div className="brand-sub">AI job intelligence</div>
          </div>
        </Link>

        <div className="auth-hero-copy">
          <h1>Your AI career co-pilot</h1>
          <p>
            Parse resumes, collect jobs from public APIs, score fit with semantic matching,
            and generate tailored application drafts — all in one protected workspace.
          </p>
          <ul className="auth-highlights">
            <li><Icon name="check" size={14} /> Multi-source job collection</li>
            <li><Icon name="check" size={14} /> Apply / Maybe / Skip decisions</li>
            <li><Icon name="check" size={14} /> Per-job resume tailoring</li>
            <li><Icon name="check" size={14} /> Bring your own API keys</li>
          </ul>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-head">
          <h2>{mode === "signup" ? "Create your account" : "Welcome back"}</h2>
          <p>{mode === "signup" ? "Free to start. Add your Groq key in Settings after signup." : "Sign in to your workspace."}</p>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === "signup" && (
            <label>
              <span>Name</span>
              <input
                value={form.name}
                onChange={(event) => update({ name: event.target.value.slice(0, 80) })}
                placeholder="Your name"
                autoComplete="name"
              />
            </label>
          )}
          <label>
            <span>Email</span>
            <input
              type="email"
              value={form.email}
              onChange={(event) => update({ email: event.target.value.slice(0, 120) })}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) => update({ password: event.target.value.slice(0, 128) })}
              placeholder="At least 8 characters"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              minLength={8}
              required
            />
          </label>

          {error && <div className="auth-error">{error}</div>}

          <Button variant="primary" size="md" disabled={busy}>
            {busy ? "Please wait..." : mode === "signup" ? "Create account" : "Log in"}
          </Button>
        </form>

        <button type="button" className="auth-switch" onClick={switchMode}>
          {mode === "signup" ? "Already have an account? Log in" : "New here? Create an account"}
        </button>

        <Link to="/" className="auth-back">← Back to home</Link>
      </section>
    </main>
  );
}
