import json
import os

import pdfplumber
from dotenv import load_dotenv

from llm import llm_json

load_dotenv()


def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    return text.strip()


def parse_resume(pdf_path: str) -> dict:
    raw_text = extract_text_from_pdf(pdf_path)

    prompt = f"""
Extract the following resume into a JSON object.

IMPORTANT:
- Look for sections titled "Projects", "Academic Projects", or "Research" and place them in "projects".
- Infer the candidate's career_stage from the whole resume, especially education dates, graduation status,
  work history, internships, project depth, and years of experience.
- Infer desired_role_level from career_stage and experience. Use values like "internship", "entry-level",
  "junior", "associate", "mid-level", or "senior".
- The "job_titles" field must mean TARGET ROLES this candidate should search/apply for next.
- Do NOT simply copy past work-experience titles into "job_titles".
- Only include internship target roles if the resume clearly indicates the candidate is seeking internships
  or is not yet ready for entry-level roles.
- Infer target roles from the candidate's strongest skills, projects, education, and work history.
- Keep "work_experience[].title" as the exact historical title from the resume.

Resume text:
{raw_text}

Return ONLY a JSON object with this exact structure:
{{
    "name": "", "email": "", "phone": "", "location": "",
    "job_titles": [],
    "career_stage": "",
    "desired_role_level": "",
    "job_search_keywords": [],
    "skills": [],
    "years_of_experience": 0,
    "education": [{{"degree": "", "institution": "", "year": ""}}],
    "work_experience": [{{"title": "", "company": "", "duration": "", "description": ""}}],
    "projects": [{{"name": "", "technologies": [], "description": ""}}],
    "languages": [],
    "summary": ""
}}
"""

    return llm_json(prompt, system="You are a JSON-only resume parser.", temperature=0)


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    resume_file = "my_resume.pdf"

    if os.path.exists(resume_file):
        print(f"Analyzing {resume_file}...")
        profile = parse_resume(resume_file)
        file_path = os.path.abspath("data/profile.json")
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(profile, file, indent=2, ensure_ascii=False)
        print(f"Profile saved to {file_path}")
    else:
        print("Error: my_resume.pdf not found.")
