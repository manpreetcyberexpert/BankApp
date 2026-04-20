from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import fitz
import os
import re
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
def find_column(df, keywords):
    for i in range(len(df.columns)):
        sample = " ".join(df.iloc[:, i].astype(str).head(30)).upper()
        if any(k in sample for k in keywords):
            return i
    return None


# -------------------------------
# 🧹 CLEAN DATA (AI STYLE FILTER)
# -------------------------------
def clean_series(series, type="text"):
    s = series.astype(str).str.upper().str.strip()

    # remove junk
    junk = ["N/A", "NONE", "NULL", "NAN", "", "0", "ID", "NO"]
    s = s[~s.isin(junk)]

    # remove short garbage
    s = s[s.str.len() > 5]

    # remove time/date garbage
    s = s[~s.str.match(r'^\d{1,2}$')]
    s = s[~s.str.match(r'^\d{1,2}:\d{2}$')]
    s = s[~s.str.contains("AM|PM", na=False)]

    # remove single letters
    s = s[~s.str.match(r'^[A-Z]$')]

    # type-based filtering
    if type == "name":
        s = s[s.str.contains(r'[A-Z]{3,}', na=False)]

    elif type == "utr":
        s = s[s.str.match(r'^\d{10,}$')]

    elif type == "account":
        s = s[s.str.match(r'^\d{9,}$')]

    return s


# -------------------------------
# 📊 TOP CALCULATION
# -------------------------------
def get_top(df, col_idx, type="text"):
    if col_idx is None or col_idx >= len(df.columns):
        return {}

    data = clean_series(df.iloc[:, col_idx], type)
    return data.value_counts().head(10).to_dict()


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

    # 🔍 detect columns
    name_col = find_column(df, ["NAME", "BENEFICIARY"])
    bank_col = find_column(df, ["BANK", "IFSC"])
    utr_col = find_column(df, ["UTR", "REF"])
    acc_col = find_column(df, ["ACCOUNT", "A/C"])
    id_col = find_column(df, ["ID", "TRANSACTION"])

    # -------------------------------
    # 📊 extract data
    # -------------------------------
    top_names = get_top(df, name_col, "name")
    top_banks = get_top(df, bank_col, "text")
    top_utr = get_top(df, utr_col, "utr")
    top_accounts = get_top(df, acc_col, "account")
    top_ids = get_top(df, id_col, "text")

    # -------------------------------
    # 🚨 suspicious detection
    # -------------------------------
    suspicious = {}

    if acc_col is not None:
        acc_series = clean_series(df.iloc[:, acc_col], "account")
        freq = acc_series.value_counts()
        suspicious["high_frequency_accounts"] = freq[freq > 10].to_dict()

    # -------------------------------
    # 📦 final output
    # -------------------------------
    return {
        "summary": {
            "total_rows": len(df)
        },
        "top": {
            "names": top_names,
            "banks": top_banks,
            "accounts": top_accounts,
            "utr": top_utr,
            "transaction_ids": top_ids
        },
        "suspicious": suspicious
    }


# -------------------------------
# 🚀 API
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    temp_path = f"temp_{file.filename}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        if file.filename.endswith(".pdf"):
            df = parse_pdf(temp_path)
            if df is None:
                return {"status": "error", "message": "PDF structure not detected"}
        else:
            df = pd.read_excel(temp_path)

        result = analyze(df)

        return {"status": "success", "data": result}

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
