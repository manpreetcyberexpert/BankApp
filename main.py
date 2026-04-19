from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import pandas as pd
import re
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/analyze")
async def analyze_statement(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        all_text = ""
        with pdfplumber.open(temp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: all_text += text + "\n"

        if not all_text.strip():
            return {"status": "success", "data": {
                "most_frequent_person": "No Text Found", "top_banks": "N/A", 
                "top_locations": "N/A", "top_utr": "N/A", "suspicious": "N/A"
            }}

        # Analysis Logic (RegEx based)
        upi_names = re.findall(r'UPI/.*?/(.*?)/', all_text)
        utrs = re.findall(r'\d{12}', all_text)
        banks = re.findall(r'(HDFC|SBI|ICICI|AXIS|PNB|BOB|PAYTM|KOTAK)', all_text, re.I)

        def format_top_10(data_list):
            if not data_list: return "No Records"
            counts = pd.Series(data_list).value_counts().head(10)
            return "\n".join([f"{k} ({v})" for k, v in counts.items()])

        return {
            "status": "success",
            "data": {
                "most_frequent_person": format_top_10(upi_names),
                "top_banks": format_top_10(banks),
                "top_locations": "Scanning Locations...",
                "top_utr": format_top_10(utrs),
                "suspicious": "Analysis in Progress"
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)
