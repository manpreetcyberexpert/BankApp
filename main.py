from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def forensic_master_scanner(text):
    # 1. खाताधारक की पहचान (अक्सर टॉप पर होता है)
    name_match = re.search(r"(?:Name|Account Holder|Customer)\s*:\s*([A-Z\s]{3,})", text, re.I)
    acc_match = re.search(r"(?:Account|A/c)\s*(?:No|Number)?\s*:\s*(\d{9,18})", text, re.I)
    
    owner_info = f"👤 Name: {name_match.group(1).strip() if name_match else 'Not Found'}\n💳 A/c: {acc_match.group(1) if acc_match else 'Not Found'}"

    patterns = {
        "outgoing": r"(?:UPI/|PAYTM/|TO\s|TRANSFER\sTO\s|GPR/)(?:[^/]+/){0,2}([^/ \n\d]{3,})",
        "incoming": r"(?:CR\sFROM|TRANSFER-FROM-|BY\s|UPI/)(?:[^/]+/){0,2}([^/ \n\d]{3,})",
        "banks": r"(HDFC|SBI|ICICI|AXIS|PNB|BOB|KOTAK|PYTM|FEDERAL|IDBI|UNION|CANARA)",
        "atm_ids": r"(?:ATM/|POS/|WDL/|S\d[A-Z0-9]{4,}|[A-Z]{3}\d{4,})",
        "utr": r"\b\d{12}\b"
    }
    
    results = {}
    ledger = []
    lines = text.split('\n')
    for line in lines:
        amount = re.findall(r"(\d{1,10}\.\d{2})", line)
        date = re.search(r"\d{2}-\d{2}-\d{2,4}", line)
        if date and amount:
            m_type = "DEBIT" if any(x in line.upper() for x in ["UPI", "TRANSFER", "WDL", "ATM", "DR"]) else "CREDIT"
            ledger.append({"date": date.group(), "amt": amount[-1], "type": m_type, "desc": line[:50]})

    def get_top_list(pattern, src_text):
        found = re.findall(pattern, src_text, re.I)
        if not found: return "Record Not Found"
        counts = pd.Series([f.strip().upper() for f in found if len(f.strip()) > 2]).value_counts().head(10)
        return "\n".join([f"• {k} ({v} times)" for k, v in counts.items()])

    return {
        "owner": owner_info,
        "person": f"💰 OUTGOING (TO):\n{get_top_list(patterns['outgoing'], text)}\n\n📥 INCOMING (FROM):\n{get_top_list(patterns['incoming'], text)}",
        "banks": get_top_list(patterns['banks'], text),
        "locs": get_top_list(patterns['atm_ids'], text),
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
        res = forensic_master_scanner(text)
        return {"status": "success", "data": {
            "most_frequent_person": res["person"],
            "top_banks": res["banks"],
            "top_locations": res["locs"],
            "top_utr": res["utr"],
            "suspicious": res["ledger"],
            "owner_info": res["owner"] # New Field
        }}
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
