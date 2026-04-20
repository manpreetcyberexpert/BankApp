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
# Normalize Columns
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
        elif "CR" in col:
            mapping[col] = "CREDIT"
        elif "DR" in col:
            mapping[col] = "DEBIT"

    return df.rename(columns=mapping)


# -------------------------------
# Clean Text (IMPORTANT)
# -------------------------------
def clean_text(series):
    s = series.astype(str).str.upper().str.strip()

    # remove junk words
    s = s[~s.str.contains("ACCOUNT|TRANSACTION|ID|NO|DATE|AMOUNT|BALANCE", na=False)]

    # remove small garbage
    s = s[s.str.len() > 5]

    # remove small numbers like 12, 05
    s = s[~s.str.match(r'^\d{1,3}$')]

    return s


# -------------------------------
# Extract Valid UTR
# -------------------------------
def extract_utr(series):
    s = series.astype(str)
    s = s[s.str.match(r'^[A-Z0-9]{10,}$')]
    return s


# -------------------------------
# Extract Valid Account Numbers
# -------------------------------
def extract_accounts(series):
    s = series.astype(str)
    s = s[s.str.match(r'^\d{9,}$')]
    return s


# -------------------------------
# MAIN ANALYSIS
# -------------------------------
def analyze(df):

    df = normalize_columns(df)

    result = {}

    # -------------------------------
    # ACCOUNTS
    # -------------------------------
    if 'ACCOUNT' in df.columns:
        acc = extract_accounts(df['ACCOUNT'])
        result['accounts'] = acc.value_counts().head(10).to_dict()
    else:
        result['accounts'] = {}

    # -------------------------------
    # BANKS
    # -------------------------------
    if 'BANK' in df.columns:
        banks = clean_text(df['BANK'])
        result['banks'] = banks.value_counts().head(10).to_dict()
    else:
        result['banks'] = {}

    # -------------------------------
    # NAMES
    # -------------------------------
    if 'NAME' in df.columns:
        names = clean_text(df['NAME'])
        result['names'] = names.value_counts().head(10).to_dict()
    else:
        result['names'] = {}

    # -------------------------------
    # UTR
    # -------------------------------
    if 'UTR' in df.columns:
        utr = extract_utr(df['UTR'])
        result['utr'] = utr.value_counts().head(10).to_dict()
    else:
        result['utr'] = {}

    # -------------------------------
    # MONEY SENT (DEBIT)
    # -------------------------------
    if 'ACCOUNT' in df.columns and 'DEBIT' in df.columns:
        df['DEBIT'] = pd.to_numeric(df['DEBIT'], errors='coerce').fillna(0)
        sent = df[df['DEBIT'] > 0].groupby('ACCOUNT')['DEBIT'].sum().sort_values(ascending=False)
        result['sent'] = sent.head(10).to_dict()
    else:
        result['sent'] = {}

    return result


# -------------------------------
# API
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}


@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    try:
        if file.filename.endswith(".csv"):
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
