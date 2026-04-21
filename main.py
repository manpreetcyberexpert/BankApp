from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def forensic_ai_scanner(temp_path):
    doc = fitz.open(temp_path)
    full_text = ""
    for i, page in enumerate(doc):
        if i < 15: full_text += page.get_text()
    doc.close()

    if not full_text.strip(): return None

    # App ki Data Class se match karne ke liye exact Keys use ki hain
    prompt = f"""
    You are a Haryana Police Forensic Expert. Analyze this data and return JSON with these EXACT keys:
    {{
      "most_frequent_person": "Top names/entities here as string",
      "top_banks": "Top banks here as string",
      "top_locations": "ATM IDs here as string",
      "top_utr": "UTRs here as string",
      "suspicious": "Forensic summary here as string"
    }}
    Important: Every value must be a plain string with \\n for new lines. No lists [].
    Data: {full_text[:5000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Cyber Cell Investigator"},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices.message.content)

@app.get("/")
def home(): return {"status": "LIVE"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_ai_scanner(temp)
        if not res: return {"status": "error", "message": "Structure mismatch"}
        return {"status": "success", "data": res}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
