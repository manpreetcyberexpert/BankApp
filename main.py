from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz
import pandas as pd
import re
import os
import json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_engine(text):
    patterns = {
        "upi": r"(?:UPI/|PAYTM/|GPR/|TRANSFER\sTO\s)(?:[^/]+/){0,2}([^/ \n\d]{3,})",
        "utr": r"\b\d{12}\b",
        "banks": r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|YESB|CANARA|IDBI|PAYTM|FEDERAL|CENTRAL|UNION|CASH|WDL)",
        "locs": r"(?:ATM/|POS/|WDL/|LOCATION:)([A-Z\s]{4,})",
        "dates": r"\d{2}-\d{2}-\d{2,4}"
    }
    
    results = {}
    raw_data = []
    
    lines = text.split('\n')
    for line in lines:
        amount_match = re.search(r"(\d{1,3}(?:,\d{2,3})*(?:\.\d{2})?)", line)
        date_match = re.search(patterns["dates"], line)
        if date_match and amount_match:
            raw_data.append({
                "date": date_match.group(),
                "desc": line[:50].strip(),
                "amount": amount_match.group()
            })

    for key, pattern in patterns.items():
        if key == "dates": continue
        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            counts = pd.Series([f.strip().upper() for f in found]).value_counts().head(10)
            results[key] = "\n".join([f"• {k} ({v})" for k, v in counts.items()])
        else:
            results[key] = "No Records Identified"
            
    results["detailed_json"] = json.dumps(raw_data[:100])
    return results

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        doc = fitz.open(temp)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        res = forensic_engine(text)
        return {"status": "success", "data": {
            "most_frequent_person": res["upi"],
            "top_banks": res["banks"],
            "top_locations": res["locs"],
            "top_utr": res["utr"],
            "suspicious": res["detailed_json"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
