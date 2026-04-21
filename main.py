from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Ensure OPENAI_API_KEY is set in Render Environment Variables
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def forensic_ai_scanner(temp_path):
    doc = fitz.open(temp_path)
    # Extracting first 15 pages to keep the AI prompt within limits while capturing enough data
    full_text = ""
    for i, page in enumerate(doc):
        if i < 15: full_text += page.get_text()
    doc.close()

    if not full_text.strip(): return None

    # STRICT FORENSIC PROMPT
    prompt = f"""
    You are a Haryana Police Cyber Cell Forensic Expert. 
    Analyze this transaction data and return a JSON object with these EXACT keys.
    Every value must be a SINGLE STRING. Use \\n for new lines.

    {{
      "most_frequent_person": "Top 10 names/entities found with counts",
      "top_banks": "Top 10 banks and involved account numbers",
      "top_locations": "ATM IDs and POS locations identified",
      "top_utr": "List 12-digit UTR/Ref numbers of high-value transfers",
      "suspicious": "Detailed 5-line fraud pattern analysis in Hindi-English mix",
      "owner_info": "🛡️ HARYANA VIGIL-SCAN: AI SCAN COMPLETE"
    }}

    RULES: Ignore junk values like AM, PM, 12/, 05. Extract only financial entities.
    DATA: {full_text[:5000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Expert Criminal Investigator"},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    return json.loads(response.choices.message.content)

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_ai_scanner(temp)
        if not res: return {"status": "error", "message": "File unreadable"}
        return {"status": "success", "data": res}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
