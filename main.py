from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Utilities
# -------------------------------
JUNK_WORDS = [
    "ACCOUNT", "TRANSACTION", "ID", "NO", "DATE", "AMOUNT",
    "BALANCE", "UPI", "NEFT", "IMPS", "RTGS", "TRANSFER"
]

def clean_series(s: pd.Series):
    s = s.astype(str).str.upper().str.strip()
    # remove junk words
    for w in JUNK_WORDS:
        s = s[~s.str.contains(w, na=False)]
    # remove tiny tokens like 12, 05
    s = s[s.str.len() > 5]
    s = s[~s.str.match(r'^\d{1,3}$')]
    return s.dropna()

def extract_utr_from_text(s: pd.Series):
    # long alphanumeric tokens (typical UTRs)
    out = s.str.extract(r'([A-Z0-9]{12,})')[0]
    out = out.dropna()
    return out

def extract_accounts_from_text(s: pd.Series):
    # 9+ digit numbers
    out = s.str.extract(r'(\d{9,})')[0]
    out = out.dropna()
    return out

def extract_names_from_text(s: pd.Series):
    # very simple heuristic: words blocks (avoid pure numbers)
    # you can tune this per your bank format
    out = s.str.extract(r'([A-Z]{3,}\s?[A-Z]{3,})')[0]
    out = out.dropna()
    # filter out tokens that still look like codes
    out = out[~out.str.match(r'^[A-Z0-9]+$')]
    return out

# -------------------------------
# Find likely columns
# -------------------------------
def find_col(df, keywords):
    for c in df.columns:
        cu = str(c).upper()
        if any(k in cu for k in keywords):
            return c
    return None

# -------------------------------
# Main Analysis
# -------------------------------
def analyze(df: pd.DataFrame):

    df.columns = [str(c).strip().upper() for c in df.columns]

    desc_col = find_col(df, ["DESCRIPTION", "NARRATION", "PARTICULAR"])
    debit_col = find_col(df, ["DEBIT", "DR"])
    credit_col = find_col(df, ["CREDIT", "CR"])
    bank_col = find_col(df, ["BANK"])
    name_col = find_col(df, ["NAME"])
    acc_col  = find_col(df, ["ACCOUNT"])
    utr_col  = find_col(df, ["UTR", "REF"])

    # Base text source (prefer description)
    if desc_col:
        text = df[desc_col].astype(str).str.upper()
    else:
        # fallback: combine all columns as text
        text = df.astype(str).agg(" ".join, axis=1).str.upper()

    # -------------------------------
    # UTR
    # -------------------------------
    if utr_col:
        utr_series = clean_series(df[utr_col])
    else:
        utr_series = extract_utr_from_text(text)

    top_utr = utr_series.value_counts().head(10).to_dict()

    # -------------------------------
    # Accounts
    # -------------------------------
    if acc_col:
        acc_series = df[acc_col].astype(str)
        acc_series = acc_series[acc_series.str.match(r'^\d{9,}$')]
    else:
        acc_series = extract_accounts_from_text(text)

    top_accounts = acc_series.value_counts().head(10).to_dict()

    # -------------------------------
    # Names
    # -------------------------------
    if name_col:
        names_series = clean_series(df[name_col])
    else:
        names_series = extract_names_from_text(text)

    top_names = names_series.value_counts().head(10).to_dict()

    # -------------------------------
    # Banks (if present)
    # -------------------------------
    if bank_col:
        banks_series = clean_series(df[bank_col])
        top_banks = banks_series.value_counts().head(10).to_dict()
    else:
        top_banks = {}

    # -------------------------------
    # Money Sent (debit-based)
    # -------------------------------
    if debit_col:
        df[debit_col] = pd.to_numeric(df[debit_col], errors="coerce").fillna(0)
        sent_rows = df[df[debit_col] > 0]

        if acc_col:
            sent_acc = sent_rows[acc_col].astype(str)
            sent_acc = sent_acc[sent_acc.str.match(r'^\d{9,}$')]
        else:
            sent_text = sent_rows.astype(str).agg(" ".join, axis=1).str.upper()
            sent_acc = extract_accounts_from_text(sent_text)

        top_sent = sent_acc.value_counts().head(10).to_dict()
    else:
        top_sent = {}

    return {
        "names": top_names,
        "banks": top_banks,
        "accounts": top_accounts,
        "utr": top_utr,
        "sent": top_sent
    }

# -------------------------------
# API
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)

        if df is None or df.empty:
            return {
                "status": "success",
                "data": {
                    "most_frequent_person": {},
                    "top_banks": {},
                    "top_locations": {},
                    "top_utr": {}
                }
            }

        result = analyze(df)

        # Android-compatible keys
        return {
            "status": "success",
            "data": {
                "most_frequent_person": result["names"] or result["accounts"],
                "top_banks": result["banks"],
                "top_locations": result["sent"],
                "top_utr": result["utr"]
            }
        }

    except Exception as e:
        return {
            "status": "success",
            "data": {
                "most_frequent_person": {},
                "top_banks": {},
                "top_locations": {},
                "top_utr": {},
                "error": str(e)
            }
        }
