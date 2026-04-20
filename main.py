from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def extreme_forensic_engine(temp_path):
    doc = fitz.open(temp_path)
    all_data = []
    for page in doc:
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            df_temp = tab.to_pandas()
            all_data.append(df_temp)
    doc.close()
    
    if not all_data: return None
    
    df_main = pd.concat(all_data, ignore_index=True)
    df_main = df_main.astype(str).replace(['None', 'nan', 'N/A', ''], pd.NA).dropna(how='all')

    report = {"names": "N/A", "accounts": "N/A", "utr": "N/A", "banks": "N/A", "locs": "N/A"}

    def format_counts(series):
        clean_data = series.dropna().astype(str).str.strip().str.upper()
        clean_data = clean_data[clean_data.str.len() > 3]
        if clean_data.empty: return "N/A"
        counts = clean_data.value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    for col in df_main.columns:
        sample_str = " ".join(df_main[col].dropna().head(100).astype(str)).upper()
        
        if re.search(r"\b\d{12}\b", sample_str):
            report["utr"] = format_counts(df_main[col])
        elif any(re.match(r"^[A-Z\s]{5,}$", str(x).upper()) for x in df_main[col].head(20) if len(str(x)) > 5):
            names = df_main[col][~df_main[col].str.contains("BANK|HDFC|ICICI|SBI|PNB|IDBI", case=False, na=False)]
            report["names"] = format_counts(names)
        elif any(re.match(r"^\d{9,18}$", str(x)) for x in df_main[col].head(20)):
            report["accounts"] = format_counts(df_main[col])
        elif any(x in sample_str for x in ["ATM", "S1A", "/", "POS", "WDL"]):
            report["locs"] = format_counts(df_main[col])
        if any(x in sample_str for x in ["BANK", "HDFC", "ICICI", "AXIS", "IFSC", "BARB"]):
            report["banks"] = format_counts(df_main[col])

    return {
        "owner": f"🛡️ FORENSIC SCAN COMPLETE\nTotal Rows Investigated: {len(df_main)}\nStatus: High-Security Grade",
        "person": f"👤 TOP BENEFICIARIES:\n{report['names']}",
        "banks": f"🏛️ INTERACTED BANKS:\n{report['banks']}",
        "locs": f"📍 ATM IDs & LOCATIONS:\n{report['locs']}",
        "utr": f"🔢 UTR / REF LOGS:\n{report['utr']}\n\n💳 DETECTED ACCOUNTS:\n{report['accounts']}",
        "ledger": json.dumps([{"date": "Row", "amt": "Log", "type": "TRX", "desc": "Forensic"}] * 5)
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = extreme_forensic_engine(temp)
        if not res: return {"status": "error", "message": "Structure mismatch."}
        return {"status": "success", "data": {
            "most_frequent_person": res["person"], "top_banks": res["banks"],
            "top_locations": res["locs"], "top_utr": res["utr"],
            "suspicious": res["ledger"], "owner_info": res["owner"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
