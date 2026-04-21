"""
AURA Cyber Forensics - AI Financial Investigation System
FastAPI Backend (main.py)

Requirements (requirements.txt):
    fastapi==0.111.0
    uvicorn[standard]==0.30.0
    python-multipart==0.0.9
    pandas==2.2.2
    openpyxl==3.1.2
    xlrd==2.0.1
    odfpy==1.4.1
    openai==1.35.0
    psycopg2-binary==2.9.9
    sqlalchemy==2.0.30
    python-dotenv==1.0.1

Environment Variables (.env):
    DATABASE_URL=postgresql://user:password@host:5432/dbname
    OPENAI_API_KEY=sk-...

Run:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import io
import json
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, JSON, Float,
    text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aura_forensics")

DATABASE_URL = os.getenv("DATABASE_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(
    title="AURA Cyber Forensics API",
    description="AI-Powered Financial Investigation System for Police Cyber Crime Cells",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(500), nullable=False)
    status = Column(String(50), default="processing")
    risk_level = Column(String(20), default="LOW")
    total_transactions = Column(Integer, default=0)
    total_amount = Column(Float, default=0.0)
    extracted_data = Column(JSON, nullable=True)
    ai_investigation = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


COLUMN_CANDIDATES = {
    "account":   ["account", "acc no", "account no", "account number", "acct", "from account", "to account"],
    "bank":      ["bank", "ifsc", "bank name", "branch", "bank code"],
    "amount":    ["amount", "debit", "credit", "transaction amount", "txn amount", "dr", "cr", "value"],
    "date":      ["date", "transaction date", "txn date", "value date", "posting date"],
    "utr":       ["utr", "ref", "reference", "transaction id", "txn id", "chq no", "cheque no", "rrn"],
    "narration": ["narration", "description", "particulars", "remarks", "details", "payment details"],
}


def detect_columns(headers: list[str]) -> dict[str, Optional[str]]:
    lower_headers = [h.lower().strip() for h in headers]
    result = {}
    for field, candidates in COLUMN_CANDIDATES.items():
        found = None
        for candidate in candidates:
            for i, h in enumerate(lower_headers):
                if candidate in h:
                    found = headers[i]
                    break
            if found:
                break
        result[field] = found
    return result


def parse_amount(val) -> float:
    if val is None or val == "":
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("₹", "").replace("$", "").strip())
    except ValueError:
        return 0.0


def analyze_dataframe(df: pd.DataFrame) -> dict:
    cols = detect_columns(list(df.columns))

    account_col = cols.get("account")
    bank_col    = cols.get("bank")
    amount_col  = cols.get("amount")
    date_col    = cols.get("date")
    utr_col     = cols.get("utr")

    df["_account"] = df[account_col].astype(str).str.strip() if account_col else "Unknown"
    df["_bank"]    = df[bank_col].astype(str).str.strip()    if bank_col    else "Unknown"
    df["_amount"]  = df[amount_col].apply(parse_amount)       if amount_col  else 0.0
    df["_date"]    = df[date_col].astype(str).str.strip()     if date_col    else ""
    df["_utr"]     = df[utr_col].astype(str).str.strip()      if utr_col     else ""

    total_transactions = len(df)
    total_amount = float(df["_amount"].sum())

    dates = sorted(df["_date"].dropna().unique().tolist())
    date_range = {
        "from": dates[0]  if dates else "N/A",
        "to":   dates[-1] if dates else "N/A",
    }

    account_grp = df.groupby("_account").agg(
        count=("_amount", "count"),
        total_amount=("_amount", "sum")
    ).reset_index().sort_values("count", ascending=False).head(10)

    top_accounts = [
        {
            "account":     row["_account"],
            "count":       int(row["count"]),
            "totalAmount": float(row["total_amount"]),
        }
        for _, row in account_grp.iterrows()
    ]

    bank_grp = df.groupby("_bank").agg(
        count=("_amount", "count"),
        total_amount=("_amount", "sum")
    ).reset_index().sort_values("count", ascending=False).head(10)

    top_banks = [
        {
            "bank":        row["_bank"],
            "count":       int(row["count"]),
            "totalAmount": float(row["total_amount"]),
        }
        for _, row in bank_grp.iterrows()
    ]

    date_grp = df.groupby("_date").agg(
        count=("_amount", "count"),
        amount=("_amount", "sum")
    ).reset_index().sort_values("count", ascending=False).head(10)

    utr_patterns = [
        {
            "date":   row["_date"],
            "count":  int(row["count"]),
            "amount": float(row["amount"]),
        }
        for _, row in date_grp.iterrows()
    ]

    avg_amount = total_amount / max(total_transactions, 1)
    suspicious_mask = (
        (df["_amount"] > avg_amount * 5) |
        (df["_amount"] == 0) |
        (utr_col is not None and df["_utr"].isin(["", "nan", "None"]))
    )
    suspicious_df = df[suspicious_mask].head(20)

    def suspicious_reason(row):
        if row["_amount"] > avg_amount * 5:
            return "Amount significantly above average"
        if row["_amount"] == 0:
            return "Zero amount transaction"
        return "Missing UTR/Reference number"

    suspicious_transactions = [
        {
            "account": row["_account"],
            "amount":  float(row["_amount"]),
            "date":    row["_date"] or "Unknown",
            "reason":  suspicious_reason(row),
        }
        for _, row in suspicious_df.iterrows()
    ]

    return {
        "totalTransactions":      total_transactions,
        "totalAmount":            total_amount,
        "dateRange":              date_range,
        "topAccounts":            top_accounts,
        "topBanks":               top_banks,
        "mostActiveAccounts":     top_accounts[:5],
        "utrPatterns":            utr_patterns,
        "suspiciousTransactions": suspicious_transactions,
    }


def load_file_to_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name_lower = filename.lower()

    if name_lower.endswith(".csv") or name_lower.endswith(".tsv"):
        sep = "\t" if name_lower.endswith(".tsv") else ","
        try:
            return pd.read_csv(io.BytesIO(file_bytes), sep=sep, dtype=str, encoding="utf-8", on_bad_lines="skip")
        except Exception:
            try:
                return pd.read_csv(io.BytesIO(file_bytes), sep=sep, dtype=str, encoding="latin-1", on_bad_lines="skip")
            except Exception:
                return pd.read_csv(io.BytesIO(file_bytes), sep=None, engine="python", dtype=str, on_bad_lines="skip")

    if name_lower.endswith((".xlsx", ".xlsm", ".xlsb")):
        return pd.read_excel(io.BytesIO(file_bytes), dtype=str, engine="openpyxl")

    if name_lower.endswith(".xls"):
        return pd.read_excel(io.BytesIO(file_bytes), dtype=str, engine="xlrd")

    if name_lower.endswith(".ods"):
        return pd.read_excel(io.BytesIO(file_bytes), dtype=str, engine="odf")

    try:
        return pd.read_csv(io.BytesIO(file_bytes), dtype=str, on_bad_lines="skip")
    except Exception:
        return pd.read_excel(io.BytesIO(file_bytes), dtype=str)


def run_ai_investigation(extracted_data: dict, file_name: str) -> dict:
    top_accounts_text = "\n".join(
        f"- {a['account']}: {a['count']} transactions, ₹{a['totalAmount']:.2f}"
        for a in extracted_data.get("topAccounts", [])
    )
    top_banks_text = "\n".join(
        f"- {b['bank']}: {b['count']} transactions, ₹{b['totalAmount']:.2f}"
        for b in extracted_data.get("topBanks", [])
    )
    suspicious_text = "\n".join(
        f"- Account: {t['account']}, Amount: ₹{t['amount']}, Reason: {t['reason']}"
        for t in extracted_data.get("suspiciousTransactions", [])[:5]
    )

    prompt = f"""You are a senior cyber forensic financial investigator for a police cyber crime cell. Analyze this bank transaction data and provide a comprehensive investigation report.

