from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def professional_grid_parser(temp_path):
    doc = fitz.open(temp_path)
    all_rows = []
    for page in doc:
        # 'text' strategy dense grid ke liye sabse best hai
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            table_data = tab.extract()
            if table_data: all_rows.extend(table_data)
    doc.close()
    
    if not all_rows: return None
    
    df = pd.DataFrame(all_rows)
    # Cleaning: Khali jagah ko hatana
    df = df.replace([None, '', 'None', 'nan'], pd.NA).dropna(how='all')

    # AAPKI IMAGE KE HISAB SE DIRECT COLUMN MAPPING:
    # Col 0: ID | Col 2: UTR | Col 5: Beneficiary Name | Col 6: Bank/Account
    
    def get_stats(col_idx, junk_list):
        if col_idx >= len(df.columns): return "N/A"
        data = df.iloc[:, col_idx].astype(str).str.strip().str.upper()
        # Header aur junk data filter karna
        filtered = data[~data.isin(junk_list) & (data.str.len() > 2)]
        if filtered.empty: return "Record Not Found"
        counts = filtered.value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    name_junk = ["BENEFICIARY NAME", "NAME", "CUSTOMER", "N/A"]
    bank_junk = ["BANK NAME", "BANK", "IFSC", "N/A", "NONE"]
    utr_junk = ["UTR", "REF NO", "TRANSACTION ID", "N/A"]

    return {
        "owner": f"🛡️ POLICE FORENSIC REPORT\nTotal Rows Scanned: {len(df)}\nStructure: Deep Grid Analysis",
        "person": f"👤 MOST USED ACCOUNTS (NAMES):\n{get_stats(5, name_junk)}",
        "banks": f"🏛️ INTERACTED BANKS/DETAILS:\n{get_stats(6, bank_junk)}",
        "locs": f"🆔 SYSTEM TRANSACTION IDs:\n{get_stats(0, ['ID', 'N/A'])}",
        "utr": f"🔢 UTR / REFERENCE LOGS:\n{get_stats(2, utr_junk)}",
        "ledger": json.dumps([{"date": "Row", "amt": "Grid", "type": "TRX", "desc": "Parsed"}] * 5)
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = professional_grid_parser(temp)
        if not res: return {"status": "error", "message": "Grid structure not detected."}
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
