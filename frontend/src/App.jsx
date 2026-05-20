import { useState, useEffect } from "react";
import axios from "axios";

const API = "http://localhost:8000/api";

// ── Helpers ───────────────────────────────────────────
function ScoreBadge({ score }) {
  const color =
    score >= 60 ? "#00ff88" :
    score >= 40 ? "#ffcc00" : "#ff4466";
  return (
    <span style={{
      background: color + "22",
      color: color,
      border: `1px solid ${color}55`,
      borderRadius: 6,
      padding: "2px 10px",
      fontWeight: 700,
      fontSize: 13,
    }}>
      {score}%
    </span>
  );
}

function Tag({ text, type }) {
  const colors = {
    have:    { bg: "#00ff8811", color: "#00ff88", border: "#00ff8833" },
    missing: { bg: "#ff446611", color: "#ff7788", border: "#ff446633" },
  };
  const c = colors[type];
  return (
    <span style={{
      background: c.bg,
      color: c.color,
      border: `1px solid ${c.border}`,
      borderRadius: 4,
      padding: "1px 8px",
      fontSize: 11,
      marginRight: 4,
      marginBottom: 4,
      display: "inline-block",
    }}>
      {text}
    </span>
  );
}

function JobCard({ job }) {
  const [expanded, setExpanded] = useState(false);
  const score = job.match_score || 0;
  const borderColor =
    score >= 60 ? "#00ff88" :
    score >= 40 ? "#ffcc00" : "#ff4466";

  return (
    <div style={{
      background: "#0d1117",
      border: `1px solid ${borderColor}33`,
      borderLeft: `3px solid ${borderColor}`,
      borderRadius: 10,
      padding: "18px 20px",
      marginBottom: 12,
      transition: "all 0.2s",
    }}>
      {/* Top row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#e6edf3", marginBottom: 2 }}>
            {job.title}
          </div>
          <div style={{ fontSize: 13, color: "#8b949e" }}>
            {job.company}
          </div>
        </div>
        <ScoreBadge score={score} />
      </div>

      {/* Skills */}
      <div style={{ marginTop: 12 }}>
        {job.matched_skills?.slice(0, 5).map(s => <Tag key={s} text={s} type="have" />)}
        {job.missing_skills?.slice(0, 5).map(s => <Tag key={s} text={s} type="missing" />)}
      </div>

      {/* Verdict */}
      {job.recommendation && (
        <div style={{ fontSize: 12, color: "#8b949e", marginTop: 10, fontStyle: "italic" }}>
          🧠 {job.recommendation}
        </div>
      )}

      {/* Actions */}
      <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
        <a
          href={job.url}
          target="_blank"
          rel="noreferrer"
          style={{
            background: "#161b22",
            color: "#58a6ff",
            border: "1px solid #30363d",
            borderRadius: 6,
            padding: "5px 14px",
            fontSize: 12,
            textDecoration: "none",
          }}
        >
          🔗 View Job
        </a>
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            background: "transparent",
            color: "#8b949e",
            border: "1px solid #30363d",
            borderRadius: 6,
            padding: "5px 14px",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          {expanded ? "▲ Less" : "▼ More"}
        </button>
      </div>

      {/* Expanded description */}
      {expanded && job.description && (
        <div style={{
          marginTop: 12,
          padding: 12,
          background: "#161b22",
          borderRadius: 6,
          fontSize: 12,
          color: "#8b949e",
          maxHeight: 200,
          overflowY: "auto",
          lineHeight: 1.6,
        }}>
          {job.description.slice(0, 800)}...
        </div>
      )}
    </div>
  );
}