File: {file_name}
Total Transactions: {extracted_data.get('totalTransactions', 0)}
Total Amount: ₹{extracted_data.get('totalAmount', 0):,.2f}
Date Range: {extracted_data.get('dateRange', {}).get('from', 'N/A')} to {extracted_data.get('dateRange', {}).get('to', 'N/A')}

Top 10 Accounts by Activity:
{top_accounts_text}

Top Banks:
{top_banks_text}

Suspicious Transactions Found: {len(extracted_data.get('suspiciousTransactions', []))}
{suspicious_text}

Provide a JSON response with EXACTLY this structure:
{{
  "riskLevel": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "summary": "2-3 sentence executive summary of the investigation",
  "fraudPatterns": ["pattern1", "pattern2", ...],
  "suspiciousAccounts": ["account1", "account2", ...],
  "keyFindings": ["finding1", "finding2", ...],
  "recommendations": ["rec1", "rec2", ...],
  "networkAnalysis": "2-3 sentences describing the transaction network"
}}

Respond with ONLY the JSON object, no markdown, no explanation."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content or "{}"
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    except Exception as e:
        logger.warning(f"AI investigation failed: {e}")
        return {
            "riskLevel": "MEDIUM",
            "summary": "Analysis completed. Manual review recommended for full investigation.",
            "fraudPatterns": ["Unable to generate AI analysis — check OpenAI API key"],
            "suspiciousAccounts": [
                t["account"] for t in extracted_data.get("suspiciousTransactions", [])[:3]
            ],
            "keyFindings": [
                f"Total of {extracted_data.get('totalTransactions', 0)} transactions analyzed",
                f"Total amount: ₹{extracted_data.get('totalAmount', 0):,.2f}",
            ],
            "recommendations": ["Manual review of suspicious transactions required"],
            "networkAnalysis": "Network analysis requires manual review.",
        }


