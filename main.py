from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import fitz
import json

from openai import OpenAI

app = FastAPI()

# Load API key from environment
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Enable CORS
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
# Clean unwanted junk text
# -------------------------------
def clean_text(text):
    junk = ["AM", "PM", "N/A", "NULL", "0", "05", "12/"]
    for j in junk:
        text = text.replace(j, "")
    return text


# -------------------------------
# Empty fallback response
# -------------------------------
def empty_response(msg="No Data Found"):
    return {
        "most_frequent_person": [],
        "top_banks": [],
        "top_locations": [],
        "top_utr": [],
        "suspicious": msg,
        "owner_info": "SYSTEM SAFE MODE"
    }


# -------------------------------
# MAIN API
# -------------------------------
@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"

    try:
        # Save uploaded file
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # -------------------------------
        # READ FILE (PDF / EXCEL / CSV)
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
            return {"status": "success", "data": empty_response("Unsupported File Format")}

        # Clean text
        text = clean_text(text)

        if not text.strip():
            return {"status": "success", "data": empty_response("No readable data")}

        # -------------------------------
        # AI PROMPT (STRICT JSON)
        # -------------------------------
        prompt = f"""
You are a professional financial forensic investigator.

Analyze the transaction dataset and return STRICT JSON:

{{
  "most_frequent_person": ["Top 10 names or accounts"],
  "top_banks": ["Top 10 banks"],
  "top_locations": ["Top ATM IDs or locations"],
  "top_utr": ["Top UTR / transaction IDs"],
  "suspicious": "5 line fraud analysis summary",
  "owner_info": "HARYANA VIGIL SCAN COMPLETE"
}}

RULES:
- Ignore junk like AM, PM, 05, 12/
- Extract only real financial entities
- Return only valid JSON

DATA:
{text[:4000]}
"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a cyber crime financial analyst."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
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
