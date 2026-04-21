from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Render Settings में अपनी OpenAI API Key पक्का चेक कर लें
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def forensic_ai_expert(temp_path):
    doc = fitz.open(temp_path)
    # 4000+ rows में से मुख्य डेटा निकालने के लिए पहले 15-20 पेज स्कैन करना
    full_text = ""
    for i, page in enumerate(doc):
        if i < 20: full_text += page.get_text()
    doc.close()

    if not full_text.strip(): return None

    # STRICT FORENSIC SCRIPT FOR CHATGPT
    prompt = f"""
    You are the Lead Financial Investigator for Haryana Police Cyber Cell.
    Analyze the provided raw transaction text and generate a professional forensic report.
    You must return a STRICT JSON object. Every value MUST be a SINGLE STRING.
    Use \\n for new lines. Do NOT use lists [].

    {{
      "most_frequent_person": "Top 10 beneficiary names/accounts found and their frequency.",
      "top_banks": "List top 10 banks and interacted account numbers.",
      "top_locations": "Identify all ATM IDs, POS locations, and merchant footprints.",
      "top_utr": "List major 12-digit UTR/Reference numbers identified.",
      "suspicious": "Provide a deep 10-line fraud pattern analysis in Hindi-English mix.",
      "owner_info": "🛡️ HARYANA VIGIL-SCAN: AI FORENSIC COMPLETE"
    }}

    Rules: 
    - Ignore junk like AM, PM, 12/, 05. 
    - Identify hidden fraud patterns.
    - Output must be valid JSON only.

    DATA:
    {full_text[:6000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a professional Cyber Forensic Expert."},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    return json.loads(response.choices.message.content)

@app.get("/")
def home(): return {"status": "HARYANA VIGIL-SCAN IS LIVE"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        # 100% AI Processing
        res = forensic_ai_expert(temp)
        if not res: return {"status": "error", "message": "File Structure Error"}
        
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
