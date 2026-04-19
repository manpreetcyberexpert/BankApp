from fastapi import FastAPI, UploadFile, File
import pandas as pd
import tabula
import os

app = FastAPI()

@app.post("/analyze")
async def analyze_statement(file: UploadFile = File(...)):
    # File ko temporary save karna
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        # 1. PDF se Data nikalna
        # Note: Banking PDF ka structure complex hota hai, 'pages' all rakha hai
        df_list = tabula.read_pdf(temp_path, pages='all', multiple_tables=True)
        df = pd.concat(df_list, ignore_index=True)

        # 2. Data Cleaning (Yahan columns ke naam bank ke hisab se change karne pad sakte hain)
        # Maan lete hain columns hain: 'Date', 'Description', 'Amount', 'Type' (CR/DR)
        
        # 3. Investigation Logic
        analysis = {
            "top_10_transactions": df.nlargest(10, 'Amount').to_dict(orient='records'),
            "top_10_locations": df['Description'].str.extract(r'([A-Z]{3,})')[0].value_counts().head(10).to_dict(),
            "top_10_banks": df['Description'].str.extract(r'(HDFC|ICICI|SBI|AXIS|PNB)')[0].value_counts().head(10).to_dict(),
            "suspicious": df[df['Amount'] > 50000].to_dict(orient='records'), # Example logic
            "most_frequent_person": df['Description'].value_counts().idxmax(),
        }

        return {"status": "success", "data": analysis}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
