from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Normalize Data
# -------------------------------
def normalize_dataframe(df):
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
# Analysis Engine
# -------------------------------
def analyze(df):

    df = normalize_dataframe(df)

    # Safe numeric conversion
    df['CREDIT'] = pd.to_numeric(df.get('CREDIT', 0), errors='coerce').fillna(0)
    df['DEBIT'] = pd.to_numeric(df.get('DEBIT', 0), errors='coerce').fillna(0)

    df['FINAL'] = df['CREDIT'] - df['DEBIT']

    # -------------------------------
    # Top Accounts (Most involved)
    # -------------------------------
    if 'ACCOUNT' in df.columns:
        top_accounts = df['ACCOUNT'].value_counts().head(10).to_dict()
    else:
        top_accounts = {}

    # -------------------------------
    # Top Banks
    # -------------------------------
    if 'BANK' in df.columns:
        top_banks = df['BANK'].value_counts().head(10).to_dict()
    else:
        top_banks = {}

    # -------------------------------
    # Money Sent (Used as Locations in UI)
    # -------------------------------
    if 'ACCOUNT' in df.columns:
        top_sent = df[df['FINAL'] < 0] \
            .groupby('ACCOUNT')['FINAL'] \
            .sum().abs().sort_values(ascending=False).head(10).to_dict()
    else:
        top_sent = {}

    # -------------------------------
    # UTR
    # -------------------------------
    if 'UTR' in df.columns:
        top_utr = df['UTR'].value_counts().head(10).to_dict()
    else:
        top_utr = {}

    return top_accounts, top_banks, top_sent, top_utr


# -------------------------------
# API
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}


@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    try:
        # Read file
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

        top_accounts, top_banks, top_sent, top_utr = analyze(df)

        # IMPORTANT: Android-compatible response
        return {
            "status": "success",
            "data": {
                "most_frequent_person": top_accounts,
                "top_banks": top_banks,
                "top_locations": top_sent,
                "top_utr": top_utr
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
