from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import fitz
import os
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# 🔍 SMART COLUMN DETECTION
# -------------------------------
def detect_column(df, keywords):
    for i in range(len(df.columns)):
        sample = " ".join(df.iloc[:, i].astype(str).head(30)).upper()
        if any(k in sample for k in keywords):
            return i
    return None


# -------------------------------
# 📂 PDF PARSER
# -------------------------------
def parse_pdf(path):
    doc = fitz.open(path)
    rows = []

    for page in doc:
        tables = page.find_tables(strategy="text")
        for t in tables:
            data = t.extract()
            if data:
                rows.extend(data)

    doc.close()

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df = df.replace([None, '', 'None', 'nan'], np.nan)
    df = df.dropna(how='all')

    return df


# -------------------------------
# 🧠 FORENSIC ANALYSIS
# -------------------------------
def analyze(df):

    print("\n📊 RAW DATA PREVIEW:")
    print(df.head(5))
    print("Columns:", df.columns)

    # 🔍 Detect columns
    name_col = detect_column(df, ["NAME", "BENEFICIARY", "CUSTOMER"])
    bank_col = detect_column(df, ["BANK", "IFSC", "BRANCH"])
    utr_col = detect_column(df, ["UTR", "REF", "TXN", "TRANSACTION"])
    acc_col = detect_column(df, ["ACCOUNT", "A/C", "ACC NO", "ACCOUNT NUMBER"])
    amount_col = detect_column(df, ["AMOUNT", "AMT", "INR", "VALUE"])
    date_col = detect_column(df, ["DATE", "TXN DATE", "TRANSACTION DATE"])
    credit_col = detect_column(df, ["CR", "CREDIT", "DEPOSIT"])
    debit_col = detect_column(df, ["DR", "DEBIT", "WITHDRAWAL"])
    atm_col = detect_column(df, ["ATM", "TERMINAL"])
    loc_col = detect_column(df, ["LOCATION", "CITY", "PLACE"])

    if date_col is None:
        return {"error": "Date column not detected. Please upload proper Excel."}

    # -------------------------------
    # 🧹 CLEANING
    # -------------------------------
    df['date'] = pd.to_datetime(df.iloc[:, date_col], errors='coerce')

    df['credit'] = pd.to_numeric(df.iloc[:, credit_col], errors='coerce') if credit_col is not None else 0
    df['debit'] = pd.to_numeric(df.iloc[:, debit_col], errors='coerce') if debit_col is not None else 0
    df['amount'] = pd.to_numeric(df.iloc[:, amount_col], errors='coerce') if amount_col is not None else 0

    df['final_amount'] = df['credit'].fillna(0) - df['debit'].fillna(0)

    df = df.dropna(subset=['date'])

    df['hour'] = df['date'].dt.hour
    df['only_date'] = df['date'].dt.date

    # -------------------------------
    # 📊 HELPER
    # -------------------------------
    def safe_top(series):
        return series.value_counts().head(10).to_dict() if series is not None else {}

    # -------------------------------
    # 🔝 ANALYTICS
    # -------------------------------
    top_accounts = safe_top(df.iloc[:, acc_col]) if acc_col is not None else {}
    top_names = safe_top(df.iloc[:, name_col]) if name_col is not None else {}
    top_banks = safe_top(df.iloc[:, bank_col]) if bank_col is not None else {}

    received_df = df[df['final_amount'] > 0]
    sent_df = df[df['final_amount'] < 0]

    top_received = received_df.groupby(df.iloc[:, acc_col])['final_amount'] \
        .sum().sort_values(ascending=False).head(10).to_dict() if acc_col is not None else {}

    top_sent = sent_df.groupby(df.iloc[:, acc_col])['final_amount'] \
        .sum().abs().sort_values(ascending=False).head(10).to_dict() if acc_col is not None else {}

    bulk_in = received_df.groupby(df.iloc[:, acc_col])['final_amount'] \
        .sum().sort_values(ascending=False).head(5).to_dict() if acc_col is not None else {}

    bulk_out = sent_df.groupby(df.iloc[:, acc_col])['final_amount'] \
        .sum().sort_values().head(5).abs().to_dict() if acc_col is not None else {}

    top_dates = df['only_date'].value_counts().head(10)
    top_dates = {str(k): int(v) for k, v in top_dates.items()}

    top_hours = df['hour'].value_counts().head(10).to_dict()

    top_utr = safe_top(df.iloc[:, utr_col]) if utr_col is not None else {}

    if utr_col is not None:
        upi_series = df.iloc[:, utr_col].astype(str)
        upi_series = upi_series[upi_series.str.contains("@|UPI|PAY", case=False, na=False)]
        top_upi = upi_series.value_counts().head(10).to_dict()
    else:
        top_upi = {}

    top_atm = safe_top(df.iloc[:, atm_col]) if atm_col is not None else {}
    top_locations = safe_top(df.iloc[:, loc_col]) if loc_col is not None else {}

    # -------------------------------
    # 🚨 SUSPICIOUS
    # -------------------------------
    suspicious = {}

    if acc_col is not None:
        freq = df.iloc[:, acc_col].value_counts()
        suspicious["high_frequency_accounts"] = freq[freq > 50].to_dict()

    repeated = df[df.duplicated(['final_amount'], keep=False)]
    suspicious["repeated_transactions"] = len(repeated)

    df['minute'] = df['date'].dt.strftime("%Y-%m-%d %H:%M")
    burst = df['minute'].value_counts()
    suspicious["burst_transactions"] = burst[burst > 20].to_dict()

    # -------------------------------
    # 📦 FINAL OUTPUT
    # -------------------------------
    return {
        "summary": {
            "total_transactions": len(df),
            "total_credit": float(df['credit'].sum()),
            "total_debit": float(df['debit'].sum())
        },
        "top": {
            "accounts": top_accounts,
            "names": top_names,
            "banks": top_banks,
            "received": top_received,
            "sent": top_sent,
            "utr": top_utr,
            "upi": top_upi,
            "atm": top_atm,
            "locations": top_locations
        },
        "bulk_flow": {
            "top_inflow_accounts": bulk_in,
            "top_outflow_accounts": bulk_out
        },
        "timeline": {
            "top_dates": top_dates,
            "top_hours": top_hours
        },
        "suspicious": suspicious
    }


# -------------------------------
# 🚀 API
# -------------------------------
@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    temp_path = f"temp_{file.filename}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        # 📂 File handling
        if file.filename.endswith(".pdf"):
            df = parse_pdf(temp_path)
            if df is None or df.empty:
                return {
                    "status": "error",
                    "message": "Unsupported structure: PDF table detect nahi hua. Excel upload karo."
                }
        else:
            df = pd.read_excel(temp_path)

        result = analyze(df)

        return {
            "status": "success",
            "data": result
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
