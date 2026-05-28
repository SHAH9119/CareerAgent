import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const client = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
});

const asArray = (value) => (Array.isArray(value) ? value : []);

const toScore = (value) => {
  const number = Number(value || 0);
  return Number.isFinite(number) ? Math.round(number) : 0;
};

const cleanSalary = (salary) => {
  const value = String(salary || "").trim();
  if (!value || /^rs\s*0$/i.test(value) || /^\$?\s*0$/.test(value)) {
    return "Compensation not listed";
  }
  return value;
};

const initials = (name = "") =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "CA";

const titleCaseDecision = (decision = "MAYBE") => decision.toUpperCase();

export function adaptProfile(profile = {}) {
  const targetRoles = asArray(profile.job_titles);
  return {
    ...profile,
    name: profile.name || "Candidate",
    initials: initials(profile.name),
    title: targetRoles[0] || profile.desired_role_level || "Target role not set",
    location: profile.location || "Location not set",
    skills: asArray(profile.skills),
    level: profile.desired_role_level || "Not inferred",
  };
}

export function adaptJob(job = {}, index = 0) {
  const fit = job.fit || {};
  const verdict = titleCaseDecision(job.decision || job.verdict || "MAYBE");
  const missing = asArray(job.missing_skills);
  const blockers = asArray(fit.required_blockers);
  const fitNotes = asArray(fit.fit_notes);
  const recommendation = job.recommendation || job.decision_reason || "";

  return {
    ...job,
    id: job.url || `${job.title || "job"}-${job.company || "company"}-${index}`,
    title: job.title || "Untitled role",
    company: job.company || "Unknown company",
    location: job.location || "Location not listed",
    salary: cleanSalary(job.salary),
    posted: job.posted_at || "Posted date unknown",
    applicants: job.applicants || "Applicants unknown",
    source: job.source || "source",
    final_score: toScore(job.final_score ?? job.match_score),
    semantic: toScore(fit.semantic_score ?? job.match_score),
    domain: toScore(fit.domain_fit),
    skills_fit: toScore(fit.skills_fit),
    seniority: toScore(fit.seniority_fit),
    verdict,
    matched_skills: asArray(job.matched_skills),
    missing_skills: missing,
    blockers,
    ai_reason: job.decision_reason || recommendation || "Fit analysis available from the latest run.",
    detail_reason:
      [recommendation, ...fitNotes].filter(Boolean).join(" ") ||
      job.description?.slice(0, 280) ||
      "No detailed analysis returned yet.",
    tailoring_suggestions: asArray(job.tailoring_suggestions),
    skills_to_learn: missing.slice(0, 4),
    next_action:
      verdict === "APPLY"
        ? "Review the job, tailor the resume, then apply."
        : verdict === "MAYBE"
          ? "Check the gaps and decide if this is worth a tailored application."
          : "Skip unless there is a strategic reason to pursue it.",
  };
}

export function adaptSummary(summary = {}) {
  const grouped = {
    apply: asArray(summary.apply).map((job, index) => adaptJob(job, index)),
    maybe: asArray(summary.maybe).map((job, index) => adaptJob(job, index)),
    skip: asArray(summary.skip).map((job, index) => adaptJob(job, index)),
  };
  const jobs = [...grouped.apply, ...grouped.maybe, ...grouped.skip];
  const avgMatch = jobs.length
    ? Math.round(jobs.reduce((total, job) => total + job.final_score, 0) / jobs.length)
    : 0;

  return {
    ...summary,
    grouped,
    jobs,
    stats: {
      scanned: summary.total_jobs_analyzed ?? jobs.length,
      filtered: grouped.apply.length + grouped.maybe.length,
      avgMatch,
      topScore: summary.top_score || Math.max(...jobs.map((job) => job.final_score), 0),
    },
    counts: {
      all: jobs.length,
      apply: grouped.apply.length,
      maybe: grouped.maybe.length,
      skip: grouped.skip.length,
    },
  };
}

export function adaptSources(payload = {}) {
  return asArray(payload.sources).map((source) => ({
    id: source.id,
    label: source.label,
    description: source.description || "",
    needs_api_key: Boolean(source.needs_api_key),
    status: source.production_safe ? (source.needs_api_key ? "key" : "active") : "prototype",
  }));
}

export async function getDashboardData() {
  const [summary, profile, status, sources] = await Promise.all([
    client.get("/summary"),
    client.get("/profile"),
    client.get("/run-agent/status"),
    client.get("/sources"),
  ]);

  return {
    summary: adaptSummary(summary.data || {}),
    profile: adaptProfile(profile.data || {}),
    status: status.data || null,
    sources: adaptSources(sources.data || {}),
  };
}

export async function startAgent(payload) {
  const { data } = await client.post("/run-agent", payload);
  return data;
}

export async function getRunStatus() {
  const { data } = await client.get("/run-agent/status");
  return data;
}

export async function uploadResume(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/upload-resume", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function parseProfile(resumePath, domainConfigPath = "") {
  const { data } = await client.post("/profile/parse", {
    resume_path: resumePath,
    domain_config_path: domainConfigPath,
  });
  return adaptProfile(data || {});
}

export async function createTailorDraft(job) {
  const { data } = await client.post("/tailor/draft", { job });
  return data;
}

export async function getTailorDrafts(status = "") {
  const { data } = await client.get("/tailor/drafts", {
    params: status ? { status } : {},
  });
  return asArray(data);
}

export async function updateTailorDraftStatus(draftId, status, notes = "") {
  const { data } = await client.post("/tailor/status", {
    draft_id: draftId,
    status,
    notes,
  });
  return data;
}

export async function getDomainConfig(path = "") {
  const { data } = await client.get("/domain-config", {
    params: path ? { path } : {},
  });
  return data || {};
}

export async function saveDomainConfig(path, config) {
  const { data } = await client.post("/domain-config", {
    path,
    config,
  });
  return data;
}
