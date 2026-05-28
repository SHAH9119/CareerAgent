import { useEffect, useMemo, useState } from "react";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/icons";
import { PageShell } from "../components/PageShell";
import {
  createTailorDraft,
  getDashboardData,
  getTailorDrafts,
  updateTailorDraftStatus,
} from "../api/careerAgent";
import "./Tailoring.css";

const statusTone = {
  draft: "info",
  review: "maybe",
  approved: "active",
  rejected: "skip",
};

export function Tailoring({ activeNav, onNav, onProfileClick, onNewRun, onBack, onLogout }) {
  const [drafts, setDrafts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [profile, setProfile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const selectedDraft = drafts.find((draft) => draft.id === selectedId) || drafts[0] || null;
  const candidateJobs = useMemo(
    () => jobs.filter((job) => ["APPLY", "MAYBE"].includes(job.verdict)).slice(0, 8),
    [jobs],
  );

  const load = async () => {
    const [draftRows, dashboard] = await Promise.all([getTailorDrafts(), getDashboardData()]);
    setDrafts(draftRows);
    setProfile(dashboard.profile);
    setJobs(dashboard.summary.jobs || []);
    setSelectedId((current) => current || draftRows[0]?.id || null);
    setLoading(false);
  };

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      load().catch((exc) => {
        setMessage(exc.response?.data?.detail || exc.message || "Could not load tailoring data.");
        setLoading(false);
      });
    }, 0);
    return () => window.clearTimeout(timeout);
  }, []);

  const createDraft = async (job) => {
    setBusy(true);
    setMessage("");
    try {
      const draft = await createTailorDraft(job);
      await load();
      setSelectedId(draft.id);
      setMessage(`Draft created for ${job.company}.`);
    } catch (exc) {
      setMessage(exc.response?.data?.detail || exc.message || "Could not create draft.");
    } finally {
      setBusy(false);
    }
  };

  const changeStatus = async (status) => {
    if (!selectedDraft) return;
    setBusy(true);
    setMessage("");
    try {
      const updated = await updateTailorDraftStatus(selectedDraft.id, status, `Marked ${status} from dashboard.`);
      await load();
      setSelectedId(updated.id);
      setMessage(`Draft #${updated.id} marked ${status}.`);
    } catch (exc) {
      setMessage(exc.response?.data?.detail || exc.message || "Could not update draft.");
    } finally {
      setBusy(false);
    }
  };

  const draftText = selectedDraft?.draft_text || "";

  return (
    <PageShell
      activeNav={activeNav}
      candidate={profile}
      onNav={onNav}
      onProfileClick={onProfileClick}
      onNewRun={onNewRun}
      onLogout={onLogout}
      showTopBar={false}
    >
      <div className="tailor">
        <header className="tailor-header">
          <div>
            <div className="tailor-title-row">
              <h1>Resume Tailoring</h1>
              <Badge tone={statusTone[selectedDraft?.status] || "info"} size="sm">
                <Icon name="sparkle" size={11} />
                {selectedDraft?.status || "no draft"}
              </Badge>
            </div>
            <p className="tailor-subtitle">
              {selectedDraft ? (
                <>Target: <strong>{selectedDraft.company}</strong> - {selectedDraft.job_title}</>
              ) : (
                <>Pick an Apply or Maybe job below, then click <strong>Draft</strong> to generate a tailored resume.</>
              )}
            </p>
          </div>
          <div className="tailor-actions">
            <Button variant="outline" size="md" onClick={onBack}>
              <Icon name="x" size={13} /> Back to Dashboard
            </Button>
            <Button variant="outline" size="md" icon={<Icon name="refresh" size={13} />} onClick={load} disabled={busy}>
              Refresh
            </Button>
            <Button variant="outline" size="md" icon={<Icon name="wand" size={13} />} onClick={() => changeStatus("review")} disabled={!selectedDraft || busy}>
              Review
            </Button>
            <Button variant="primary" size="md" icon={<Icon name="check" size={13} />} onClick={() => changeStatus("approved")} disabled={!selectedDraft || busy}>
              Approve
            </Button>
            <Button variant="outline" size="md" icon={<Icon name="x" size={13} />} onClick={() => changeStatus("rejected")} disabled={!selectedDraft || busy}>
              Reject
            </Button>
          </div>
        </header>

        {message && <div className="tailor-alert"><Icon name="warning" size={16} />{message}</div>}

        <div className="tailor-grid">
          <Card
            title="Candidate Profile"
            icon={<Icon name="doc" size={13} />}
            action={<span className="muted-tiny">{profile?.name || "No profile loaded"}</span>}
          >
            <h4 className="tailor-section">Summary</h4>
            <p className="tailor-text">{profile?.summary || "Run resume parsing to load profile summary."}</p>

            <h4 className="tailor-section">Experience</h4>
            {(profile?.work_experience || []).slice(0, 4).map((exp) => (
              <div key={`${exp.title}-${exp.company}`} className="tailor-exp">
                <div className="tailor-exp-row">
                  <strong>{exp.title}</strong>
                  <span className="muted-tiny">{exp.company} ({exp.duration})</span>
                </div>
                <p className="tailor-text">{exp.description}</p>
              </div>
            ))}

            <h4 className="tailor-section">Skills</h4>
            <div className="chip-row">
              {(profile?.skills || []).slice(0, 12).map((skill) => (
                <span key={skill} className="plain-chip">{skill}</span>
              ))}
            </div>
          </Card>

          <Card
            title="Tailored Draft"
            icon={<Icon name="sparkle" size={13} />}
            action={selectedDraft && <Badge tone={statusTone[selectedDraft.status] || "info"} size="sm">{selectedDraft.status}</Badge>}
          >
            {loading ? (
              <p className="tailor-text">Loading drafts...</p>
            ) : selectedDraft ? (
              <>
                <h4 className="tailor-section tailor-section-brand">{selectedDraft.job_title}</h4>
                <pre className="tailor-text tailor-draft-text">{draftText}</pre>
              </>
            ) : (
              <p className="tailor-text">No tailoring drafts yet. Create one from the jobs below.</p>
            )}
          </Card>
        </div>

        <div className="tailor-secondary-grid">
          <Card title="Existing Drafts" icon={<Icon name="doc" size={13} />}>
            {drafts.length === 0 ? (
              <p className="tailor-text">No drafts saved yet.</p>
            ) : (
              <div className="tailor-list">
                {drafts.map((draft) => (
                  <button
                    key={draft.id}
                    type="button"
                    className={`tailor-row ${draft.id === selectedDraft?.id ? "tailor-row-active" : ""}`}
                    onClick={() => setSelectedId(draft.id)}
                  >
                    <span>#{draft.id} {draft.job_title} - {draft.company}</span>
                    <Badge tone={statusTone[draft.status] || "info"} size="sm">{draft.status}</Badge>
                  </button>
                ))}
              </div>
            )}
          </Card>

          <Card title="Create From Real Jobs" icon={<Icon name="wand" size={13} />}>
            {candidateJobs.length === 0 ? (
              <p className="tailor-text">No Apply/Maybe jobs available yet. Run the agent first.</p>
            ) : (
              <div className="tailor-list">
                {candidateJobs.map((job) => (
                  <div key={job.id} className="tailor-row">
                    <span>{job.title} - {job.company}</span>
                    <Button variant="soft" size="sm" icon={<Icon name="wand" size={12} />} onClick={() => createDraft(job)} disabled={busy}>
                      Draft
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Current Gaps" icon={<Icon name="warning" size={13} />}>
            <div className="chip-row">
              {candidateJobs.flatMap((job) => job.missing_skills || []).slice(0, 10).map((gap) => (
                <span key={gap} className="gap-chip">{gap}</span>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </PageShell>
  );
}
