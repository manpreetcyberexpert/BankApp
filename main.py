from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz, os, json, pandas as pd
from openai import OpenAI

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


client = OpenAI(api_key="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")

@app.get("/")
def home(): return {"status": "alive"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    temp = f"temp_{file.filename}"
    with open(temp, "wb") as f: f.write(await file.read())
    
    try:
        # 1. PDF Forensic Extraction
        doc = fitz.open(temp)
       
        text = "".join([page.get_text() for page in doc[:15]]) 
        doc.close()

        # 2. ChatGPT Analysis (Fixed Path)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Haryana Police Forensic Analyst. Extract Top 10 Names, Banks, Locations, and UTRs from the provided data. Return ONLY a JSON object with keys: names, banks, locations, utrs. Format values as bullet points string."},
                {"role": "user", "content": text[:12000]} # Increase limit for better analysis
            ],
            response_format={ "type": "json_object" }
        )
        
      
        ai_data = json.loads(response.choices[0].message.content)

        return {
            "status": "success",
            "data": {
                "most_frequent_person": ai_data.get("names", "No names found"),
                "top_banks": ai_data.get("banks", "No banks found"),
                "top_locations": ai_data.get("locations", "No locations found"),
                "top_utr": ai_data.get("utrs", "No UTRs found"),
                "suspicious": "AI Case Analysis: Completed",
                "owner_info": f"⚖️ HARYANA VIGIL-SCAN (AI MODE)\nCase ID: FIU-{os.urandom(2).hex().upper()}"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Forensic Engine Error: {str(e)}"}
    finally:
        if os.path.exists(temp): os.remove(temp)
