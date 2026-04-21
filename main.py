from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Render Settings में OPENAI_API_KEY सेट करें
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def deep_ai_scanner(temp_path):
    doc = fitz.open(temp_path)
    # 4000+ rows के लिए हम पहले 15-20 पेजों का सघन डेटा (Dense Data) उठाएंगे
    full_text = ""
    for i, page in enumerate(doc):
        if i < 20: full_text += page.get_text()
    doc.close()

    if not full_text.strip(): return None

    # AI PROMPT: इसे हमने 'Forensic Grade' बनाया है
    prompt = f"""
    You are a Senior Financial Forensic Investigator for Haryana Police.
    Analyze the following transaction ledger and provide a deep investigation report.
    Return STRICT JSON with these EXACT keys. All values must be PLAIN STRINGS (Use \n for new lines).

    {{
      "most_frequent_person": "Identify top 10 beneficiary names and their transaction counts.",
      "top_banks": "List top 10 banks and account numbers involved.",
      "top_locations": "Extract all ATM IDs, POS locations and system footprints.",
      "top_utr": "List 12-digit UTR/Reference numbers of major transfers.",
      "suspicious": "Provide a detailed 10-line forensic summary in Hindi-English mix identifying fraud patterns.",
      "owner_info": "🛡️ HARYANA VIGIL-SCAN: AI FORENSIC ANALYSIS COMPLETE"
    }}

    RULES: 
    - Ignore junk text like AM, PM, 12/, 05. 
    - Only include REAL financial entities.
    - Format lists clearly within the string.

    DATA:
    {full_text[:6000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a professional Cyber Cell Expert."},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    return json.loads(response.choices[0].message.content)

@app.get("/")
def home(): return {"status": "alive"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = deep_ai_scanner(temp)
        if not res: return {"status": "error", "message": "File not readable"}
        return {"status": "success", "data": res}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
