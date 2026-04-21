from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import fitz
import json
from openai import OpenAI

app = FastAPI()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "alive"}

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
       
        if file.filename.lower().endswith(".pdf"):
            doc = fitz.open(temp_path)
           
            sample_text = "".join([page.get_text() for page in doc.pages[:10]])
            doc.close()
        elif file.filename.lower().endswith((".csv", ".xls", ".xlsx")):
            df = pd.read_csv(temp_path) if file.filename.endswith(".csv") else pd.read_excel(temp_path)
            sample_text = df.head(300).to_string() # 300 rows for AI
        else:
            return {"status": "error", "message": "Format not supported"}

        
        prompt = f"""
        You are a Haryana Police Cybercrime Forensic Expert.
        Analyze this bank data and return a JSON object with these EXACT keys.
        Value must be a SINGLE STRING with newline characters (\n) for lists.

        Required JSON Structure:
        {{
          "most_frequent_person": "List top 10 beneficiary names with count",
          "top_banks": "List top 10 banks and account numbers",
          "top_locations": "List identified ATM/POS locations and IDs",
          "top_utr": "List top 10 12-digit UTR/Ref numbers",
          "suspicious": "5-line fraud pattern analysis in Hindi/English mix",
          "owner_info": "🛡️ HARYANA VIGIL-SCAN: AI SCAN COMPLETE"
        }}

        Rules: 
        - Ignore junk like AM, PM, 12/, 05. 
        - Only include valid financial data.
        - Data must be formatted as a readable string list.

        Data: {sample_text[:5000]}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional financial fraud investigator."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

    
        ai_output = json.loads(response.choices[0].message.content)

        return {
            "status": "success",
            "data": ai_data # Android App accepts this structure
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
