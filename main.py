from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

# Safe import (prevents crash if openai not installed properly)
try:
    from openai import OpenAI
except:
    OpenAI = None

app = FastAPI()

# Load API key safely
api_key = os.getenv("OPENAI_API_KEY")

# Initialize client safely
client = OpenAI(api_key=api_key) if OpenAI and api_key else None

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
    try:
        # Read file safely
        try:
            if file.filename.endswith(".csv"):
                df = pd.read_csv(file.file)
            else:
                df = pd.read_excel(file.file)
        except Exception:
            return {
                "status": "success",
                "report": "Invalid file. Please upload Excel or CSV."
            }

        if df is None or df.empty:
            return {
                "status": "success",
                "report": "No data found in file"
            }

        # Limit rows (important for speed + cost)
        df = df.head(150)

        data_preview = df.to_string()

        # If OpenAI not available
        if not client:
            return {
                "status": "success",
                "report": "AI service not configured. Please set OPENAI_API_KEY."
            }

        prompt = f"""
You are a professional financial forensic investigator.

Analyze the following bank transaction data and provide:

1. Top 10 most involved accounts
2. Top 10 banks
3. Top accounts receiving money
4. Top accounts sending money
5. Top UTR transactions
6. Top UPI IDs
7. Peak transaction dates
8. Peak transaction times
9. Suspicious patterns or fraud indicators

Data:
{data_preview}

Give a clean structured report.
"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are an expert financial fraud analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        report = response.choices[0].message.content

        return {
            "status": "success",
            "report": report
        }

    except Exception as e:
        return {
            "status": "success",
            "report": f"Error: {str(e)}"
        }
