from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import re

# Safe OpenAI import
try:
    from openai import OpenAI
except:
    OpenAI = None

app = FastAPI()

# Load API key
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if OpenAI and api_key else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# ROOT CHECK
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}


# -------------------------------
# SMART COLUMN DETECTION
# -------------------------------
def normalize_columns(df):
    df.columns = [str(c).strip().upper() for c in df.columns]

    mapping = {}
    for col in df.columns:
        if "DATE" in col:
            mapping[col] = "DATE"
        elif "ACCOUNT" in col:
            mapping[col] = "ACCOUNT"
        elif "NAME" in col:
            mapping[col] = "NAME"
        elif "BANK" in col:
            mapping[col] = "BANK"
        elif "UTR" in col or "REF" in col:
            mapping[col] = "UTR"
        elif "CR" in col or "CREDIT" in col:
            mapping[col] = "CREDIT"
        elif "DR" in col or "DEBIT" in col:
            mapping[col] = "DEBIT"
        elif "DESC" in col or "REMARK" in col:
            mapping[col] = "DESCRIPTION"

    return df.rename(columns=mapping)


# -------------------------------
# FORENSIC ANALYSIS ENGINE
# -------------------------------
def forensic_analysis(df):
    df = normalize_columns(df)

    # Safe numeric conversion
    df["CREDIT"] = pd.to_numeric(df.get("CREDIT", 0), errors="coerce").fillna(0)
    df["DEBIT"] = pd.to_numeric(df.get("DEBIT", 0), errors="coerce").fillna(0)

    df["FINAL"] = df["CREDIT"] - df["DEBIT"]

    insights = {}

    # Top accounts
    if "ACCOUNT" in df.columns:
        insights["top_accounts"] = df["ACCOUNT"].value_counts().head(10).to_dict()

    # Top banks
    if "BANK" in df.columns:
        insights["top_banks"] = df["BANK"].value_counts().head(10).to_dict()

    # Money received
    if "ACCOUNT" in df.columns:
        insights["top_received"] = (
            df[df["FINAL"] > 0]
            .groupby("ACCOUNT")["FINAL"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )

    # Money sent
    if "ACCOUNT" in df.columns:
        insights["top_sent"] = (
            df[df["FINAL"] < 0]
            .groupby("ACCOUNT")["FINAL"]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )

    # UTR
    if "UTR" in df.columns:
        insights["top_utr"] = df["UTR"].value_counts().head(10).to_dict()

    # UPI detection
    if "DESCRIPTION" in df.columns:
        upi = df["DESCRIPTION"].astype(str).str.extract(r'([\w\.-]+@[\w\.-]+)')
        insights["top_upi"] = upi[0].value_counts().head(10).to_dict()

    # Dates
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
        insights["peak_dates"] = df["DATE"].dt.date.value_counts().head(10).to_dict()

    # Suspicious pattern (simple)
    insights["suspicious_flags"] = {
        "high_frequency_accounts": list(insights.get("top_accounts", {}).keys())[:3],
        "high_value_receivers": list(insights.get("top_received", {}).keys())[:3],
    }

    return insights


# -------------------------------
# API
# -------------------------------
@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    try:
        # Read file
        try:
            if file.filename.endswith(".csv"):
                df = pd.read_csv(file.file)
            else:
                df = pd.read_excel(file.file)
        except Exception:
            return {"status": "error", "message": "Invalid file format"}

        if df is None or df.empty:
            return {"status": "error", "message": "Empty file"}

        # Run forensic engine
        structured_data = forensic_analysis(df)

        # AI ANALYSIS (ADVANCED)
        if client:
            sample = df.head(100).to_string()

            prompt = f"""
You are a cyber crime financial investigator.

Analyze this transaction data and generate:

- Fraud pattern detection
- Network behavior analysis
- Suspicious accounts
- Money laundering indicators
- Final investigation summary

Data:
{sample}
"""

            ai_response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "Expert cybercrime analyst"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )

            ai_report = ai_response.choices[0].message.content
        else:
            ai_report = "AI not configured"

        return {
            "status": "success",
            "structured": structured_data,
            "ai_report": ai_report
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
