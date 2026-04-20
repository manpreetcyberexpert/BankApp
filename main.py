from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import fitz
import os
import numpy as np
import re

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
        sample = " ".join(df.iloc[:, i].astype(str).head(20)).upper()
        if any(k in sample for k in keywords):
            return i
    return None


# -------------------------------
# 🧹 CLEAN DATA
# -------------------------------
def clean_series(series):
    s = series.astype(str).str.upper().str.strip()

    # remove junk
    s = s[~s.str.contains("DATE|AMOUNT|BALANCE|CREDIT|DEBIT", na=False)]
    s = s[~s.str.match(r'^\d{1,2}$')]
    s = s[~s.str.match(r'^\d{1,2}:\d{2}$')]
    s = s[~s.str.contains("AM|PM", na=False)]
    s = s[~s.str.match(r'^[A-Z]$')]
    s = s[s.str.len() > 5]

    return s


# -------------------------------
# 📊 TOP VALUES
# -------------------------------
def get_top(series):
    series = clean_series(series)
    return series.value_counts().head(10).to_dict()


# -------------------------------
# 📂 PDF TABLE PARSER
# -------------------------------
def parse_pdf_table(path):
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
    df = df.replace([None, '', 'None'], np.nan)
    df = df.dropna(how='all')

    return df


# -------------------------------
# 📄 PDF TEXT FALLBACK
# -------------------------------
def parse_pdf_text(path):
    doc = fitz.open(path)
    lines = []

    for page in doc:
        text = page.get_text()
        for line in text.split("\n"):
            if len(line.strip()) > 5:
                lines.append(line.strip())

    doc.close()

    if not lines:
        return None

    return pd.DataFrame(lines, columns=["raw"])


# -------------------------------
# 🧠 MAIN ANALYSIS
# -------------------------------
def analyze(df):

    # if structured table
    if len(df.columns) > 1:

        name_col = find_column(df, ["NAME", "BENEFICIARY"])
        bank_col = find_column(df, ["BANK"])
        utr_col = find_column(df, ["UTR", "REF"])
        acc_col = find_column(df, ["ACCOUNT", "A/C"])
        id_col = find_column(df, ["ID", "TRANSACTION"])

        result = {
            "names": get_top(df.iloc[:, name_col]) if name_col is not None else {},
            "banks": get_top(df.iloc[:, bank_col]) if bank_col is not None else {},
            "accounts": get_top(df.iloc[:, acc_col]) if acc_col is not None else {},
            "utr": get_top(df.iloc[:, utr_col]) if utr_col is not None else {},
            "transaction_ids": get_top(df.iloc[:, id_col]) if id_col is not None else {},
        }

    else:
        # fallback raw text analysis
        text_series = df.iloc[:, 0]

        result = {
            "utr": get_top(text_series[text_series.str.contains(r'\d{10,}', na=False)]),
            "accounts": get_top(text_series[text_series.str.contains(r'\d{9,}', na=False)]),
            "names": get_top(text_series[text_series.str.contains(r'[A-Z]{3,}', na=False)]),
        }

    return result


# -------------------------------
# 🚀 API
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    temp = f"temp_{file.filename}"

    with open(temp, "wb") as f:
        f.write(await file.read())

    try:
        # -------------------------------
        # FILE TYPE HANDLING
        # -------------------------------
        if file.filename.endswith(".pdf"):

            df = parse_pdf_table(temp)

            # fallback if no table
            if df is None:
                df = parse_pdf_text(temp)

                if df is None:
                    return {
                        "status": "error",
                        "message": "File unreadable"
                    }

        elif file.filename.endswith(".csv"):
            df = pd.read_csv(temp)

        else:
            df = pd.read_excel(temp)

        result = analyze(df)

        return {
            "status": "success",
            "data": result
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        if os.path.exists(temp):
            os.remove(temp)
