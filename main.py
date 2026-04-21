from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def forensic_ai_scanner(temp_path):
    doc = fitz.open(temp_path)
    full_text = "".join([page.get_text() for page in doc.pages[:15]])
    doc.close()

    if not full_text.strip(): return None

    # Android ki Data Class (most_frequent_person, etc.) ke mutabik keys
    prompt = f"""
    You are a Haryana Police Forensic Expert. Analyze this data and return JSON with these EXACT keys:
    {{
      "most_frequent_person": "Top 10 beneficiary names as a single string",
      "top_banks": "Top banks as a single string",
      "top_locations": "ATM IDs as a single string",
      "top_utr": "UTRs as a single string",
      "suspicious": "10-line fraud pattern summary"
    }}
    IMPORTANT: Every value MUST be a plain string with \\n for new lines. NO lists [].
    Data: {full_text[:6000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Cyber Cell Investigator"},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    # Adding owner_info manually to avoid structure mismatch
    res = json.loads(response.choices.message.content)
    res["owner_info"] = "🛡️ HARYANA VIGIL-SCAN: SCAN COMPLETE"
    return res

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_ai_scanner(temp)
        # Android app "data" object ke andar ye dhundta hai
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
