from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz  # Zaroori: PDF tables ke liye
import pandas as pd
import re
import os
import json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def smart_grid_parser(temp_path):
    doc = fitz.open(temp_path)
    all_rows = []
    for page in doc:
        # 'text' strategy dense grids (4000+ rows) ke liye best hai
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            rows = tab.extract()
            if rows: all_rows.extend(rows)
    doc.close()
    
    if not all_rows: return None
    
    # Table ko clean data mein badalna
    df = pd.DataFrame(all_rows)
    
    def get_top_stats(col_idx):
        if col_idx >= len(df.columns): return "N/A"
        data = df.iloc[:, col_idx].astype(str).str.strip().str.upper()
        # Junk data filter (Bank names, headers etc.)
        junk = ["NONE", "N/A", "NAN", "NULL", "BENEFICIARY NAME", "BANK NAME", "UTR"]
        clean = data[~data.isin(junk) & (data.str.len() > 2)]
        if clean.empty: return "No Data Identified"
        counts = clean.value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    # Aapke portal format ke hisab se Column Mapping:
    # Col 5: Names, Col 6: Banks/Accounts, Col 2: UTR, Col 0: IDs
    return {
        "person": get_top_stats(5),
        "banks": get_top_stats(6),
        "locs": get_top_stats(0),
        "utr": get_top_stats(2),
        "owner": f"⚖️ OFFICIAL FORENSIC REPORT\nTotal Records: {len(df)}\nUnit: Haryana Vigil-Scan"
    }

@app.get("/")
def home(): return {"status": "alive"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f:
        f.write(await file.read())
    try:
        # PDF handle karne ka forensic method
        res = smart_grid_parser(temp)
        if not res:
            return {"status": "error", "message": "Grid structure not detected"}
        
        return {
            "status": "success",
            "data": {
                "most_frequent_person": res["person"],
                "top_banks": res["banks"],
                "top_locations": res["locs"],
                "top_utr": res["utr"],
                "suspicious": "[]",
                "owner_info": res["owner"]
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
