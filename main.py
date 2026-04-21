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
        # 1. Extraction
        doc = fitz.open(temp)
        all_tabs = []
        for page in doc:
            tabs = page.find_tables(strategy="text")
            for tab in tabs: all_tabs.append(tab.to_pandas())
        doc.close()

        if not all_tabs: return {"status": "error", "message": "Grid Not Detected"}
        df = pd.concat(all_tabs, ignore_index=True)

        # 2. Math Formula (Excel-style calculation)
        numeric_df = df.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',', ''), errors='coerce'))
        amt_col = numeric_df.std().idxmax()
        amounts = numeric_df[amt_col].dropna()
        total_cr = float(amounts[amounts > 0].sum())
        total_dr = float(amounts[amounts < 0].sum().abs())
        math_summary = f"Total Credit: ₹{total_cr:,.2f} | Total Debit: ₹{total_dr:,.2f}"

        # 3. AI Forensic Prompt (STRICT KEY MATCHING FOR ANDROID)
        prompt = f"""
        Role: Haryana Police Senior Financial Auditor.
        Analyze this data and return STRICT JSON with these EXACT keys.
        Values must be SINGLE STRINGS with \\n.
        
        {{
          "most_frequent_person": "Top 10 beneficiary names and counts",
          "top_banks": "Top 10 banks and account numbers",
          "top_locations": "Identify ATM/POS footprints and suspicious hours",
          "top_utr": "List 12-digit UTR/Ref numbers of high-value transfers",
          "suspicious": "10-line DEEP Forensic Analysis summary (Hindi-English mix) using banking formulas."
        }}
        Data Sample: {df.head(150).to_string()[:5000]}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a professional Cyber Forensic Analyst."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        ai_res = json.loads(response.choices.message.content)
        
        # MAPPING TO YOUR ANDROID DATA CLASS
        return {
            "status": "success",
            "data": {
                "most_frequent_person": ai_res["most_frequent_person"],
                "top_banks": ai_res["top_banks"],
                "top_locations": ai_res["top_locations"],
                "top_utr": ai_res["top_utr"],
                "suspicious": ai_res["suspicious"],
                "owner_info": f"🛡️ HARYANA VIGIL-SCAN | {math_summary}"
            }
        }

    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
