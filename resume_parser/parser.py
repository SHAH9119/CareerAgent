import pdfplumber
import json
from groq import Groq
from dotenv import load_dotenv
import os
import re

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text.strip()

def clean_json_output(raw_output: str) -> str:
    """Removes LLM chatter and markdown formatting to get pure JSON"""
    # Find anything between the first '{' and the last '}'
    match = re.search(r'(\{.*\})', raw_output, re.DOTALL)
    if match:
        return match.group(1)
    return raw_output

def parse_resume(pdf_path: str) -> dict:
    raw_text = extract_text_from_pdf(pdf_path)
    
    # We add 'PROJECTS' explicitly to the prompt to force the LLM to find them
    prompt = f"""
    Extract the following resume into a JSON object. 
    IMPORTANT: Look for sections titled 'Projects', 'Academic Projects', or 'Research'. 
    Place them in the "projects" key. 
    
    Resume text:
    {raw_text}

    Return ONLY a JSON object with this exact structure:
    {{
        "name": "", "email": "", "phone": "", "location": "",
        "job_titles": [],
        "skills": [],
        "years_of_experience": 0,
        "education": [{{"degree": "", "institution": "", "year": ""}}],
        "work_experience": [{{"title": "", "company": "", "duration": "", "description": ""}}],
        "projects": [{{"name": "", "technologies": [], "description": ""}}],
        "languages": [],
        "summary": ""
    }}
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": "You are a JSON-only response bot."},
                  {"role": "user", "content": prompt}],
        temperature=0
    )
    
    raw_output = response.choices[0].message.content.strip()
    
    # Clean the output before parsing
    clean_output = clean_json_output(raw_output)
    
    try:
        return json.loads(clean_output)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON. Raw output was: {raw_output}")
        raise e

if __name__ == "__main__":
    import os
    
    # Force the directory to exist
    os.makedirs("data", exist_ok=True)
    
    resume_file = "my_resume.pdf"
    
    if os.path.exists(resume_file):
        print(f"📄 Analyzing {resume_file}...")
        profile = parse_resume(resume_file)
        
        # Define the absolute path to be 100% sure where it's going
        file_path = os.path.abspath("data/profile.json")
        
        # We use 'w+' to truncate the file and write fresh content
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
            f.flush() # Force the buffer to empty into the file
            os.fsync(f.fileno()) # Force the OS to write to disk
            
        print(f"\n✅ Success! File physically updated at:")
        print(f"🔗 {file_path}")
        
        # Verify the projects in the terminal right now
        projs = profile.get('projects', [])
        print(f"🔍 Found {len(projs)} projects:")
        for p in projs:
            print(f"   - {p.get('name')}")
    else:
        print("❌ Error: my_resume.pdf not found.")