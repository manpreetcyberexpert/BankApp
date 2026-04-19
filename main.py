from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF for PDF
import pandas as pd
import re
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_parser(text):
    # Professional Patterns jo har bank format mein kaam karenge
    patterns = {
        "upi_names": r"(?:UPI/|PAYTM/|GPR/|TRANSFER TO\s)(?:[^/]+/){0,2}([^/ \n\d]{3,})",
        "utr_ids": r"\b\d{12}\b",
        "banks": r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|PYTM|UPI|CASH|WDL)",
        "locations": r"(?:ATM/|POS/|WDL/|LOCATION:)([A-Z\s]{4,})",
    }
    
    results = {}
    for key, pattern in patterns.items():
        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            counts = pd.Series([f.strip() for f in found]).value_counts().head(10)
            results[key] = "\n".join([f"• {k} ({v})" for k, v in counts.items()])
        else:
            results[key] = "Record not identified"
    return results

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    try:
        full_text = ""
        ext = file.filename.lower().split('.')[-1]
        
        # 1. Handle PDF
        if ext == 'pdf':
            doc = fitz.open(temp_path)
            for page in doc: full_text += page.get_text()
            doc.close()
        # 2. Handle Excel (XLS, XLSX)
        elif ext in ['xls', 'xlsx']:
            df = pd.read_excel(temp_path, engine='openpyxl' if ext == 'xlsx' else None)
            full_text = df.to_string()
        # 3. Handle CSV
        elif ext == 'csv':
            df = pd.read_csv(temp_path)
            full_text = df.to_string()
        else:
            return {"status": "error", "message": f"Unsupported Format: {ext}"}

        if not full_text.strip():
            return {"status": "error", "message": "The file seems empty or is a scanned image."}

        analysis = forensic_parser(full_text)
        return {
            "status": "success",
            "data": {
                "most_frequent_person": analysis["upi_names"],
                "top_banks": analysis["banks"],
                "top_locations": analysis["locations"],
                "top_utr": analysis["utr_ids"],
                "suspicious": "🚨 Deep Scan: Transaction Analysis Complete"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Engine Error: {str(e)}"}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)
