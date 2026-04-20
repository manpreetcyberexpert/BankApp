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
# 🔧 NORMALIZE DATA (CORE LOGIC)
# -------------------------------
def normalize_dataframe(df):
    df.columns = [str(c).strip().upper() for c in df.columns]

    mapping = {}

    for col in df.columns:
        if "DATE" in col:
            mapping[col] = "DATE"
        elif "AMOUNT" in col or "INR" in col:
            mapping[col] = "AMOUNT"
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
        elif "UPI" in col:
            mapping[col] = "UPI"

    df = df.rename(columns=mapping)
    return df


# -------------------------------
# 🧠 ANALYTICS ENGINE
# -------------------------------
def analyze(df):

    df = normalize_dataframe(df)

    # Cleaning
    df['DATE'] = pd.to_datetime(df.get('DATE'), errors='coerce')

    df['CREDIT'] = pd.to_numeric(df.get('CREDIT', 0), errors='coerce').fillna(0)
    df['DEBIT'] = pd.to_numeric(df.get('DEBIT', 0), errors='coerce').fillna(0)

    df['FINAL_AMOUNT'] = df['CREDIT'] - df['DEBIT']

    df['ONLY_DATE'] = df['DATE'].dt.date
    df['HOUR'] = df['DATE'].dt.hour

    # Top Accounts
    top_accounts = df['ACCOUNT'].value_counts().head(10)

    # Top Banks
    top_banks = df['BANK'].value_counts().head(10)

    # Money Received
    top_received = df[df['FINAL_AMOUNT'] > 0] \
        .groupby('ACCOUNT')['FINAL_AMOUNT'] \
        .sum().sort_values(ascending=False).head(10)

    # Money Sent
    top_sent = df[df['FINAL_AMOUNT'] < 0] \
        .groupby('ACCOUNT')['FINAL_AMOUNT'] \
        .sum().abs().sort_values(ascending=False).head(10)

    # UTR
    top_utr = df['UTR'].value_counts().head(10) if 'UTR' in df.columns else {}

    # UPI
    top_upi = df['UPI'].value_counts().head(10) if 'UPI' in df.columns else {}

    # Dates
    top_dates = df['ONLY_DATE'].value_counts().head(10)

    # Time
    top_hours = df['HOUR'].value_counts().head(10)

    return {
        "top_accounts": top_accounts.to_dict(),
        "top_banks": top_banks.to_dict(),
        "top_received": top_received.to_dict(),
        "top_sent": top_sent.to_dict(),
        "top_utr": top_utr if isinstance(top_utr, dict) else top_utr.to_dict(),
        "top_upi": top_upi if isinstance(top_upi, dict) else top_upi.to_dict(),
        "top_dates": {str(k): int(v) for k, v in top_dates.items()},
        "top_hours": top_hours.to_dict()
    }


# -------------------------------
# 🚀 API
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    df = pd.read_excel(file.file)

    result = analyze(df)

    return {
        "status": "success",
        "data": result
    }
