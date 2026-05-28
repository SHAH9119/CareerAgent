import { useEffect, useMemo, useState } from "react";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/icons";
import { PageShell } from "../components/PageShell";
import { getDashboardData, getDomainConfig, saveDomainConfig } from "../api/careerAgent";
import "./Settings.css";

const stringify = (value) => JSON.stringify(value || {}, null, 2);

export function Settings({ activeNav, onNav, onProfileClick, onNewRun }) {
  const [profile, setProfile] = useState(null);
  const [configPath, setConfigPath] = useState("");
  const [configText, setConfigText] = useState("{}");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      const data = await getDashboardData();
      const path = data.profile?.domain_config_path || "config/candidates/active.json";
      const config = await getDomainConfig(path);
      setProfile(data.profile);
      setConfigPath(path);
      setConfigText(stringify(config));
    }
    load().catch((exc) => setMessage(exc.response?.data?.detail || exc.message || "Could not load settings."));
  }, []);

  const presets = [
    { id: "auto", label: "Default (auto-detect)", path: "config/domain_config.default.json" },
    { id: "ai", label: "AI / ML Engineer", path: "config/candidates/ai_ml_engineer.json" },
    { id: "swe", label: "Software Engineer", path: "config/candidates/software_engineer.json" },
  ];

  const loadPreset = async (path) => {
    setConfigPath(path);
    try {
      const config = await getDomainConfig(path);
      setConfigText(stringify(config));
      setMessage(`Loaded preset from ${path}. Click Save to apply.`);
    } catch (exc) {
      setMessage(exc.response?.data?.detail || exc.message || "Could not load preset.");
    }
  };

  const parsedConfig = useMemo(() => {
    try {
      return JSON.parse(configText);
    } catch {
      return null;
    }
  }, [configText]);

  const weights = parsedConfig?.score_weights || {};
  const thresholds = parsedConfig?.decision_thresholds || {};

  const handleSave = async () => {
    if (!parsedConfig) {
      setMessage("Domain config JSON is invalid.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const result = await saveDomainConfig(configPath, parsedConfig);
      setConfigPath(result.path);
      setMessage(`Saved domain config to ${result.path}.`);
    } catch (exc) {
      setMessage(exc.response?.data?.detail || exc.message || "Could not save settings.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      activeNav={activeNav}
      candidate={profile}
      onNav={onNav}
      onProfileClick={onProfileClick}
      onNewRun={onNewRun}
    >
      <div className="settings">
        <header className="settings-header">
          <div>
            <h1>Settings</h1>
            <p>Tune the rules used by the matcher and decision engine. Pick a preset or edit the JSON directly.</p>
          </div>
          <Button variant="primary" size="md" icon={<Icon name="check" size={13} />} onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Settings"}
          </Button>
        </header>

        {message && (
          <div className="settings-alert">
            <Icon name="warning" size={16} />
            <span>{message}</span>
          </div>
        )}

        <div className="settings-grid-2">
          <Card title="Active Candidate" icon={<Icon name="brain" size={13} />} subtitle="Domain rules are layered on top of your resume profile.">
            <Field label="Name">
              <input readOnly value={profile?.name || "No profile loaded"} />
            </Field>
            <Field label="Target Role">
              <input readOnly value={profile?.title || "Run parser first"} />
            </Field>
            <Field label="Domain Config Path">
              <input value={configPath} onChange={(event) => setConfigPath(event.target.value)} />
            </Field>
            <div className="preset-row">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className={`preset-chip ${configPath === preset.path ? "preset-chip-active" : ""}`}
                  onClick={() => loadPreset(preset.path)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </Card>

          <Card title="Current Scoring Rules" icon={<Icon name="sparkle" size={13} />}>
            <div className="endpoint-row">
              <div className="endpoint-body">
                <div className="endpoint-name">Primary domain</div>
                <div className="endpoint-key">{parsedConfig?.primary_domain || "not set"}</div>
              </div>
              <Badge tone={parsedConfig ? "active" : "skip"} size="sm">{parsedConfig ? "VALID JSON" : "INVALID JSON"}</Badge>
            </div>
            <div className="thresholds-grid">
              <Field label="Apply min">
                <input readOnly value={thresholds.apply_min_final ?? ""} />
              </Field>
              <Field label="Maybe min">
                <input readOnly value={thresholds.maybe_min_final ?? ""} />
              </Field>
              <Field label="Skip domain below">
                <input readOnly value={thresholds.skip_max_domain ?? ""} />
              </Field>
            </div>
          </Card>
        </div>

        <Card
          title="Scoring Weights"
          icon={<Icon name="brain" size={13} />}
          subtitle="These weights are loaded from the active domain config."
        >
          <div className="weights-grid">
            {Object.entries(weights).map(([key, value]) => (
              <div key={key} className="weight-row">
                <div className="weight-row-head">
                  <span>{key.replaceAll("_", " ")}</span>
                  <strong>{Math.round(Number(value) * 100)}%</strong>
                </div>
                <input className="slider" type="range" min={0} max={50} value={Math.round(Number(value) * 100)} readOnly />
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="Domain Rules JSON"
          icon={<Icon name="doc" size={13} />}
          subtitle="Edit carefully. These rules directly change domain filtering and final scores."
        >
          <textarea
            className="settings-json"
            value={configText}
            onChange={(event) => setConfigText(event.target.value)}
            spellCheck={false}
          />
        </Card>

        <footer className="settings-footer">
          <span>CareerAgent local prototype.</span>
          <span>Groq + FastAPI + React</span>
        </footer>
      </div>
    </PageShell>
  );
}

function Field({ label, children }) {
  return (
    <label className="field-block">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
