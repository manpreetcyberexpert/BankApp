from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Server is Live!"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    return {
        "status": "success",
        "data": {
            "most_frequent_person": "Server Connected Successfully!",
            "top_banks": "HDFC, SBI, ICICI",
            "top_locations": "Mumbai, Delhi",
            "top_utr": "UTR123456789",
            "suspicious": "Clean"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
