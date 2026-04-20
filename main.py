from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_grid_scanner(temp_path):
    doc = fitz.open(temp_path)
    rows = []
    # पन्नों से टेबल डेटा निकालना
    for page in doc:
        tables = page.find_tables()
        for table in tables:
            rows.extend(table.extract())
    doc.close()
    
    if not rows: return None
    
    # DataFrame में बदलना (4045 rows को हैंडल करने के लिए)
    df = pd.DataFrame(rows)
    df = df.dropna(how='all').reset_index(drop=True)
    
    # कॉलम पहचान (आपकी इमेज के आधार पर):
    # Col 0: Trans ID, Col 2: UTR, Col 5: Beneficiary Name, Col 6: Bank Name
    def get_stats(col_idx):
        if col_idx >= len(df.columns): return "N/A"
        data = df.iloc[:, col_idx].astype(str).str.strip().str.upper()
        # 'NONE' या खाली डेटा हटाना
        filtered = data[~data.isin(['', 'NONE', 'BENEFICIARY NAME', 'BANK NAME'])]
        counts = filtered.value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    return {
        "owner": f"📂 TOTAL ROWS ANALYZED: {len(df)}\nStatus: Deep Forensic Scan Complete",
        "person": f"👤 TOP BENEFICIARIES:\n{get_stats(5)}",
        "banks": f"🏛️ INTERACTED BANKS:\n{get_stats(6)}",
        "locs": f"🆔 TRANSACTION IDs:\n{get_stats(0)}",
        "utr": f"🔢 UTR / REF LOGS:\n{get_stats(2)}",
        "ledger": json.dumps([{"date": str(r[1]), "amt": str(r[4]), "type": "TRX", "desc": str(r[5])} for r in rows[1:150] if len(r) > 5])
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_grid_scanner(temp)
        if not res: return {"status": "error", "message": "Grid structure not detected"}
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
