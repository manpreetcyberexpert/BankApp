from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, numpy as np, os, json, re
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class BankingForensicEngine:
    @staticmethod
    def extract_and_validate(temp_path):
        doc = fitz.open(temp_path)
        all_tables = []
        for page in doc:
            tabs = page.find_tables(strategy="text")
            for tab in tabs:
                df = tab.to_pandas()
                if not df.empty: all_tables.append(df)
        doc.close()
        
        if not all_tables: return None
        df_master = pd.concat(all_tables, ignore_index=True)
        
        # --- Rule 1: Professional Cleaning (Excel-Style) ---
        df_master = df_master.replace(r'^\s*$', np.nan, regex=True).dropna(how='all')
        
        # --- Rule 2: Amount & Date Standardisation ---
        # Identifying Amount Column via Variance
        numeric_df = df_master.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',', ''), errors='coerce'))
        amt_col = numeric_df.std().idxmax()
        
        # Identifying Date Column
        date_col = None
        for col in df_master.columns:
            if any(re.search(r'\d{2}[-/]\d{2}[-/]\d{2,4}', str(x)) for x in df_master[col].head(10)):
                date_col = col
                break
        
        # --- Rule 3: Mathematical Forensic Audit ---
        amounts = numeric_df[amt_col].dropna()
        total_cr = float(amounts[amounts > 0].sum())
        total_dr = float(amounts[amounts < 0].sum().abs())
        
        # Risk Flags
        high_risk_trx = len(amounts[amounts.abs() > 100000]) # 1 Lakh+
        
        return {
            "df_sample": df_master.head(200).to_string(),
            "math_stats": f"Volume: {len(df_master)} | Total Cr: ₹{total_cr:,.2f} | Total Dr: ₹{total_dr:,.2f}",
            "risk_flag": f"High-Value Alerts: {high_risk_trx} identified"
        }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        engine = BankingForensicEngine()
        audit = engine.extract_and_validate(temp)
        
        if not audit: return {"status": "error", "message": "Grid Not Detected"}

        # AI Investigation with Mathematical Grounding
        prompt = f"""
        Role: Haryana Police Senior Financial Auditor.
        Math Data: {audit['math_stats']} | {audit['risk_flag']}
        
        Analyze the transactions for SMURFING, LAYERING, and STRUCTURING.
        Return STRICT JSON with EXACT keys:
        {{
          "most_frequent_person": "Top 10 beneficiary names with counts",
          "top_banks": "Identified Bank names and accounts",
          "top_locations": "ATM/POS footprints",
          "top_utr": "12-digit UTR list of suspicious transfers",
          "suspicious": "10-line DEEP Forensic Analysis using Banking Formulas (Hindi-English).",
          "owner_info": "{audit['math_stats']} | {audit['risk_flag']}"
        }}
        Data: {audit['df_sample'][:6000]}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a Banking Forensic Expert."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return {"status": "success", "data": json.loads(response.choices[0].message.content)}

    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
