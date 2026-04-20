from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_scanner(text):
    patterns = {
        # UPI & Names (Incoming/Outgoing)
        "outgoing": r"(?:UPI/|PAYTM/|TO\s|TRANSFER\sTO\s|GPR/)(?:[^/]+/){0,2}([^/ \n\d]{3,})",
        "incoming": r"(?:CR\sFROM|TRANSFER-FROM-|BY\s|UPI/)(?:[^/]+/){0,2}([^/ \n\d]{3,})",
        
        # Banks Identifiers
        "banks": r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|PYTM|YESB|CANARA|UNION|IDBI|CITI|HSBC)",
        
        # ATM ID & Locations (Identifying ATM/S1A... type IDs)
        "atm_ids": r"(?:ATM/|POS/|WDL/|S\d[A-Z0-9]{4,}|[A-Z]{3}\d{4,})",
        "locations": r"(?:ATM|POS|WDL)\s(?:ANY\sWHERE\s)?([A-Z\s]{4,})",
        
        # UTR & Transaction IDs (12 Digits)
        "utr": r"\b\d{12}\b",
        "dates": r"\d{2}-\d{2}-\d{2,4}"
    }
    
    results = {}
    ledger = []
    
    # Forensic Money Flow Analysis
    lines = text.split('\n')
    for line in lines:
        amount = re.findall(r"(\d{1,10}\.\d{2})", line)
        date = re.search(patterns["dates"], line)
        if date and amount:
            is_debit = any(x in line.upper() for x in ["UPI", "TRANSFER", "WDL", "ATM", "DR"])
            m_type = "DEBIT" if is_debit else "CREDIT"
            ledger.append({"date": date.group(), "amt": amount[-1], "type": m_type, "desc": line[:50]})

    def get_top_list(pattern, src_text):
        found = re.findall(pattern, src_text, re.I)
        if not found: return "Record Not Found"
        counts = pd.Series([f.strip().upper() for f in found if len(f.strip()) > 2]).value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    return {
        "person": f"💰 OUTGOING (TO):\n{get_top_list(patterns['outgoing'], text)}\n\n📥 INCOMING (FROM):\n{get_top_list(patterns['incoming'], text)}",
        "banks": get_top_list(patterns['banks'], text),
        "locs": f"🆔 ATM/POS IDs:\n{get_top_list(patterns['atm_ids'], text)}\n\n📍 LOCATIONS:\n{get_top_list(patterns['locations'], text)}",
        "utr": get_top_list(patterns['utr'], text),
        "ledger": json.dumps(ledger[:200])
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        doc = fitz.open(temp)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        res = forensic_scanner(text)
        return {"status": "success", "data": {
            "most_frequent_person": res["person"],
            "top_banks": res["banks"],
            "top_locations": res["locs"],
            "top_utr": res["utr"],
            "suspicious": res["ledger"]
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
