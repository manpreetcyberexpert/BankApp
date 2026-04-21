from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, pandas as pd, re, os, json
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Render Environment Variables se API Key uthana
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def forensic_ai_engine(temp_path):
    doc = fitz.open(temp_path)
    all_rows = []
    text_sample = ""
    for i, page in enumerate(doc):
        if i < 5: text_sample += page.get_text() # AI Analysis ke liye shuruati data
        tabs = page.find_tables(strategy="text")
        for tab in tabs:
            rows = tab.extract()
            if rows: all_rows.extend(rows)
    doc.close()
    
    if not all_rows: return None
    df = pd.DataFrame(all_rows)
    
    def get_stats(col_idx):
        if col_idx >= len(df.columns): return "N/A"
        data = df.iloc[:, col_idx].astype(str).str.strip().str.upper()
        clean = data[~data.isin(["NONE", "N/A", "NAN", "NULL", "BENEFICIARY NAME", "BANK NAME"])]
        return "\n".join([f"• {k} ({v} times)" for k, v in clean.value_counts().head(10).items()])

    # --- AI INVESTIGATION ---
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a Haryana Police Forensic Expert."},
                      {"role": "user", "content": f"Analyze these transactions for fraud patterns and provide a 5-line summary in Hindi/English mix:\n{text_sample[:3000]}"}]
        )
        ai_summary = response.choices[0].message.content
    except:
        ai_summary = "AI Analysis failed (Check API Credit/Key)"

    return {
        "person": get_stats(5),
        "banks": get_stats(6),
        "locs": get_stats(0),
        "utr": get_stats(2),
        "ai_report": ai_summary,
        "owner": f"🛡️ HARYANA VIGIL-SCAN (AI ENABLED)\nRecords Analyzed: {len(df)}\nStatus: AI Forensic Complete"
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    try:
        res = forensic_ai_engine(temp)
        if not res: return {"status": "error", "message": "Grid mismatch"}
        
        # EXACT KEYS FOR ANDROID
        return {
            "status": "success",
            "data": {
                "most_frequent_person": res["person"],
                "top_banks": res["banks"],
                "top_locations": res["locs"],
                "top_utr": res["utr"],
                "suspicious": res["ai_report"], # AI Report ko 'suspicious' field mein bhej rahe hain
                "owner_info": res["owner"]
            }
        }
    except Exception as e: return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp): os.remove(temp)
