"""Resume tailoring with human approval workflow (draft -> review -> approved)."""

import json
import os

from dotenv import load_dotenv

from llm import llm_text
from scraper.utils import safe_join
from storage.db import save_tailor_draft

load_dotenv()


def create_tailor_draft(profile: dict, job: dict, user_id: int | None = None) -> dict:
    """Generate a tailored resume draft for one job. Status starts as 'draft'."""
    prompt = f"""
You are an expert resume writer. Tailor this candidate's resume for ONE job.
Keep facts truthful. Do not invent employers, degrees, or tools.

Candidate profile:
{json.dumps(profile, ensure_ascii=False)[:6000]}

Target job:
Title: {job.get('title')}
Company: {job.get('company')}
Description excerpt:
{(job.get('description') or '')[:3500]}

Matched skills: {safe_join((job.get('matched_skills') or [])[:12])}
Gaps to address carefully: {safe_join(((job.get('fit') or {}).get('nice_to_have_gaps') or [])[:8])}

Return plain text resume sections:
- Professional Summary (3-4 lines)
- Key Skills (bullet list)
- Selected Experience bullets (rewrite 4-6 bullets from relevant roles)
- Projects (2 bullets if relevant)
- Closing note: 2 lines on why this candidate fits the role
"""

    draft_text = llm_text(prompt, temperature=0.3)

    return save_tailor_draft(
        job_url=job.get("url", ""),
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        draft_text=draft_text,
        status="draft",
        notes="AI-generated draft awaiting human review.",
        user_id=user_id,
    )


def update_draft_status(draft_id: int, status: str, notes: str = "", user_id: int | None = None) -> dict:
    allowed = {"draft", "review", "approved", "rejected"}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")

    from storage.db import list_tailor_drafts

    drafts = list_tailor_drafts(user_id=user_id)
    current = next((item for item in drafts if item["id"] == draft_id), None)
    if not current:
        raise ValueError("Draft not found")

    return save_tailor_draft(
        job_url=current["job_url"],
        job_title=current["job_title"],
        company=current["company"],
        draft_text=current["draft_text"],
        status=status,
        notes=notes or current.get("notes", ""),
        draft_id=draft_id,
        user_id=user_id,
    )
