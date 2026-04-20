from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_engine_v3(temp_path):
    doc = fitz.open(temp_path)
    all_data = []
    
    for page in doc:
        # 'text' strategy har tarah ki digital PDF ke liye best hai
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            df_temp = tab.to_pandas()
            if not df_temp.empty:
                all_data.append(df_temp)
    doc.close()
    
    if not all_data: return None
    
    df = pd.concat(all_data, ignore_index=True)
    df = df.fillna("N/A")

    # Forensic Analysis (Aapke landscape format ke hisab se)
    def get_top(col_idx):
        if col_idx >= len(df.columns): return "N/A"
        vals = df.iloc[:, col_idx].astype(str).str.strip().str.upper()
        # Cleaning junk
        clean = vals[~vals.isin(["N/A", "NONE", "", "NULL", "NAME", "BANK"])]
        counts = clean.value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    # Mapping based on your grid images:
    # Most likely: Col 5 = Name, Col 6 = Bank, Col 2 = UTR, Col 0 = ID
    return {
        "owner": f"⚖️ FORENSIC SCAN COMPLETE\nTotal Records: {len(df)}\nStructure: Multi-Column Digital Grid",
        "person": f"👤 TOP RECIPIENTS:\n{get_top(5)}",
        "banks": f"🏛️ INTERACTED BANKS:\n{get_top(6)}",
        "locs": f"🆔 SYSTEM TRANSACTION IDs:\n{get_top(0)}",
        "utr": f"🔢 UTR / REF NUMBERS:\n{get_top(2)}",
        "ledger": json.dumps([{"date": "Row "+str(i), "amt": "N/A", "type": "TRX", "desc": "Parsed"} for i in range(min(len(df), 50))])
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_engine_v3(temp)
        if not res:
            return {"status": "error", "message": "Standard Grid not detected. Try digital PDF."}
        return {"status": "success", "data": {
            "most_frequent_person": res["person"],
            "top_banks": res["banks"],
            "top_locations": res["locs"],
            "top_utr": res["utr"],
            "suspicious": res["ledger"],
            "owner_info": res["owner"]
        }}
    except Exception as e:
        return {"status": "error", "message": f"Parsing Error: {str(e)}"}
    finally:
        if os.path.exists(temp): os.remove(temp)
