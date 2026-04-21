from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, numpy as np, os, json, re
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        # 1. Deep Grid Extraction (Forensic Grade)
        doc = fitz.open(temp)
        all_tabs = []
        for page in doc:
            tabs = page.find_tables(strategy="text")
            for tab in tabs: all_tabs.append(tab.to_pandas())
        doc.close()

        if not all_tabs: return {"status": "error", "message": "Grid Not Detected"}
        df = pd.concat(all_tabs, ignore_index=True)

        # 2. Banking Math (Excel-style logic)
        # Cleaning amounts for calculation
        df_clean = df.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',', ''), errors='coerce'))
        amt_col = df_clean.std().idxmax()
        amounts = df_clean[amt_col].dropna()
        total_cr = float(amounts[amounts > 0].sum())
        total_dr = float(amounts[amounts < 0].sum().abs())
        math_summary = f"Total Credit: ₹{total_cr:,.2f} | Total Debit: ₹{total_dr:,.2f} | Rows: {len(df)}"

        # 3. AI Investigation (Strictly mapped to Android Keys)
        prompt = f"""
        Role: Senior Haryana Police Financial Investigator.
        Analyze the bank ledger for Fraud, Layering, and Money Laundering.
        Return STRICT JSON with these EXACT keys:
        {{
          "most_frequent_person": "Top 10 names with transaction counts",
          "top_banks": "Top 10 involved banks and accounts",
          "top_locations": "Identify ATM IDs and POS locations",
          "top_utr": "List of 12-digit UTR/Ref numbers",
          "suspicious": "10-line forensic analysis summary (Hindi-English mix) based on math and patterns."
        }}
        Data: {df.head(200).to_string()[:5000]}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a professional Cyber Forensic Auditor."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        ai_res = json.loads(response.choices.message.content)

        # FINAL RESPONSE - MATCHING ANDROID DATA CLASS EXACTLY
        return {
            "status": "success",
            "data": {
                "most_frequent_person": str(ai_res["most_frequent_person"]),
                "top_banks": str(ai_res["top_banks"]),
                "top_locations": str(ai_res["top_locations"]),
                "top_utr": str(ai_res["top_utr"]),
                "suspicious": str(ai_res["suspicious"]),
                "owner_info": f"🛡️ HARYANA VIGIL-SCAN | {math_summary}"
            }
        }

    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
