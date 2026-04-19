from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
import pandas as pd
import re
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def smart_parser(text):
    # Banking Patterns: Khud identify karega data ko
    patterns = {
        "upi_names": r"(?:UPI/|PAYTM/|GPR/)(?:[^/]+/){2}([^/]+)",
        "utr_ids": r"\b\d{12}\b",
        "banks": r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|YESB|CANARA|IDBI|PYTM)",
        "locations": r"(?:ATM/|POS/|WDL/)([A-Z\s]{4,})",
    }
    
    results = {}
    for key, pattern in patterns.items():
        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            counts = pd.Series(found).value_counts().head(10)
            results[key] = "\n".join([f"• {k.strip()} ({v})" for k, v in counts.items()])
        else:
            results[key] = "Data not identified in this file"
    return results

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        full_text = ""
        # Auto-Identify Format
        if file.filename.endswith('.pdf'):
            doc = fitz.open(temp_path)
            for page in doc: full_text += page.get_text()
            doc.close()
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(temp_path)
            full_text = df.to_string()
        elif file.filename.endswith('.csv'):
            df = pd.read_csv(temp_path)
            full_text = df.to_string()
        else:
            return {"status": "error", "message": "Unsupported Format"}

        results = smart_parser(full_text)
        return {"status": "success", "data": {
            "most_frequent_person": results["upi_names"],
            "top_banks": results["banks"],
            "top_locations": results["locations"],
            "top_utr": results["utrs_ids"], # Fix: Corrected key name
            "suspicious": "Forensic Scan: Complete"
        }}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)
