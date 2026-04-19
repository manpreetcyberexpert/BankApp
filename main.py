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

        # --- ADVANCED EXTRACTION LOGIC ---
        # UPI IDs (Names)
        upi_names = re.findall(r'UPI/.*?/(.*?)/', all_text)
        # UTR Numbers (12 Digits)
        utrs = re.findall(r'\d{12}', all_text)
        # ATM IDs & Locations
        atm_locations = re.findall(r'ATM-(.*?)\s', all_text)
        # Banks (Keywords)
        banks = re.findall(r'(HDFC|SBI|ICICI|AXIS|PNB|BOB|PAYTM|KOTAK)', all_text, re.I)
        # High Value Transactions (>20,000)
        suspicious = re.findall(r'[Rr][Ss]\.?\s?(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)', all_text)
        suspicious_flags = [s for s in suspicious if float(s.replace(',', '')) > 20000]

        def get_top_10(data_list):
            if not data_list: return "No Record Found"
            counts = pd.Series(data_list).value_counts().head(10)
            return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

        analysis_data = {
            "most_frequent_person": get_top_10(upi_names),
            "top_banks": get_top_10(banks),
            "top_locations": get_top_10(atm_locations),
            "top_utr": get_top_10(utrs),
            "suspicious": f"⚠️ Found {len(suspicious_flags)} High Value Transfers!\n" + "\n".join(suspicious_flags[:5])
        }

        return {"status": "success", "data": analysis_data}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)
