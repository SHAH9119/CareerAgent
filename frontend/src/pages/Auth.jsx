import { useState } from "react";
import { login, signup } from "../api/careerAgent";
import { Button } from "../components/Button";
import { Icon } from "../components/icons";
import "./Auth.css";

export function Auth({ onAuthed }) {
  const [mode, setMode] = useState("login");
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
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Could not continue.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-brand">
          <div className="brand-mark auth-mark">
            <Icon name="sparkle" size={16} />
          </div>
          <div>
            <div className="brand-name">CareerAgent</div>
            <div className="brand-sub">AI job intelligence</div>
          </div>
        </div>

        <div className="auth-copy">
          <h1>{mode === "signup" ? "Create your workspace" : "Welcome back"}</h1>
          <p>Upload a resume, bring your own API keys, run job matching, and create tailored drafts from one protected dashboard.</p>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === "signup" && (
            <label>
              <span>Name</span>
              <input
                value={form.name}
                onChange={(event) => update({ name: event.target.value.slice(0, 80) })}
                placeholder="Syed Haider"
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

        <button
          type="button"
          className="auth-switch"
          onClick={() => {
            setMode(mode === "signup" ? "login" : "signup");
            setError("");
          }}
        >
          {mode === "signup" ? "Already have an account? Log in" : "New here? Create an account"}
        </button>
      </section>
    </main>
  );
}
