from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import fitz
import json
from openai import OpenAI

app = FastAPI()

# Load API Key from environment
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# CORS (important for Android)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Health Check
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}


# -------------------------------
# File Analyzer API
# -------------------------------
@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    temp_path = f"temp_{file.filename}"

    try:
        # Save file temporarily
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # -------------------------------
        # Read File (ALL formats supported)
        # -------------------------------
        if file.filename.lower().endswith(".pdf"):
            doc = fitz.open(temp_path)
            text = ""
            for page in doc.pages[:5]:
                text += page.get_text()
            doc.close()

        elif file.filename.lower().endswith(".csv"):
            df = pd.read_csv(temp_path)
            text = df.head(150).to_string()

        elif file.filename.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(temp_path)
            text = df.head(150).to_string()

        else:
            return {
                "status": "success",
                "data": empty_response("Unsupported file format")
            }

        if not text.strip():
            return {
                "status": "success",
                "data": empty_response("No readable data")
            }

        # -------------------------------
        # AI PROMPT (STRICT JSON OUTPUT)
        # -------------------------------
        prompt = f"""
You are a professional financial forensic investigator.

Analyze the dataset and return STRICT JSON:

{{
  "most_frequent_person": ["Top 10 names or accounts"],
  "top_banks": ["Top 10 banks"],
  "top_locations": ["Top ATM IDs or locations"],
  "top_utr": ["Top UTR / transaction IDs"],
  "suspicious": "5 line fraud analysis",
  "owner_info": "HARYANA VIGIL SCAN COMPLETE"
}}

IMPORTANT:
- Ignore words like AM, PM, DATE numbers
- Only extract real financial data
- Output must be valid JSON only

DATA:
{text[:4000]}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial fraud analyst."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        ai_output = json.loads(response.choices[0].message.content)

        return {
            "status": "success",
            "data": ai_output
        }

    except Exception as e:
        return {
            "status": "success",
            "data": empty_response(str(e))
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# -------------------------------
# Empty Safe Response (No Crash)
# -------------------------------
def empty_response(msg="No Data"):
    return {
        "most_frequent_person": [],
        "top_banks": [],
        "top_locations": [],
        "top_utr": [],
        "suspicious": msg,
        "owner_info": "SYSTEM SAFE MODE"
    }