function SkillAdvice({ advice }) {
  if (!advice?.top_skills_to_learn?.length) return null;
  return (
    <div style={{
      background: "#0d1117",
      border: "1px solid #30363d",
      borderRadius: 10,
      padding: 20,
      marginBottom: 24,
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#e6edf3", marginBottom: 12 }}>
        📚 Skills to Learn — AI Recommendation
      </div>
      <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 16, fontStyle: "italic" }}>
        {advice.summary}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {advice.top_skills_to_learn.map((item, i) => (
          <div key={i} style={{
            background: "#161b22",
            border: "1px solid #58a6ff33",
            borderRadius: 8,
            padding: "10px 14px",
            minWidth: 160,
            flex: 1,
          }}>
            <div style={{ color: "#58a6ff", fontWeight: 700, fontSize: 13 }}>
              {item.skill}
            </div>
            <div style={{ color: "#8b949e", fontSize: 11, marginTop: 4 }}>
              {item.reason}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────
export default function App() {
  const [data, setData]       = useState(null);
  const [profile, setProfile] = useState(null);
  const [tab, setTab]         = useState("apply");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState(null);

  const loadData = () => {
    return Promise.all([
      axios.get(`${API}/summary`),
      axios.get(`${API}/profile`),
    ]).then(([summary, prof]) => {
      setData(summary.data);
      setProfile(prof.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!running) return;

    const id = setInterval(() => {
      axios.get(`${API}/run-agent/status`).then((res) => {
        setRunStatus(res.data);

        if (["succeeded", "failed"].includes(res.data.stage)) {
          setRunning(false);
          if (res.data.stage === "succeeded") loadData();
        }
      });
    }, 2500);

    return () => clearInterval(id);
  }, [running]);

  const runAgent = () => {
    setRunning(true);
    setRunStatus({ stage: "starting", message: "Starting agent..." });

    axios.post(`${API}/run-agent`, {
      sources: ["existing"],
      skip_parse: true,
      skip_scrape: false,
      target_jobs: 25,
      location: "Pakistan",
      remote: true,
    }).then((res) => {
      setRunStatus(res.data);
    }).catch((err) => {
      setRunning(false);
      setRunStatus({
        stage: "failed",
        message: err.response?.data?.detail || "Could not start agent.",
      });
    });
  };

  if (loading) return (
    <div style={{
      minHeight: "100vh",
      background: "#010409",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: "#58a6ff",
      fontSize: 18,
      fontFamily: "monospace",
    }}>
      🤖 Loading agent data...
    </div>
  );

  if (!data) return (
    <div style={{
      minHeight: "100vh",
      background: "#010409",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: "#ff4466",
      fontSize: 16,
      fontFamily: "monospace",
    }}>
      ⚠️ No data found. Run the pipeline first.
    </div>
  );

  const tabs = [
    { key: "apply", label: `✅ Apply`,  count: data.apply?.length  || 0 },
    { key: "maybe", label: `🤔 Maybe`,  count: data.maybe?.length  || 0 },
    { key: "skip",  label: `❌ Skipped`, count: data.skip?.length   || 0 },
  ];

  const currentJobs =
    tab === "apply" ? data.apply  || [] :
    tab === "maybe" ? data.maybe  || [] :
    data.skip || [];

  return (
    <div style={{
      minHeight: "100vh",
      background: "#010409",
      fontFamily: "'SF Pro Display', -apple-system, sans-serif",
      color: "#e6edf3",
    }}>
      {/* Header */}
      <div style={{
        borderBottom: "1px solid #21262d",
        padding: "16px 32px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "#0d1117",
      }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: -0.5 }}>
            🤖 AI Job Agent
          </div>
          {profile && (
            <div style={{ fontSize: 12, color: "#8b949e", marginTop: 2 }}>
              {profile.name} · {profile.skills?.slice(0, 4).join(", ")}...
            </div>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={runAgent}
            disabled={running}
            style={{
              background: running ? "#21262d" : "#238636",
              color: "#fff",
              border: "1px solid #2ea043",
              borderRadius: 6,
              padding: "7px 14px",
              fontSize: 12,
              fontWeight: 700,
              cursor: running ? "not-allowed" : "pointer",
            }}
          >
            {running ? "Running..." : "Run Agent"}
          </button>
        </div>
        <div style={{
          background: "#00ff8811",
          color: "#00ff88",
          border: "1px solid #00ff8833",
          borderRadius: 20,
          padding: "4px 12px",
          fontSize: 12,
          fontWeight: 600,
        }}>
          ● Live
        </div>
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "28px 24px" }}>

        {runStatus && (
          <div style={{
            background: runStatus.stage === "failed" ? "#ff446611" : "#161b22",
            border: runStatus.stage === "failed" ? "1px solid #ff446655" : "1px solid #30363d",
            borderRadius: 8,
            padding: "10px 14px",
            marginBottom: 16,
            color: runStatus.stage === "failed" ? "#ff7788" : "#8b949e",
            fontSize: 12,
          }}>
            <strong style={{ color: "#e6edf3", marginRight: 8 }}>
              {runStatus.stage}
            </strong>
            {runStatus.message}
          </div>
        )}

        {/* Stats */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          gap: 12,
          marginBottom: 24,
        }}>
          {[
            { label: "Total Jobs",  value: data.total_jobs_analyzed || 0, color: "#58a6ff" },
            { label: "Apply",       value: data.apply_count || 0,          color: "#00ff88" },
            { label: "Maybe",       value: data.maybe_count || 0,          color: "#ffcc00" },
            { label: "Skipped",     value: data.skip_count  || 0,          color: "#ff4466" },
            { label: "Top Match",   value: `${data.top_score || 0}%`,      color: "#a855f7" },
          ].map((stat, i) => (
            <div key={i} style={{
              background: "#0d1117",
              border: "1px solid #21262d",
              borderRadius: 10,
              padding: "14px 16px",
              textAlign: "center",
            }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: stat.color }}>
                {stat.value}
              </div>
              <div style={{ fontSize: 11, color: "#8b949e", marginTop: 2 }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Skill Advice */}
        <SkillAdvice advice={data.skill_advice} />

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                background: tab === t.key ? "#161b22" : "transparent",
                color: tab === t.key ? "#e6edf3" : "#8b949e",
                border: tab === t.key ? "1px solid #30363d" : "1px solid transparent",
                borderRadius: 6,
                padding: "7px 16px",
                fontSize: 13,
                cursor: "pointer",
                fontWeight: tab === t.key ? 600 : 400,
              }}
            >
              {t.label} ({t.count})
            </button>
          ))}
        </div>

        {/* Job Cards */}
        {currentJobs.length === 0 ? (
          <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>
            No jobs in this category.
          </div>
        ) : (
          currentJobs.map((job, i) => <JobCard key={i} job={job} />)
        )}
      </div>
    </div>
  );
}
