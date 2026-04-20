from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def smart_forensic_engine(temp_path):
    doc = fitz.open(temp_path)
    all_text = ""
    all_rows = []
    
    # 1. टेक्स्ट और टेबल दोनों को पढ़ना (Dual-Mode Scanning)
    for page in doc:
        all_text += page.get_text()
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            rows = tab.extract()
            if rows: all_rows.extend(rows)
    doc.close()
    
    # 2. Smart Identification Logic (बिना कॉलम नंबर के)
    # हम पूरे डेटा में पैटर्न्स ढूंढेंगे
    
    # UTR: 12 अंकों का नंबर या बैंक स्पेसिफिक कोड
    utr_pattern = r"\b\d{12}\b|[A-Z]{4}\d{7,12}"
    # Account Numbers: 9 से 18 अंकों के नंबर जो UTR नहीं हैं
    acc_pattern = r"\b\d{9,11}\b|\b\d{13,18}\b"
    # Names: जो केवल अक्षरों से बने हों और बैंक कीवर्ड्स न हों
    name_pattern = r"\b[A-Z]{3,}\s[A-Z]{3,}(?:\s[A-Z]{3,})?\b"
    # Banks: IFSC कोड या बैंक के नाम
    bank_pattern = r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|PAYTM|IFSC|BARB|SBIN|HDFC0)"

    def get_top_stats(pattern, text_data, exclude_list=[]):
        found = re.findall(pattern, text_data, re.I)
        cleaned = [f.strip().upper() for f in found if f.strip().upper() not in exclude_list]
        if not cleaned: return "No Data Identified"
        counts = pd.Series(cleaned).value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    # बैंक कीवर्ड्स जिन्हें नामों से हटाना है
    junk_keywords = ["BANK", "ACCOUNT", "TRANSFER", "UPI", "TRANSACTION", "ID", "DATE", "TIME"]

    return {
        "person": get_top_stats(name_pattern, all_text, junk_keywords),
        "banks": get_top_stats(bank_pattern, all_text),
        "utr": get_top_stats(utr_pattern, all_text),
        "accounts": get_top_stats(acc_pattern, all_text),
        "owner": f"⚖️ CASE FILE ANALYZED: {os.path.basename(temp_path)}\nForensic Intelligence Level: High"
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = smart_forensic_engine(temp)
        return {"status": "success", "data": {
            "most_frequent_person": res["person"],
            "top_banks": res["banks"],
            "top_locations": f"💳 DETECTED ACCOUNT NUMBERS:\n{res['accounts']}",
            "top_utr": res["utr"],
            "suspicious": "Forensic Engine Active",
            "owner_info": res["owner"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
