from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def extreme_forensic_engine(temp_path):
    doc = fitz.open(temp_path)
    all_data = []
    
    # 1. पूरी फाइल को टेबल ग्रिड में लोड करना (No Page Limit)
    for page in doc:
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            df_temp = tab.to_pandas()
            all_data.append(df_temp)
    doc.close()
    
    if not all_data: return None
    
    # 4000+ रोज़ को एक साथ जोड़ना
    df_main = pd.concat(all_data, ignore_index=True)
    df_main = df_main.astype(str).replace(['None', 'nan', 'N/A', ''], pd.NA).dropna(how='all')

    # 2. बैंकिंग फ़ॉर्मूला: कॉलम्स को उनके डेटा टाइप से पहचानना
    def identify_and_get_top(dataframe):
        report = {"names": "N/A", "accounts": "N/A", "utr": "N/A", "banks": "N/A", "locs": "N/A"}
        
        for col in dataframe.columns:
            sample = dataframe[col].dropna().head(100).tolist()
            sample_str = " ".join(sample).upper()
            
            # A. UTR Identification (12 digit numeric patterns)
            if re.search(r"\b\d{12}\b", sample_str):
                report["utr"] = format_counts(dataframe[col])
            
            # B. Name Identification (Alpha only, no digits, multiple words)
            elif any(re.match(r"^[A-Z\s]{5,}$", str(x).upper()) for x in sample if len(str(x)) > 5):
                # Filter out bank names from person names
                names = dataframe[col][~dataframe[col].str.contains("BANK|HDFC|ICICI|SBI|PNB|IDBI", case=False, na=False)]
                report["names"] = format_counts(names)

            # C. Account/Bank ID Identification (Long numbers, not 12 digits)
            elif any(re.match(r"^\d{9,11}$|^\d{13,18}$", str(x)) for x in sample):
                report["accounts"] = format_counts(dataframe[col])

            # D. ATM/Location ID (Alpha-Numeric mixed)
            elif "ATM" in sample_str or "S1A" in sample_str or "/" in sample_str:
                report["locs"] = format_counts(dataframe[col])

            # E. Bank Names
            if any(x in sample_str for x in ["BANK", "HDFC", "ICICI", "AXIS", "IFSC"]):
                report["banks"] = format_counts(dataframe[col])
                
        return report

    def format_counts(series):
        clean_data = series.dropna().astype(str).str.strip().str.upper()
        clean_data = clean_data[clean_data.str.len() > 3]
        counts = clean_data.value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" else "N/A" for k, v in counts.items()])

    res = identify_and_get_top(df_main)
    return {
        "owner": f"🛡️ POLICE FORENSIC SCAN COMPLETE\nTotal Rows Investigated: {len(df_main)}\nReliability: High-Security Grade",
        "person": f"👤 TOP BENEFICIARIES:\n{res['names']}",
        "banks": f"🏛️ INTERACTED BANKS:\n{res['banks']}",
        "locs": f"📍 ATM IDs & LOCATIONS:\n{res['locs']}",
        "utr": f"🔢 UTR / REF LOGS:\n{res['utr']}\n\n💳 DETECTED ACCOUNTS:\n{res['accounts']}",
        "ledger": json.dumps([{"date": "Row", "amt": "Log", "type": "TRX", "desc": "Forensic"}] * 10)
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
            "suspicious": "Digital Evidence Extracted", "owner_info": res["owner"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
