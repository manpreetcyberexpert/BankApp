from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import fitz
import json
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home(): return {"status": "alive"}

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        # 1. READ FILE
        if file.filename.lower().endswith(".pdf"):
            doc = fitz.open(temp_path)
            # 4000 rows handle karne ke liye text sampling
            text = "".join([page.get_text() for page in doc.pages[:10]])
            doc.close()
        elif file.filename.lower().endswith((".csv", ".xls", ".xlsx")):
            df = pd.read_csv(temp_path) if file.filename.endswith(".csv") else pd.read_excel(temp_path)
            text = df.head(300).to_string()
        else:
            return {"status": "error", "message": "Format Not Supported"}

        # 2. AI PROMPT (STRICT STRING FORMAT FOR ANDROID)
        prompt = f"""
        Analyze this bank data for Haryana Police. Return STRICT JSON.
        Every value must be a SINGLE STRING, not a list. Use \\n for new lines.

        Structure:
        {{
          "most_frequent_person": "Top 10 beneficiary names with counts",
          "top_banks": "Top 10 banks and account numbers",
          "top_locations": "ATM IDs and locations found",
          "top_utr": "List 12-digit UTR numbers",
          "suspicious": "5-line fraud pattern analysis in Hindi/English mix",
          "owner_info": "🛡️ HARYANA VIGIL-SCAN: AI SCAN COMPLETE"
        }}
        Rules: Ignore AM, PM, 12/, 05. Extract only real financial data.
        Data: {text[:5000]}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini", # Corrected Model Name
            messages=[
                {"role": "system", "content": "You are a professional forensic investigator."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        ai_data = json.loads(response.choices[0].message.content)

        return {
            "status": "success",
            "data": ai_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)
