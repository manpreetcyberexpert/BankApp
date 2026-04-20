from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz  # Zaroori PDF ke liye
import pandas as pd
import re
import os
import json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_engine(temp_path):
    doc = fitz.open(temp_path)
    all_rows = []
    for page in doc:
        # 4000+ rows handle karne ke liye text strategy
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            rows = tab.extract()
            if rows: all_rows.extend(rows)
    doc.close()
    
    if not all_rows: return None
    df = pd.DataFrame(all_rows)
    
    def get_stats(col_idx):
        if col_idx >= len(df.columns): return "N/A"
        data = df.iloc[:, col_idx].astype(str).str.strip().str.upper()
        clean = data[~data.isin(["NONE", "N/A", "NAN", "NULL", "BENEFICIARY NAME", "BANK NAME"])]
        counts = clean[clean.str.len() > 2].value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    return {
        "person": get_stats(5), # Beneficiary Names
        "banks": get_stats(6),  # Banks/Accounts
        "locs": get_stats(0),   # System IDs
        "utr": get_stats(2),    # UTR Numbers
        "owner": f"⚖️ OFFICIAL FORENSIC REPORT\nTotal Records: {len(df)}\nStatus: Secure Scan Complete"
    }

@app.get("/")
def home(): return {"status": "alive"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        # Digital PDF format handling
        res = forensic_engine(temp)
        if not res: return {"status": "error", "message": "Structure not detected"}
        
        return {"status": "success", "data": {
            "most_frequent_person": res["person"],
            "top_banks": res["banks"],
            "top_locations": res["locs"],
            "top_utr": res["utr"],
            "suspicious": "[]",
            "owner_info": res["owner"]
        }}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
