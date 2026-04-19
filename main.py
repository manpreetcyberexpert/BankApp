from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
import pandas as pd
import re
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_scanner(text):
    # Professional Patterns for Indian Banks
    patterns = {
        "upi_names": r"(?:UPI/|PAYTM/|GPR/)(?:[^/]+/){2}([^/]+)",
        "utr_ids": r"\b\d{12}\b",
        "banks": r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|YESB|CANARA|IDBI)",
        "locations": r"(?:ATM/|POS/)([A-Z\s]{4,})",
        "amounts": r"(?:\s|^)(\d{1,3}(?:,\d{2,3})*(?:\.\d{2})?)(?:\s|$)"
    }
    
    results = {}
    for key, pattern in patterns.items():
        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            counts = pd.Series(found).value_counts().head(10)
            results[key] = "\n".join([f"• {k.strip()} ({v})" for k, v in counts.items()])
        else:
            results[key] = "No suspicious records found"
            
    return results

@app.post("/analyze")
async def analyze_statement(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        doc = fitz.open(temp_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        if not full_text.strip():
            return {"status": "error", "message": "Scanned Image PDF detected. Please upload digital PDF."}

        scan_results = forensic_scanner(full_text)

        analysis_data = {
            "most_frequent_person": scan_results["upi_names"],
            "top_banks": scan_results["banks"],
            "top_locations": scan_results["locations"],
            "top_utr": scan_results["utr_ids"],
            "suspicious": "⚠️ High Value Analysis:\nCheck UTR list for bulk transfers."
        }

        return {"status": "success", "data": analysis_data}

    except Exception as e:
        return {"status": "error", "message": f"Engine Error: {str(e)}"}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)
