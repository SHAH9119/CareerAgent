from sentence_transformers import SentenceTransformer, util
from groq import Groq
from dotenv import load_dotenv
import json
import os

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Load model once — this downloads on first run (~90MB)
print("Loading semantic model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model ready.")


def build_resume_text(profile: dict) -> str:
    """Convert profile dict into one rich text blob for embedding"""
    parts = []

    parts.append(f"Name: {profile.get('name', '')}")
    parts.append(f"Years of experience: {profile.get('years_of_experience', 0)}")

    titles = profile.get("job_titles", [])
    if titles:
        parts.append(f"Target roles: {', '.join(titles)}")

    skills = profile.get("skills", [])
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")

    for exp in profile.get("work_experience", []):
        parts.append(f"Work: {exp['title']} at {exp['company']}. {exp['description']}")

    for proj in profile.get("projects", []):
        techs = ", ".join(proj.get("technologies", []))
        parts.append(f"Project: {proj['name']} using {techs}. {proj['description']}")

    edu = profile.get("education", [])
    if edu:
        e = edu[0]
        parts.append(f"Education: {e['degree']} from {e['institution']}")

    return " | ".join(parts)


def get_skill_gap(profile: dict, job: dict) -> dict:
    """Ask Groq to analyze skill gap between profile and job"""

    resume_skills = profile.get("skills", [])
    job_desc = job.get("description", "")[:3000]  # limit tokens

    prompt = f"""
You are a recruiter analyzing a candidate's fit for a job.

Candidate skills: {', '.join(resume_skills)}

Job description (excerpt):
{job_desc}

Return ONLY a JSON object like this (no markdown, no extra text):
{{
    "required_skills": ["skills the job clearly requires"],
    "matched_skills": ["skills candidate HAS that job needs"],
    "missing_skills": ["skills job needs that candidate is MISSING"],
    "recommendation": "one sentence on fit"
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        raw = response.choices[0].message.content.strip()
        # Clean markdown if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  ⚠️ Skill gap analysis failed: {e}")
        return {
            "required_skills": [],
            "matched_skills": [],
            "missing_skills": [],
            "recommendation": "Could not analyze"
        }


def match_jobs(profile: dict, jobs: list) -> list:
    """Core matching engine — scores every job against the resume"""

    print("\n🧠 Building resume embedding...")
    resume_text = build_resume_text(profile)
    resume_embedding = model.encode(resume_text, convert_to_tensor=True)

    print(f"🔍 Scoring {len(jobs)} jobs...\n")
    scored_jobs = []

    for i, job in enumerate(jobs):
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        description = job.get("description", "")

        if not description:
            print(f"  [{i+1}] ⚠️ Skipping '{title}' — no description")
            continue

        # Combine title + description for richer job embedding
        job_text = f"{title} at {company}. {description}"
        job_embedding = model.encode(job_text, convert_to_tensor=True)

        # Cosine similarity — gives a score between 0 and 1
        similarity = util.cos_sim(resume_embedding, job_embedding).item()
        match_score = round(similarity * 100, 1)  # convert to percentage

        print(f"  [{i+1}/{len(jobs)}] {title} @ {company}")
        print(f"    📊 Match Score: {match_score}%")

        # Get skill gap analysis
        gap = get_skill_gap(profile, job)
        print(f"    ✅ Matched: {', '.join(gap['matched_skills'][:3])}")
        print(f"    ❌ Missing: {', '.join(gap['missing_skills'][:3])}")

        scored_jobs.append({
            **job,
            "match_score": match_score,
            "matched_skills": gap["matched_skills"],
            "missing_skills": gap["missing_skills"],
            "required_skills": gap["required_skills"],
            "recommendation": gap["recommendation"]
        })

    # Sort by score highest first
    scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
    return scored_jobs


if __name__ == "__main__":
    # Load profile
    with open("data/profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)

    # Load jobs
    with open("data/jobs.json", "r", encoding="utf-8") as f:
        jobs = json.load(f)

    print(f"📄 Profile: {profile['name']}")
    print(f"💼 Jobs to score: {len(jobs)}")

    scored = match_jobs(profile, jobs)

    # Save results
    os.makedirs("data", exist_ok=True)
    with open("data/scored_jobs.json", "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2)

    # Print top 10
    print("\n\n===== TOP 10 MATCHES =====")
    for i, job in enumerate(scored[:10]):
        print(f"\n#{i+1} {job['title']} @ {job['company']}")
        print(f"   Score: {job['match_score']}%")
        print(f"   Missing: {', '.join(job['missing_skills'][:3]) or 'None'}")
        print(f"   Verdict: {job['recommendation']}")

    print(f"\n✅ Scored jobs saved to data/scored_jobs.json")