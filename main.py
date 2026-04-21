from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Ensure OPENAI_API_KEY is in Render Environment Variables
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def forensic_ai_scanner(temp_path):
    doc = fitz.open(temp_path)
    # 4000+ rows ke liye sirf pehle 15 pages ka text nikalna (Memory safe)
    full_text = ""
    for i, page in enumerate(doc):
        if i < 15: full_text += page.get_text()
    doc.close()

    if not full_text.strip(): return None

    # Android ki Data Class ke hisab se EXACT KEYS
    prompt = f"""
    You are a Haryana Police Forensic Expert. Analyze this data and return JSON with these EXACT keys.
    Values MUST be plain strings with \\n for new lines. No lists [].
    
    {{
      "most_frequent_person": "Top 10 beneficiary names found",
      "top_banks": "Top 10 banks and accounts",
      "top_locations": "Identify ATM/POS footprints",
      "top_utr": "List 12-digit UTR/Ref numbers",
      "suspicious": "5-line fraud pattern analysis"
    }}
    Data: {full_text[:5000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Cyber Cell Investigator"},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    res = json.loads(response.choices.message.content)
    # Manual key adding for owner info
    res["owner_info"] = "🛡️ HARYANA VIGIL-SCAN: SCAN COMPLETE"
    return res

@app.get("/")
def home(): return {"status": "alive"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_ai_scanner(temp)
        if not res: return {"status": "error", "message": "Structure Mismatch"}
        # Android expects data inside "data" object
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
