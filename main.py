from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def find_column(df, keywords):
    for col in df.columns:
        col_text = str(df[col].iloc[0]).upper() if not df.empty else ""
        if any(key in col_text for key in keywords):
            return col
    return None

def advanced_forensic_engine(temp_path):
    doc = fitz.open(temp_path)
    all_tabs = []
    for page in doc:
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            all_tabs.append(tab.to_pandas())
    doc.close()

    if not all_tabs: return None
    df = pd.concat(all_tabs, ignore_index=True)
    
    # Cleaning: Pehli row agar title hai toh headers set karein
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

    # 1. Accounts/Names Identification
    acc_col = find_column(df, ["ACCOUNT", "A/C", "BENEFICIARY"])
    bank_col = find_column(df, ["BANK", "IFSC"])
    utr_col = find_column(df, ["UTR", "REF", "TRANSACTION ID"])
    loc_col = find_column(df, ["LOCATION", "ATM", "ADDRESS"])

    def extract_top_10(col_name, label):
        if col_name is not None:
            data = df[col_name].astype(str).str.strip().str.upper()
            data = data[~data.isin(["NONE", "N/A", "", "NAN", "NULL"])]
            counts = data.value_counts().head(10)
            return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])
        return f"No {label} identified in grid."

    return {
        "owner": f"📊 SCAN COMPLETE\nTotal Entries: {len(df)}\nColumns Scanned: {len(df.columns)}",
        "person": f"👤 ACCOUNT/BENEFICIARY NAMES:\n{extract_top_10(acc_col, 'Names')}",
        "banks": f"🏛️ BANK ACCOUNTS/DETAILS:\n{extract_top_10(bank_col, 'Bank Details')}",
        "utr": f"🔢 UTR / REF NUMBERS:\n{extract_top_10(utr_col, 'UTRs')}",
        "locs": f"📍 ATM / LOCATION LOGS:\n{extract_top_10(loc_col, 'Locations')}",
        "ledger": json.dumps([{"date": "Entry", "amt": "Check", "type": "TRX", "desc": "Parsed"} for i in range(min(len(df), 20))])
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = advanced_forensic_engine(temp)
        if not res: return {"status": "error", "message": "Grid analysis failed."}
        return {"status": "success", "data": {
            "most_frequent_person": res["person"],
            "top_banks": res["banks"],
            "top_locations": res["locs"],
            "top_utr": res["utr"],
            "suspicious": res["ledger"],
            "owner_info": res["owner"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
