import pdfplumber
import json
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def extract_text_from_pdf(pdf_path: str) -> str:
    """Step 1: Pull raw text out of the PDF"""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text.strip()


def parse_resume(pdf_path: str) -> dict:
    """Step 2: Send raw text to Groq, get back structured profile"""
    
    raw_text = extract_text_from_pdf(pdf_path)
    
    prompt = f"""
You are a resume parser. Extract information from this resume and return ONLY a JSON object.

Resume text:
{raw_text}

Return this exact JSON structure (no extra text, no markdown, just raw JSON):
{{
    "name": "full name",
    "email": "email address",
    "phone": "phone number",
    "location": "city, country",
    "job_titles": ["list of job titles they have held or are targeting"],
    "skills": ["list of all technical and soft skills"],
    "years_of_experience": 0,
    "education": [
        {{
            "degree": "degree name",
            "institution": "university name",
            "year": "graduation year"
        }}
    ],
    "work_experience": [
        {{
            "title": "job title",
            "company": "company name",
            "duration": "how long",
            "description": "what they did"
        }}
    ],
    "languages": ["list of languages they speak"],
    "summary": "2-3 sentence summary of this candidate"
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    raw_output = response.choices[0].message.content.strip()
    
    # Parse JSON
    profile = json.loads(raw_output)
    return profile


def display_profile(profile: dict):
    """Just for testing - prints the profile nicely"""
    print("\n===== PARSED RESUME =====")
    print(f"Name: {profile['name']}")
    print(f"Email: {profile['email']}")
    print(f"Location: {profile['location']}")
    print(f"Years of Experience: {profile['years_of_experience']}")
    print(f"\nSkills ({len(profile['skills'])}):")
    for skill in profile['skills']:
        print(f"  - {skill}")
    print(f"\nJob Titles:")
    for title in profile['job_titles']:
        print(f"  - {title}")
    print(f"\nSummary: {profile['summary']}")
    print("=========================\n")


# Test it
if __name__ == "__main__":
    # Put your resume PDF in the root folder and change the name here
    profile = parse_resume("my_resume.pdf")
    display_profile(profile)
    
    # Save it for other components to use later
    with open("data/profile.json", "w") as f:
        json.dump(profile, f, indent=2)
    
    print("Profile saved to data/profile.json")