@app.post("/api/analysis/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    db = SessionLocal()
    report = AnalysisReport(
        file_name=file.filename,
        status="processing",
        risk_level="LOW",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    report_id = report.id

    try:
        df = load_file_to_dataframe(file_bytes, file.filename)
        df.dropna(how="all", inplace=True)
        df.columns = [str(c).strip() for c in df.columns]

        if df.empty:
            raise HTTPException(status_code=400, detail="File has no data rows")

        extracted_data   = analyze_dataframe(df)
        ai_investigation = run_ai_investigation(extracted_data, file.filename)

        report.status             = "complete"
        report.risk_level         = ai_investigation.get("riskLevel", "LOW")
        report.total_transactions = extracted_data["totalTransactions"]
        report.total_amount       = extracted_data["totalAmount"]
        report.extracted_data     = extracted_data
        report.ai_investigation   = ai_investigation
        db.commit()
        db.refresh(report)

        return {
            "id":              str(report.id),
            "fileName":        report.file_name,
            "createdAt":       report.created_at.isoformat(),
            "status":          report.status,
            "extractedData":   report.extracted_data,
            "aiInvestigation": report.ai_investigation,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Analysis failed for report {report_id}: {e}")
        report.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    finally:
        db.close()


@app.get("/api/analysis/history")
def get_history():
    db = SessionLocal()
    try:
        reports = (
            db.query(AnalysisReport)
            .order_by(AnalysisReport.created_at.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "id":                str(r.id),
                "fileName":          r.file_name,
                "createdAt":         r.created_at.isoformat(),
                "totalTransactions": r.total_transactions,
                "riskLevel":         r.risk_level,
                "status":            r.status,
            }
            for r in reports
        ]
    finally:
        db.close()


@app.get("/api/analysis/stats/overview")
def get_stats():
    db = SessionLocal()
    try:
        reports = (
            db.query(AnalysisReport)
            .order_by(AnalysisReport.created_at.desc())
            .all()
        )
        total_reports               = len(reports)
        total_transactions_analyzed = sum(r.total_transactions or 0 for r in reports)
        high_risk_cases             = sum(1 for r in reports if r.risk_level == "HIGH")
        critical_cases              = sum(1 for r in reports if r.risk_level == "CRITICAL")

        recent_activity = [
            {
                "id":                str(r.id),
                "fileName":          r.file_name,
                "createdAt":         r.created_at.isoformat(),
                "totalTransactions": r.total_transactions,
                "riskLevel":         r.risk_level,
                "status":            r.status,
            }
            for r in reports[:5]
        ]

        return {
            "totalReports":              total_reports,
            "totalTransactionsAnalyzed": total_transactions_analyzed,
            "highRiskCases":             high_risk_cases,
            "criticalCases":             critical_cases,
            "recentActivity":            recent_activity,
        }
    finally:
        db.close()


@app.get("/api/analysis/{report_id}")
def get_report(report_id: int):
    db = SessionLocal()
    try:
        report = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return {
            "id":              str(report.id),
            "fileName":        report.file_name,
            "createdAt":       report.created_at.isoformat(),
            "status":          report.status,
            "extractedData":   report.extracted_data,
            "aiInvestigation": report.ai_investigation,
        }
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AURA Cyber Forensics API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
