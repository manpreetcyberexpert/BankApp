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

@app.get("/")
def home():
    return {"status": "alive"}


# -------------------------------
# Normalize columns
# -------------------------------
def normalize(df):
    df.columns = [str(c).upper().strip() for c in df.columns]

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
# Local Analysis (fast)
# -------------------------------
def local_analysis(df):
    df = normalize(df)

    df["CREDIT"] = pd.to_numeric(df.get("CREDIT", 0), errors="coerce").fillna(0)
    df["DEBIT"] = pd.to_numeric(df.get("DEBIT", 0), errors="coerce").fillna(0)

    df["FINAL"] = df["CREDIT"] - df["DEBIT"]

    result = {}

    if "ACCOUNT" in df.columns:
        result["top_accounts"] = df["ACCOUNT"].value_counts().head(10).to_dict()

        result["top_received"] = (
            df[df["FINAL"] > 0]
            .groupby("ACCOUNT")["FINAL"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )

        result["top_sent"] = (
            df[df["FINAL"] < 0]
            .groupby("ACCOUNT")["FINAL"]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )

    if "BANK" in df.columns:
        result["top_banks"] = df["BANK"].value_counts().head(10).to_dict()

    if "UTR" in df.columns:
        result["top_utr"] = df["UTR"].value_counts().head(10).to_dict()

    if "DESCRIPTION" in df.columns:
        upi = df["DESCRIPTION"].astype(str).str.extract(r'([\w\.-]+@[\w\.-]+)')
        result["top_upi"] = upi[0].value_counts().head(10).to_dict()

    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
        result["peak_dates"] = df["DATE"].dt.date.value_counts().head(10).to_dict()

    return result


# -------------------------------
# MAIN API
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
        except:
            return {"status": "error", "message": "Invalid file format"}

        if df is None or df.empty:
            return {"status": "error", "message": "Empty file"}

        # Run local analysis
        structured = local_analysis(df)

        # -------------------------------
        # AI Analysis
        # -------------------------------
        if client:
            sample = df.head(100).to_string()

            prompt = f"""
You are a cyber crime financial investigator.

Analyze this transaction dataset and provide:

- Fraud patterns
- Suspicious accounts
- Money flow behavior
- Risk summary

Data:
{sample}
"""

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "Expert fraud analyst"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )

            ai_report = response.choices[0].message.content
        else:
            ai_report = "AI not configured"

        # -------------------------------
        # FINAL RESPONSE (ANDROID SAFE)
        # -------------------------------
        return {
            "status": "success",
            "data": {
                "ai_report": ai_report,
                "top_accounts": structured.get("top_accounts", {}),
                "top_banks": structured.get("top_banks", {}),
                "top_received": structured.get("top_received", {}),
                "top_sent": structured.get("top_sent", {}),
                "top_utr": structured.get("top_utr", {}),
                "top_upi": structured.get("top_upi", {}),
                "peak_dates": structured.get("peak_dates", {})
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
