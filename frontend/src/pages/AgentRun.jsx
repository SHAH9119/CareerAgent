import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/icons";
import { PageShell } from "../components/PageShell";
import { getDashboardData, getRunStatus, startAgent } from "../api/careerAgent";
import "./AgentRun.css";

const STAGES = [
  { id: "starting", label: "Run queued" },
  { id: "profile", label: "Resume profile" },
  { id: "queries", label: "Search plan" },
  { id: "jobs", label: "Job collection" },
  { id: "matching", label: "Matching" },
  { id: "decision", label: "Decision engine" },
  { id: "succeeded", label: "Completed" },
];

const stageIndex = (stage = "") => {
  if (stage === "failed") return STAGES.findIndex((item) => item.id === "decision");
  const index = STAGES.findIndex((item) => item.id === stage);
  return index >= 0 ? index : 0;
};

const tagForStage = (stage) => {
  if (stage === "jobs") return "SCRAPE";
  if (stage === "matching") return "MATCH";
  if (stage === "decision") return "DECIDE";
  if (stage === "queries") return "PLAN";
  if (stage === "failed") return "ERROR";
  if (stage === "succeeded") return "DONE";
  return "INFO";
};

const tagColor = {
  INFO: "log-info",
  SCRAPE: "log-scrape",
  MATCH: "log-match",
  DECIDE: "log-match",
  PLAN: "log-info",
  DONE: "log-info",
  WARN: "log-warn",
  ERROR: "log-error",
};

export function AgentRun({ activeNav, onNav, onProfileClick, onNewRun, onBack, onLogout }) {
  const [status, setStatus] = useState({ stage: "idle", message: "Agent is idle." });
  const [summary, setSummary] = useState(null);
  const [profile, setProfile] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);
  const lastMsg = useRef("");
  const termRef = useRef(null);
  const currentIndex = stageIndex(status?.stage);

  const addLog = useCallback((tag, text) => {
    if (text === lastMsg.current) return;
    lastMsg.current = text;
    setLogs((prev) => [...prev, { tag, text, time: new Date().toLocaleTimeString() }]);
  }, []);

  const load = useCallback(async () => {
    try {
      const [runStatus, data] = await Promise.all([getRunStatus(), getDashboardData()]);
      const st = runStatus || { stage: "idle", message: "Agent is idle." };
      setStatus(st);
      setSummary(data.summary);
      setProfile(data.profile);

      if (st.message && st.stage !== "idle") {
        addLog(tagForStage(st.stage), st.message);
      }
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Could not load run state.");
    }
  }, [addLog]);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    const id = setInterval(load, 2000);
    return () => { clearTimeout(timer); clearInterval(id); };
  }, [load]);

  useEffect(() => {
    if (termRef.current) {
      termRef.current.scrollTop = termRef.current.scrollHeight;
    }
  }, [logs]);

  const handleStart = async () => {
    setStarting(true);
    setError("");
    setLogs([]);
    lastMsg.current = "";
    try {
      const next = await startAgent({
        resume_path: "my_resume.pdf",
        sources: ["existing"],
        target_jobs: 25,
        location: profile?.location || "",
        skip_parse: true,
        skip_scrape: true,
        custom_queries: [],
        domain_config_path: profile?.domain_config_path || "",
        use_db: true,
      });
      setStatus(next);
      addLog("INFO", "Agent run started.");
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Could not start run.");
    } finally {
      setStarting(false);
    }
  };

  return (
    <PageShell
      activeNav={activeNav}
      candidate={profile}
      onNav={onNav}
      onProfileClick={onProfileClick}
      onNewRun={onNewRun}
      onLogout={onLogout}
    >
      <div className="run">
        <header className="run-header">
          <div className="run-header-left">
            <h1>Agent Run</h1>
            <Badge tone={status?.stage === "failed" ? "skip" : "info"} size="sm">
              <Icon name="pin" size={11} />
              {status?.stage || "idle"}
            </Badge>
          </div>
          <div className="run-header-right">
            <Button variant="primary" size="md" icon={<Icon name="play" size={13} />} onClick={handleStart} disabled={starting} title="Re-score the last collected jobs using your saved profile.">
              {starting ? "Starting..." : "Re-score Saved Jobs"}
            </Button>
            <Button variant="outline" size="md" onClick={onBack}>
              View Results
            </Button>
          </div>
        </header>

        {error && <div className="run-alert"><Icon name="warning" size={16} />{error}</div>}

        <div className="run-stats-row">
          <Card padded>
            <div className="run-stat">
              <span className="run-stat-label">Target Role</span>
              <span className="run-stat-value">{profile?.title || "Profile not loaded"}</span>
            </div>
          </Card>
          <Card padded>
            <div className="run-stat">
              <span className="run-stat-label">Sources</span>
              <span className="run-stat-value">{(status?.sources || ["saved data"]).join(", ")}</span>
            </div>
          </Card>
          <Card padded>
            <div className="run-stat">
              <span className="run-stat-label">Jobs Analyzed</span>
              <span className="run-stat-value">{summary?.stats?.scanned || 0}</span>
            </div>
          </Card>
          <Card padded>
            <div className="run-stat">
              <span className="run-stat-label">Apply / Maybe / Skip</span>
              <span className="run-stat-value">
                {summary?.counts?.apply || 0} / {summary?.counts?.maybe || 0} / {summary?.counts?.skip || 0}
              </span>
            </div>
          </Card>
        </div>

        <div className="run-grid">
          <Card title="Pipeline Execution">
            <ol className="stepper">
              {STAGES.map((step, idx) => {
                const done = status?.stage === "succeeded" || idx < currentIndex;
                const active = idx === currentIndex && !["succeeded", "failed", "idle"].includes(status?.stage);
                const failed = status?.stage === "failed" && idx === currentIndex;
                return (
                  <li key={step.id} className={`step ${done ? "step-done" : active ? "step-active" : failed ? "step-failed" : "step-pending"}`}>
                    <div className="step-marker">
                      {done ? <Icon name="check" size={12} /> : active ? <span className="step-pulse" /> : failed ? <Icon name="warning" size={12} /> : <span className="step-empty" />}
                    </div>
                    <div className="step-body">
                      <div className="step-label">{step.label}</div>
                      <div className="step-detail">{active || failed ? status?.message : done ? "Completed" : "Waiting"}</div>
                    </div>
                    {idx !== STAGES.length - 1 && <span className="step-connector" />}
                  </li>
                );
              })}
            </ol>
          </Card>

          <Card padded={false} className="terminal-card">
            <div className="terminal-bar">
              <span className="terminal-dot" style={{ background: "#ef4444" }} />
              <span className="terminal-dot" style={{ background: "#f59e0b" }} />
              <span className="terminal-dot" style={{ background: "#22c55e" }} />
              <span className="terminal-title">Agent Progress Log</span>
              {status?.stage && !["idle", "succeeded", "failed"].includes(status.stage) && (
                <span className="terminal-live"><span className="terminal-live-dot" /> LIVE</span>
              )}
            </div>
            <div className="terminal-body" ref={termRef}>
              {logs.length === 0 ? (
                <div className="terminal-line terminal-empty">
                  Run the agent from the Dashboard to see progress here.
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="terminal-line">
                    <span className="terminal-time">{log.time}</span>
                    <span className={`terminal-tag ${tagColor[log.tag] || "log-info"}`}>[{log.tag}]</span>
                    <span>{log.text}</span>
                  </div>
                ))
              )}
              {status?.stage && !["idle", "succeeded", "failed"].includes(status.stage) && (
                <div className="terminal-line"><span className="terminal-caret">_</span></div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </PageShell>
  );
}
