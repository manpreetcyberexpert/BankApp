from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import fitz
import re
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
def home():
    return {"status": "alive"}


# -------------------------------
# CLEAN FUNCTION
# -------------------------------
def clean_series(series):
    return (
        series.astype(str)
        .str.upper()
        .str.strip()
        .replace(["N/A", "NONE", "NULL", "0", "", "nan"], pd.NA)
        .dropna()
        .loc[lambda x: x.str.len() > 3]
    )


# -------------------------------
# PANDAS ANALYSIS (EXACT DATA)
# -------------------------------
def structured_analysis(df):

    df.columns = [str(c).upper().strip() for c in df.columns]

    result = {}

    # ACCOUNT
    if "ACCOUNT" in df.columns:
        acc = clean_series(df["ACCOUNT"])
        result["most_frequent_person"] = acc.value_counts().head(10).index.tolist()

    # BANK
    if "BANK" in df.columns:
        bank = clean_series(df["BANK"])
        result["top_banks"] = bank.value_counts().head(10).index.tolist()

    # UTR
    if "UTR" in df.columns:
        utr = clean_series(df["UTR"])
        result["top_utr"] = utr.value_counts().head(10).index.tolist()

    # DESCRIPTION → UPI
    if "DESCRIPTION" in df.columns:
        upi = df["DESCRIPTION"].astype(str).str.extract(r'([\w\.-]+@[\w\.-]+)')
        result["top_locations"] = upi[0].dropna().value_counts().head(10).index.tolist()

    return result


# -------------------------------
# AI ANALYSIS
# -------------------------------
def ai_analysis(text):

    prompt = f"""
You are a cybercrime financial investigator.

Analyze this data and give:

- Fraud pattern
- Suspicious accounts
- Risk level
- Summary

Data:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Expert fraud analyst"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


# -------------------------------
# MAIN API
# -------------------------------
@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    temp_path = f"temp_{file.filename}"

    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # READ FILE
        if file.filename.endswith(".pdf"):
            doc = fitz.open(temp_path)
            text = "".join([p.get_text() for p in doc.pages[:5]])
            doc.close()
            df = None

        elif file.filename.endswith(".csv"):
            df = pd.read_csv(temp_path)
            text = df.head(150).to_string()

        else:
            df = pd.read_excel(temp_path)
            text = df.head(150).to_string()

        # -------------------------------
        # STRUCTURED (EXACT)
        # -------------------------------
        structured = structured_analysis(df) if df is not None else {}

        # -------------------------------
        # AI (SMART)
        # -------------------------------
        ai_report = ai_analysis(text)

        # -------------------------------
        # FINAL RESPONSE
        # -------------------------------
        return {
            "status": "success",
            "data": {
                "most_frequent_person": structured.get("most_frequent_person", []),
                "top_banks": structured.get("top_banks", []),
                "top_locations": structured.get("top_locations", []),
                "top_utr": structured.get("top_utr", []),
                "suspicious": ai_report,
                "owner_info": "HYBRID AI SCAN COMPLETE"
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
