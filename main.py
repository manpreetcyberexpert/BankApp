from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import fitz
import json
from openai import OpenAI

app = FastAPI()

# Make sure OPENAI_API_KEY is set in Render Environment Variables
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

def clean_text(text):
    bad_words = ["AM", "PM", "NA", "N/A", "NULL", "0", "05", "12/"]
    for word in bad_words:
        text = text.replace(word, "")
    return text

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        # FILE READ LOGIC
        if file.filename.lower().endswith(".pdf"):
            doc = fitz.open(temp_path)
            # 4000 rows ke liye pehle 5-10 pages ka sample kaafi hai AI ke liye
            sample_text = "".join([page.get_text() for page in doc.pages[:10]])
            doc.close()
        elif file.filename.lower().endswith((".csv", ".xls", ".xlsx")):
            df = pd.read_csv(temp_path) if file.filename.endswith(".csv") else pd.read_excel(temp_path)
            sample_text = df.head(200).to_string()
        else:
            return {"status": "error", "message": "Unsupported Format"}

        sample_text = clean_text(sample_text)

        # AI FORENSIC PROMPT
        prompt = f"""
        You are a Haryana Police cybercrime financial investigator.
        Return STRICT JSON ONLY:
        {{
          "most_frequent_person": "Top 10 real names/accounts here",
          "top_banks": "Top 10 banks used here",
          "top_locations": "Identify ATM/POS locations here",
          "top_utr": "List 12-digit UTR/Ref numbers here",
          "suspicious": "5-line fraud pattern analysis here",
          "owner_info": "🛡️ HARYANA VIGIL-SCAN: AI INVESTIGATION COMPLETE"
        }}
        Rules: Ignore AM, PM, 05, 12/. Extract ONLY real financial entities.
        Data: {sample_text[:4000]}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini", # CORRECTED MODEL NAME
            messages=[
                {"role": "system", "content": "Expert financial fraud investigator"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        # Response Parsing
        ai_output = response.choices[0].message.content
        ai_data = json.loads(ai_output)

        return {
            "status": "success",
            "data": ai_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
