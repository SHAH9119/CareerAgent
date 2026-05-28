import { useState } from "react";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/icons";
import { parseProfile, uploadResume } from "../api/careerAgent";
import "./Onboarding.css";

const DOMAIN_PRESETS = [
  { id: "", label: "Auto detect from resume", path: "" },
  { id: "ai_ml", label: "AI / ML / Computer Vision", path: "config/candidates/ai_ml_engineer.json" },
  { id: "swe", label: "Software Engineering", path: "config/candidates/software_engineer.json" },
];

export function Onboarding({ onComplete }) {
  const [stage, setStage] = useState("upload");
  const [fileName, setFileName] = useState("");
  const [resumePath, setResumePath] = useState("");
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [domainPreset, setDomainPreset] = useState("");

  const domainConfigPath = DOMAIN_PRESETS.find((preset) => preset.id === domainPreset)?.path || "";

  const onFileChosen = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setStage("parsing");
    setFileName(file.name);
    try {
      const uploaded = await uploadResume(file);
      setResumePath(uploaded.resume_path);
      const parsed = await parseProfile(uploaded.resume_path, domainConfigPath);
      setProfile(parsed);
      setStage("preview");
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Upload or parsing failed.");
      setStage("upload");
    }
  };

  return (
    <div className="onb-wrap">
      <div className="onb-shell">
        <header className="onb-head">
          <h1>Welcome to CareerAgent</h1>
          <p>Upload your resume. We extract a structured profile and use it to find matching jobs.</p>
        </header>

        {stage !== "preview" ? (
          <div className="onb-card">
            <div className="onb-help">
              <Icon name="sparkle" size={14} />
              <span>Pick the role family you target. "Auto" lets the matcher infer everything from your resume.</span>
            </div>
            <div className="onb-preset-row">
              {DOMAIN_PRESETS.map((preset) => (
                <button
                  key={preset.id || "auto"}
                  type="button"
                  onClick={() => setDomainPreset(preset.id)}
                  className={`onb-preset ${domainPreset === preset.id ? "onb-preset-active" : ""}`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <label className="onb-drop">
              <input type="file" accept=".pdf" onChange={onFileChosen} disabled={stage === "parsing"} />
              {stage === "upload" ? (
                <>
                  <Icon name="doc" size={36} />
                  <strong>Drop your resume here or click to browse</strong>
                  <span className="muted-tiny">PDF only. Stored locally on this machine.</span>
                </>
              ) : (
                <>
                  <Icon name="doc" size={36} />
                  <strong>{fileName}</strong>
                  <div className="onb-progress">
                    <div className="onb-progress-row">
                      <span>Uploading and parsing resume...</span>
                      <span>Live</span>
                    </div>
                    <div className="onb-progress-track">
                      <div className="onb-progress-fill" style={{ width: "72%" }} />
                    </div>
                  </div>
                </>
              )}
            </label>

            {error && <div className="onb-error"><Icon name="warning" size={14} />{error}</div>}

            <div className="onb-trust">
              <span><Icon name="check" size={11} /> FastAPI upload</span>
              <span><Icon name="check" size={11} /> Groq LLM parsing</span>
              <span><Icon name="check" size={11} /> Stored locally</span>
            </div>
          </div>
        ) : (
          <div className="onb-preview">
            <Card title="Parsed Profile" icon={<Icon name="sparkle" size={13} />}>
              <div className="onb-grid">
                <Field label="Full Name">
                  <input readOnly value={profile?.name || ""} />
                </Field>
                <Field label="Target Roles">
                  <input readOnly value={(profile?.job_titles || []).join(", ")} />
                </Field>
                <Field label="Experience Level">
                  <input readOnly value={profile?.level || profile?.desired_role_level || ""} />
                </Field>
                <Field label="Years of Experience">
                  <input readOnly value={profile?.years_of_experience || 0} />
                </Field>
                <Field label="Location">
                  <input readOnly value={profile?.location || "Not detected"} />
                </Field>
                <Field label="Resume File">
                  <input readOnly value={resumePath} />
                </Field>
              </div>

              <div className="onb-block">
                <span className="field-label">Extracted Skills</span>
                <div className="chip-row">
                  {(profile?.skills || []).slice(0, 18).map((skill) => (
                    <span key={skill} className="chip chip-active">{skill}</span>
                  ))}
                </div>
              </div>

              <div className="onb-actions">
                <Button variant="ghost" size="md" onClick={() => setStage("upload")}>
                  Re-upload Resume
                </Button>
                <Button variant="primary" size="md" icon={<Icon name="sparkle" size={13} />} onClick={onComplete}>
                  Open Dashboard
                </Button>
              </div>
            </Card>

            <Card title="What Happens Next" icon={<Icon name="brain" size={13} />}>
              <ul className="onb-bullets">
                <li><Badge tone="info" size="sm">1</Badge> Pick data sources on the dashboard (Remotive / RemoteOK / Adzuna...).</li>
                <li><Badge tone="info" size="sm">2</Badge> Click "Run agent" to scrape, match, and rank jobs.</li>
                <li><Badge tone="info" size="sm">3</Badge> Open the Resumes tab to tailor your resume for any matched job.</li>
                {domainConfigPath && (
                  <li><Badge tone="active" size="sm">Domain</Badge> Using rules from {domainConfigPath}</li>
                )}
              </ul>
            </Card>
          </div>
        )}

        <footer className="onb-footer">
          <span><Icon name="check" size={11} /> Resume stored locally in this prototype</span>
          <span>v1.0</span>
        </footer>
      </div>
    </div>
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
