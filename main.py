from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

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


# -------------------------------
# CLEAN DATA
# -------------------------------
def clean_df(df):
    df = df.fillna("")
    df = df.astype(str)
    return df


# -------------------------------
# MAIN API
# -------------------------------
@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    try:
        # Read file
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)

        if df is None or df.empty:
            return {"status": "error", "message": "Empty file"}

        df = clean_df(df)

        # Reduce size for AI
        sample = df.head(200).to_string()

        # 🔥 VERY IMPORTANT PROMPT
        prompt = f"""
You are a cybercrime financial investigator.

Analyze the transaction data and return STRICT JSON format:

{{
  "top_accounts": [],
  "top_banks": [],
  "top_received": [],
  "top_sent": [],
  "top_utr": [],
  "top_upi": [],
  "peak_dates": [],
  "peak_times": [],
  "suspicious_summary": ""
}}

Rules:
- Ignore junk values like PM, AM, 05, 12/
- Only include real names, accounts, banks
- Return top 10 in each category
- Use clean readable values
- Detect actual financial patterns

Data:
{sample}
"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Expert financial fraud analyst"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        ai_output = response.choices[0].message.content

        return {
            "status": "success",
            "data": ai_output   # JSON string
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
