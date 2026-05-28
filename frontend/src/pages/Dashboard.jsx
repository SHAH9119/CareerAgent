import { useEffect, useMemo, useState } from "react";
import {
  createTailorDraft,
  getDashboardData,
  getRunStatus,
  startAgent,
  uploadResume,
} from "../api/careerAgent";
import { Inspector } from "../components/Inspector";
import { JobQueue } from "../components/JobQueue";
import { SearchParameters } from "../components/SearchParameters";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import "./Dashboard.css";

const DEFAULT_RUN_CONFIG = {
  resume_path: "",
  sources: ["remotive", "remoteok", "arbeitnow", "jsearch"],
  target_jobs: 25,
  location: "",
  mode: "all",
  workplace_types: ["remote", "hybrid", "on-site"],
  remote: false,
  past_24h: false,
  skip_parse: true,
  skip_scrape: false,
  custom_queries: "",
  sector: "",
  workplace_type: "",
  domain_config_path: "",
  adzuna_country: "us",
  use_db: true,
  exp_label: "From resume",
  exp_index: 1,
};

const terminalStages = new Set(["succeeded", "failed"]);

function parseQueries(value = "") {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildRunPayload(config) {
  return {
    resume_path: config.resume_path || "my_resume.pdf",
    sources: config.sources?.length ? config.sources : ["remotive", "remoteok", "arbeitnow"],
    target_jobs: Number(config.target_jobs || 25),
    location: config.location || "",
    remote: config.workplace_types?.length === 1 && config.workplace_types[0] === "remote",
    past_24h: Boolean(config.past_24h),
    adzuna_country: (config.adzuna_country || "us").toLowerCase(),
    skip_parse: Boolean(config.skip_parse),
    skip_scrape: Boolean(config.skip_scrape),
    custom_queries: parseQueries(config.custom_queries),
    sector: config.sector || "",
    workplace_type: config.workplace_type || "",
    workplace_types: config.workplace_types || [],
    domain_config_path: config.domain_config_path || "",
    use_db: Boolean(config.use_db),
  };
}

export function Dashboard({ activeNav, onNav, onProfileClick, onNewRun, onLogout }) {
  const [profile, setProfile] = useState(null);
  const [summary, setSummary] = useState(null);
  const [sources, setSources] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [runConfig, setRunConfig] = useState(DEFAULT_RUN_CONFIG);
  const [runStatus, setRunStatus] = useState(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const loadData = async ({ preserveSelection = true } = {}) => {
    setError("");
    try {
      const data = await getDashboardData();
      setProfile(data.profile);
      setSummary(data.summary);
      setSources(data.sources);
      setRunStatus(data.status);

      setRunConfig((current) => ({
        ...current,
        resume_path: current.resume_path || "",
        location: current.location || data.profile?.location || "",
        domain_config_path: data.profile?.domain_config_path || current.domain_config_path,
        exp_label: data.profile?.level || current.exp_label,
        exp_index:
          data.profile?.level?.toLowerCase().includes("senior")
            ? 2
            : data.profile?.level?.toLowerCase().includes("lead")
              ? 3
              : current.exp_index,
      }));

      const jobs = data.summary.jobs;
      setSelectedJob((current) => {
        if (preserveSelection && current) {
          return jobs.find((job) => job.id === current.id) || jobs[0] || null;
        }
        return jobs[0] || null;
      });
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Could not load backend data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      loadData({ preserveSelection: false });
    }, 0);
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (!running) return undefined;

    const interval = setInterval(async () => {
      try {
        const status = await getRunStatus();
        setRunStatus(status);
        if (terminalStages.has(status.stage)) {
          setRunning(false);
          await loadData({ preserveSelection: false });
        }
      } catch (exc) {
        setRunning(false);
        setError(exc.response?.data?.detail || exc.message || "Could not read run status.");
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [running]);

  const handleRun = async () => {
    setToast("");
    setError("");
    setRunning(true);
    setRunStatus({ stage: "starting", message: "Agent run starting." });

    try {
      const status = await startAgent(buildRunPayload(runConfig));
      setRunStatus(status);
    } catch (exc) {
      setRunning(false);
      setRunStatus({ stage: "failed", message: exc.response?.data?.detail || "Could not start agent." });
    }
  };

  const handleUpload = async (file) => {
    setToast("");
    setError("");
    try {
      const result = await uploadResume(file);
      setRunConfig((current) => ({
        ...current,
        resume_path: result.resume_path,
        skip_parse: false,
      }));
      setToast(`Uploaded ${result.filename}. Resume parsing will run on next agent run.`);
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Upload failed.");
    }
  };

  const handleTailor = async (job) => {
    setToast("");
    setError("");
    try {
      const draft = await createTailorDraft(job);
      setToast(`Tailoring draft #${draft.id} created for ${job.company}. Open the Resumes tab to review.`);
    } catch (exc) {
      setError(exc.response?.data?.detail || exc.message || "Could not create tailoring draft.");
    }
  };

  const visibleJobs = useMemo(() => summary?.jobs || [], [summary]);

  return (
    <div className="dashboard">
      <Sidebar
        candidate={profile}
        activeNav={activeNav}
        onNav={onNav}
        onProfileClick={onProfileClick}
        onNewRun={onNewRun}
        onLogout={onLogout}
      />
      <div className="dashboard-body">
        <TopBar
          candidate={profile}
          search={search}
          onSearch={setSearch}
          onRun={handleRun}
          onRerun={handleRun}
          running={running}
          status={runStatus}
        />
        {(toast || error) && (
          <div className={`dashboard-toast ${error ? "dashboard-toast-error" : ""}`}>
            {error || toast}
          </div>
        )}
        <div className="dashboard-content">
          <SearchParameters
            config={runConfig}
            sources={sources}
            running={running}
            status={runStatus}
            onConfigChange={setRunConfig}
            onUpload={handleUpload}
            onRun={handleRun}
          />
          <JobQueue
            jobs={visibleJobs}
            selectedId={selectedJob?.id}
            onSelect={setSelectedJob}
            stats={summary?.stats}
            counts={summary?.counts}
            loading={loading}
            error={error}
            search={search}
            onTailor={handleTailor}
          />
          <Inspector
            job={selectedJob}
            skillAdvice={summary?.skill_advice}
            onClose={() => setSelectedJob(null)}
            onTailor={handleTailor}
          />
        </div>
      </div>
    </div>
  );
}
