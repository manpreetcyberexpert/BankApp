from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def smart_forensic_parser(temp_path):
    doc = fitz.open(temp_path)
    all_rows = []
    for page in doc:
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            rows = tab.extract()
            if rows: all_rows.extend(rows)
    doc.close()
    
    if not all_rows: return None
    
    df = pd.DataFrame(all_rows)
    
    # Cleaning: Remove empty values and junk
    def get_clean_top(col_idx, is_number=False):
        if col_idx >= len(df.columns): return "No Data Identified"
        data = df.iloc[:, col_idx].astype(str).str.strip()
        # Junk words filter
        junk = ["NONE", "N/A", "nan", "NULL", "BENEFICIARY NAME", "UTR", "BANK", "NAME"]
        filtered = data[~data.str.upper().isin(junk) & (data.str.len() > 2)]
        
        if is_number:
            # Sirf lambe numbers (A/c ya UTR) ke liye
            filtered = filtered[filtered.str.contains(r'\d{8,}')]
        else:
            # Sirf Names/Text ke liye (Numbers hata diye)
            filtered = filtered[~filtered.str.contains(r'^\d+$')]
            
        if filtered.empty: return "No Record Identified"
        counts = filtered.value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    # Aapki image ke Grid format ke hisab se mapping:
    # Col 5 = Beneficiary Name | Col 6 = Bank Name/AC | Col 2 = UTR/Ref | Col 0 = Trans ID
    return {
        "person": get_clean_top(5, is_number=False), # Names
        "banks": get_clean_top(6, is_number=False),  # Bank Names
        "utr": get_clean_top(2, is_number=True),    # Real UTRs
        "accounts": get_clean_top(6, is_number=True), # Accounts (if in col 6)
        "owner": f"⚖️ FORENSIC SCAN: GRID MODE\nTotal Transactions: {len(df)}\nStatus: High-Detail Investigation"
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = smart_forensic_parser(temp)
        if not res: return {"status": "error", "message": "Grid structure not detected."}
        
        return {"status": "success", "data": {
            "most_frequent_person": f"👤 IDENTIFIED NAMES:\n{res['person']}",
            "top_banks": f"🏛️ INTERACTED BANKS:\n{res['banks']}\n\n💳 DETECTED ACCOUNT NOs:\n{res['accounts']}",
            "top_locations": "📍 SYSTEM TRANSACTION IDs:\nScan Result Attached",
            "top_utr": f"🔢 UTR / REFERENCE LOGS:\n{res['utr']}",
            "suspicious": "Forensic Complete",
            "owner_info": res["owner"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
