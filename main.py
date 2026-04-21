from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import fitz
import json
from openai import OpenAI

app = FastAPI()

# API Key from Render ENV
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Allow Android connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# HEALTH CHECK
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}


# -------------------------------
# SAFE EMPTY RESPONSE
# -------------------------------
def empty_response(msg="No Data Found"):
    return {
        "most_frequent_person": "",
        "top_banks": "",
        "top_locations": "",
        "top_utr": "",
        "suspicious": msg,
        "owner_info": "SYSTEM SAFE MODE"
    }


# -------------------------------
# CLEAN TEXT
# -------------------------------
def clean_text(text):
    junk = ["AM", "PM", "N/A", "NULL", "0", "05", "12/"]
    for j in junk:
        text = text.replace(j, "")
    return text


# -------------------------------
# CONVERT LIST → STRING (ANDROID FIX)
# -------------------------------
def convert_to_string(data):
    keys = ["most_frequent_person", "top_banks", "top_locations", "top_utr"]

    for key in keys:
        if key in data and isinstance(data[key], list):
            data[key] = ", ".join([str(x) for x in data[key]])

    return data


# -------------------------------
# MAIN ANALYZE API
# -------------------------------
@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    temp_path = f"temp_{file.filename}"

    try:
        # Save file
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # -------------------------------
        # READ FILE
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
            return {"status": "success", "data": empty_response("Unsupported File")}

        # Clean text
        text = clean_text(text)

        if not text.strip():
            return {"status": "success", "data": empty_response("No readable data")}

        # -------------------------------
        # AI PROMPT
        # -------------------------------
        prompt = f"""
You are a cybercrime financial investigator.

Analyze this data and return STRICT JSON:

{{
  "most_frequent_person": "Top 10 accounts/names",
  "top_banks": "Top 10 banks",
  "top_locations": "Top ATM IDs or locations",
  "top_utr": "Top UTR transactions",
  "suspicious": "Write 5 line fraud analysis",
  "owner_info": "HARYANA VIGIL SCAN COMPLETE"
}}

Rules:
- Ignore AM, PM, 05, 12/
- Only real financial data
- No junk words

DATA:
{text[:4000]}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial fraud analyst"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        ai_output = json.loads(response.choices[0].message.content)

        # 🔥 IMPORTANT FIX (NO ANDROID CRASH)
        ai_output = convert_to_string(ai_output)

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
