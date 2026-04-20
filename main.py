import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
from datetime import datetime

app = FastAPI(title="Bank Investigator API")

# Allow Frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class BankAnalyser:
    def __init__(self, df):
        self.df = df
        self.clean_data()

    def clean_data(self):
        # Standardize column names (lowercase and no spaces)
        self.df.columns = [str(c).lower().strip().replace(" ", "_") for c in self.df.columns]
        
        # Convert Date & Amount to proper formats
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
        if 'amount' in self.df.columns:
            self.df['amount'] = pd.to_numeric(self.df['amount'], errors='coerce').fillna(0)

    def get_top_insights(self):
        insights = {}

        # 1. Top 10 Involved Accounts (Count)
        if 'account_number' in self.df.columns:
            insights['top_involved_accounts'] = self.df['account_number'].value_counts().head(10).to_dict()

        # 2. Top 10 Banks
        if 'bank_name' in self.df.columns:
            insights['top_banks'] = self.df['bank_name'].value_counts().head(10).to_dict()

        # 3. Money Received (Sum of Amount)
        if 'account_number' in self.df.columns and 'amount' in self.df.columns:
            insights['top_receivers_value'] = self.df.groupby('account_number')['amount'].sum().nlargest(10).to_dict()

        # 4. Top UTR Transactions
        if 'utr' in self.df.columns:
            insights['top_utr_repeated'] = self.df['utr'].value_counts().head(10).to_dict()

        # 5. Top UPI IDs (if available in remarks/description)
        # Simple extraction logic from description
        if 'description' in self.df.columns:
            insights['top_upi_mentions'] = self.df['description'].str.extract(r'([\w\.-]+@[\w\.-]+)')[0].value_counts().head(10).to_dict()

        # 6. Peak Transaction Dates
        if 'date' in self.df.columns:
            insights['peak_dates'] = self.df['date'].dt.date.value_counts().head(10).to_dict()

        return insights

@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    # Check file extension
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload Excel or CSV.")

    contents = await file.read()
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
            
        analyser = BankAnalyser(df)
        results = analyser.get_top_insights()
        
        return {
            "filename": file.filename,
            "total_transactions": len(df),
            "insights": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/")
def home():
    return {"message": "Bank Investigator Backend is Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
