import streamlit as st
import json
import os
import subprocess
import sys

# ── Page Config ──────────────────────────────────────────
st.set_page_config(
    page_title="AI Job Agent",
    page_icon="🤖",
    layout="wide"
)

# ── Helpers ───────────────────────────────────────────────
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ── Load Data ─────────────────────────────────────────────
profile    = load_json("data/profile.json")
decisions  = load_json("data/decisions.json")
scored     = load_json("data/scored_jobs.json")

# ── Header ────────────────────────────────────────────────
st.title("🤖 AI Job Application Agent")
if profile:
    st.markdown(f"**Candidate:** {profile.get('name', 'Unknown')} &nbsp;|&nbsp; "
                f"**Skills:** {', '.join(profile.get('skills', [])[:6])}...")

st.divider()

# ── No Data State ─────────────────────────────────────────
if not decisions:
    st.warning("⚠️ No data found. Run the pipeline first.")
    st.code("python main.py", language="bash")
    st.stop()

# ── Top Stats ─────────────────────────────────────────────
summary = decisions.get("summary", {})
apply_jobs = decisions.get("apply", [])
maybe_jobs = decisions.get("maybe", [])
skip_jobs  = decisions.get("skip",  [])
all_jobs   = apply_jobs + maybe_jobs + skip_jobs

top_score = max((j.get("match_score", 0) for j in all_jobs), default=0)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📋 Total Jobs",    summary.get("total_jobs_analyzed", 0))
col2.metric("✅ Auto Apply",    summary.get("apply_count", 0))
col3.metric("🤔 Maybe",         summary.get("maybe_count", 0))
col4.metric("❌ Skipped",        summary.get("skip_count",  0))
col5.metric("🏆 Top Match",     f"{top_score}%")

st.divider()

# ── Skill Advice Panel ────────────────────────────────────
skill_advice = decisions.get("skill_advice", {})
if skill_advice:
    with st.expander("📚 Skills to Learn (AI Recommendation)", expanded=True):
        st.markdown(f"💡 **{skill_advice.get('summary', '')}**")
        st.markdown("")
        cols = st.columns(len(skill_advice.get("top_skills_to_learn", [])) or 1)
        for i, item in enumerate(skill_advice.get("top_skills_to_learn", [])):
            with cols[i]:
                st.markdown(f"### {item['skill']}")
                st.caption(item['reason'])

st.divider()

# ── Job Tabs ──────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    f"✅ Apply ({len(apply_jobs)})",
    f"🤔 Maybe ({len(maybe_jobs)})",
    f"❌ Skipped ({len(skip_jobs)})"
])

def render_job_card(job, index, bucket):
    """Renders one job card with all details"""
    score = job.get("match_score", 0)

    # Color based on score
    if score >= 60:
        color = "🟢"
    elif score >= 40:
        color = "🟡"
    else:
        color = "🔴"

    with st.container():
        col1, col2 = st.columns([4, 1])

        with col1:
            st.markdown(f"### {color} {job.get('title', 'Unknown')}")
            st.markdown(f"**{job.get('company', 'Unknown')}**")

        with col2:
            st.metric("Match", f"{score}%")

        # Skills row
        c1, c2 = st.columns(2)
        with c1:
            matched = job.get("matched_skills", [])
            if matched:
                st.markdown("✅ **Have:** " + " · ".join(
                    [f"`{s}`" for s in matched[:5]]
                ))
        with c2:
            missing = job.get("missing_skills", [])
            if missing:
                st.markdown("❌ **Missing:** " + " · ".join(
                    [f"`{s}`" for s in missing[:5]]
                ))

        # Verdict
        verdict = job.get("recommendation", "")
        if verdict:
            st.caption(f"🧠 {verdict}")

        # Action buttons
        b1, b2, b3 = st.columns([1, 1, 4])
        with b1:
            st.link_button("🔗 View Job", job.get("url", "#"))
        with b2:
            # Manual override button
            if bucket == "apply":
                if st.button("Move to Maybe", key=f"maybe_{index}"):
                    st.session_state[f"override_{index}"] = "maybe"
                    st.rerun()
            elif bucket == "maybe":
                if st.button("Move to Apply", key=f"apply_{index}"):
                    st.session_state[f"override_{index}"] = "apply"
                    st.rerun()

        st.divider()


with tab1:
    if not apply_jobs:
        st.info("No jobs in Apply list yet.")
    for i, job in enumerate(apply_jobs):
        render_job_card(job, i, "apply")

with tab2:
    if not maybe_jobs:
        st.info("No jobs in Maybe list.")
    for i, job in enumerate(maybe_jobs):
        render_job_card(job, i, "maybe")

with tab3:
    if not skip_jobs:
        st.info("No skipped jobs.")
    # Show skipped in compact table
    import pandas as pd
    skip_data = [{
        "Title":   j.get("title", "")[:50],
        "Company": j.get("company", ""),
        "Score":   f"{j.get('match_score', 0)}%",
    } for j in skip_jobs]
    if skip_data:
        st.dataframe(pd.DataFrame(skip_data), use_container_width=True)

# ── Sidebar: Run Pipeline ─────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    st.markdown("**Pipeline Steps:**")

    st.markdown("**1. Parse Resume**")
    resume_file = st.file_uploader("Upload Resume PDF", type=["pdf"])
    if resume_file and st.button("Parse Resume"):
        with open("uploaded_resume.pdf", "wb") as f:
            f.write(resume_file.read())
        st.success("Resume uploaded. Run parser manually for now.")

    st.divider()

    st.markdown("**2. Search Preferences**")
    remote_only = st.checkbox("Remote Only", value=False)
    location    = st.text_input("Location", value="Islamabad, Pakistan")
    time_filter = st.selectbox("Posted Within", ["Any", "24 hours", "1 week"])

    st.divider()

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

    st.divider()
    st.caption("Built by Syed Haider Ali")
    st.caption("AI Job Application Agent v1.0")