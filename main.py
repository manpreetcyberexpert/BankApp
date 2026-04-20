from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
import pandas as pd
import re
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_engine(text):
    data = {
        "beneficiaries": re.findall(r"(?:UPI/|TO\s|TRANSFER\sTO\s)([^/ \n\d]{4,})", text, re.I),
        "banks": re.findall(r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|PAYTM|FEDERAL)", text, re.I),
        "locations": re.findall(r"(?:ATM/|POS/|WDL/)([A-Z\s]{4,})", text),
        "utr_ids": re.findall(r"\b\d{12}\b", text),
        "dates": re.findall(r"\d{2}-\d{2}-\d{2,4}", text)
    }
    
    def get_top_10(src):
        if not src: return "N/A"
        counts = pd.Series([s.strip().upper() for s in src]).value_counts().head(10)
        return "\n".join([f"• {k} ({v})" for k, v in counts.items()])

    return {
        "person": get_top_10(data["beneficiaries"]),
        "banks": get_top_10(data["banks"]),
        "locs": get_top_10(data["locations"]),
        "utr": get_top_10(data["utr_ids"]),
        "dates": get_top_10(data["dates"])
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        doc = fitz.open(temp)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        
        results = forensic_engine(text)
        return {"status": "success", "data": {
            "most_frequent_person": results["person"],
            "top_banks": results["banks"],
            "top_locations": results["locs"],
            "top_utr": results["utr"],
            "suspicious": f"Analysis complete. Found transactions on {len(results['dates'].splitlines())} dates."
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
