from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def police_forensic_engine(text):
    # Advanced Forensic Regex
    patterns = {
        "upi_out": r"(?:UPI|PAYTM|GPR)/.*?/(.*?)/", # Paisa Jisko Bheja
        "upi_in": r"TRANSFER-FROM-(.*?)\s",         # Paisa Jahan Se Aaya
        "utr": r"\b\d{12}\b",
        "atm": r"(?:ATM|POS|WDL)/(.*?)\s",
        "banks": r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|PYTM|UPI|CASH|WDL)"
    }
    
    results = {}
    ledger = []
    
    # Line by line Money Flow Analysis
    lines = text.split('\n')
    for line in lines:
        amount = re.findall(r"(\d{1,10}\.\d{2})", line)
        date = re.search(r"\d{2}-\d{2}-\d{2,4}", line)
        if date and amount:
            # Banking Formula: Identify Debit vs Credit based on position or keywords
            type = "DEBIT" if any(x in line.upper() for x in ["UPI", "TRANSFER", "WDL", "ATM"]) else "CREDIT"
            ledger.append({"date": date.group(), "amt": amount[-1], "type": type, "desc": line[:40]})

    for key, pattern in patterns.items():
        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            counts = pd.Series([f.strip().upper() for f in found]).value_counts().head(10)
            results[key] = "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])
        else: results[key] = "No Data Identified"

    results["ledger"] = json.dumps(ledger[:150])
    return results

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        doc = fitz.open(temp)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        res = police_forensic_engine(text)
        return {"status": "success", "data": {
            "most_frequent_person": f"💰 OUTGOING (TO):\n{res['upi_out']}\n\n📥 INCOMING (FROM):\n{res['upi_in']}",
            "top_banks": res["banks"],
            "top_locations": res["atm"],
            "top_utr": res["utr"],
            "suspicious": res["ledger"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
