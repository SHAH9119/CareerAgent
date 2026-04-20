from groq import Groq
from dotenv import load_dotenv
import json
import os

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def assign_decisions(scored_jobs: list) -> list:
    """Step 1: Auto-assign Apply/Maybe/Skip based on score"""

    print("⚡ Assigning decisions based on match scores...")

    for job in scored_jobs:
        score = job.get("match_score", 0)

        if score >= 40:
            job["decision"] = "APPLY"
        elif score >= 30:
            job["decision"] = "MAYBE"
        else:
            job["decision"] = "SKIP"

    # Count decisions
    apply = sum(1 for j in scored_jobs if j["decision"] == "APPLY")
    maybe = sum(1 for j in scored_jobs if j["decision"] == "MAYBE")
    skip  = sum(1 for j in scored_jobs if j["decision"] == "SKIP")

    print(f"  ✅ APPLY: {apply} jobs")
    print(f"  🤔 MAYBE: {maybe} jobs")
    print(f"  ❌ SKIP:  {skip} jobs")

    return scored_jobs


def get_global_skill_gaps(profile: dict, scored_jobs: list) -> dict:
    """Step 2: Analyze top 10 jobs and find the most common missing skills"""

    print("\n🧠 Analyzing global skill gaps across top jobs...")

    # Only look at top 10 jobs by score
    top_jobs = sorted(scored_jobs, key=lambda x: x["match_score"], reverse=True)[:10]

    # Collect all missing skills from top jobs
    all_missing = []
    for job in top_jobs:
        all_missing.extend(job.get("missing_skills", []))

    # Collect top job descriptions for context
    top_descriptions = []
    for job in top_jobs[:5]:
        top_descriptions.append(
            f"Job: {job['title']} at {job['company']} (Score: {job['match_score']}%)\n"
            f"Missing: {', '.join(job.get('missing_skills', []))}"
        )

    prompt = f"""
You are a career advisor analyzing a job seeker's skill gaps.

Candidate current skills: {', '.join(profile.get('skills', []))}

Top matching jobs analysis:
{chr(10).join(top_descriptions)}

All missing skills across top jobs: {', '.join(all_missing)}

Based on this, identify the TOP 5 skills this candidate should learn to dramatically improve their job matches.
For each skill, explain in ONE sentence why it matters.

Return ONLY a JSON object like this (no markdown, no extra text):
{{
    "top_skills_to_learn": [
        {{
            "skill": "skill name",
            "reason": "one sentence why this matters",
            "appears_in_jobs": 3
        }}
    ],
    "summary": "2 sentence overall career advice for this candidate"
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    except Exception as e:
        print(f"  ⚠️ Global skill gap analysis failed: {e}")
        return {
            "top_skills_to_learn": [],
            "summary": "Could not analyze"
        }


def run_decision_engine(profile: dict, scored_jobs: list) -> dict:
    """Master function — runs everything and returns final results"""

    print("\n" + "="*50)
    print("🤖 DECISION ENGINE STARTING")
    print("="*50)

    # Step 1: Assign decisions
    jobs_with_decisions = assign_decisions(scored_jobs)

    # Step 2: Global skill gap analysis
    skill_advice = get_global_skill_gaps(profile, scored_jobs)

    # Step 3: Separate into buckets
    apply_jobs = [j for j in jobs_with_decisions if j["decision"] == "APPLY"]
    maybe_jobs = [j for j in jobs_with_decisions if j["decision"] == "MAYBE"]
    skip_jobs  = [j for j in jobs_with_decisions if j["decision"] == "SKIP"]

    # Step 4: Remove duplicate jobs (same title + company)
    def deduplicate(jobs):
        seen = set()
        unique = []
        for job in jobs:
            key = f"{job['title']}_{job['company']}"
            if key not in seen:
                seen.add(key)
                unique.append(job)
        return unique

    apply_jobs = deduplicate(apply_jobs)
    maybe_jobs = deduplicate(maybe_jobs)

    # Print skill advice
    print("\n📚 TOP SKILLS TO LEARN:")
    for item in skill_advice.get("top_skills_to_learn", []):
        print(f"  → {item['skill']}: {item['reason']}")

    print(f"\n💡 Career Advice: {skill_advice.get('summary', '')}")

    # Final result
    result = {
        "apply":  apply_jobs,
        "maybe":  maybe_jobs,
        "skip":   skip_jobs,
        "skill_advice": skill_advice,
        "summary": {
            "total_jobs_analyzed": len(scored_jobs),
            "apply_count": len(apply_jobs),
            "maybe_count": len(maybe_jobs),
            "skip_count":  len(skip_jobs)
        }
    }

    return result


if __name__ == "__main__":
    # Load profile
    with open("data/profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)

    # Load scored jobs from matcher
    with open("data/scored_jobs.json", "r", encoding="utf-8") as f:
        scored_jobs = json.load(f)

    print(f"📄 Profile: {profile['name']}")
    print(f"💼 Scored jobs loaded: {len(scored_jobs)}")

    # Run engine
    result = run_decision_engine(profile, scored_jobs)

    # Save results
    os.makedirs("data", exist_ok=True)
    with open("data/decisions.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Print final summary
    print("\n" + "="*50)
    print("📊 FINAL SUMMARY")
    print("="*50)
    print(f"Total analyzed: {result['summary']['total_jobs_analyzed']}")
    print(f"✅ APPLY:  {result['summary']['apply_count']} jobs")
    print(f"🤔 MAYBE:  {result['summary']['maybe_count']} jobs")
    print(f"❌ SKIP:   {result['summary']['skip_count']} jobs")

    print("\n✅ APPLY LIST:")
    for job in result["apply"]:
        print(f"  → {job['title']} @ {job['company']} ({job['match_score']}%)")

    print("\n🤔 MAYBE LIST:")
    for job in result["maybe"]:
        print(f"  → {job['title']} @ {job['company']} ({job['match_score']}%)")

    print("\n✅ Results saved to data/decisions.json")