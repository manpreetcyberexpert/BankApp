from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Render Settings mein OPENAI_API_KEY check kar lena
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def forensic_ai_scanner(temp_path):
    doc = fitz.open(temp_path)
    full_text = ""
    for i, page in enumerate(doc):
        if i < 20: full_text += page.get_text()
    doc.close()

    if not full_text.strip(): return None

    # EXACT KEYS MATCHING ANDROID DATA CLASS
    prompt = f"""
    You are a Haryana Police Cyber Cell Expert. 
    Analyze this data and return EXACT JSON with these keys:
    {{
      "most_frequent_person": "List top 10 names found",
      "top_banks": "List top 10 banks and accounts",
      "top_locations": "Identify ATM/POS locations",
      "top_utr": "List major 12-digit UTRs",
      "suspicious": "5-line fraud pattern analysis"
    }}
    IMPORTANT: Values must be a SINGLE STRING with \\n, NOT lists [].
    Data: {full_text[:6000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Expert Forensic Investigator"},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices.message.content)

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_ai_scanner(temp)
        # Android app "data" object ke andar ye keys dhundta hai
        return {"status": "success", "data": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
