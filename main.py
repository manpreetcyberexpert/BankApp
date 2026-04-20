from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
from openai import OpenAI

app = FastAPI()

# Load API key safely
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("WARNING: OPENAI_API_KEY not found")

client = OpenAI(api_key=api_key) if api_key else None

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
                "report": "File could not be read. Please upload valid Excel/CSV."
            }

        if df is None or df.empty:
            return {
                "status": "success",
                "report": "No data found in file"
            }

        # Limit rows (important for speed + cost)
        df = df.head(150)

        data_preview = df.to_string()

        prompt = f"""
You are a professional financial forensic investigator.

Analyze the following transaction dataset and provide:

- Top 10 most involved accounts
- Top 10 banks
- Top accounts receiving money
- Top accounts sending money
- Top UTR transactions
- Top UPI IDs
- Peak transaction dates
- Peak transaction times
- Any suspicious patterns or fraud indicators

Data:
{data_preview}

Give a clear, structured report.
"""

        if not client:
            return {
                "status": "success",
                "report": "API key missing. Please configure OPENAI_API_KEY."
            }

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
