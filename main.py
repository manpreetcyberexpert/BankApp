from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# SAFE ANALYSIS (NO CRASH)
# -------------------------------
def safe_analyze(df):
    result = {
        "most_frequent_person": {},
        "top_banks": {},
        "top_locations": {},
        "top_utr": {}
    }

    try:
        df.columns = [str(c).upper() for c in df.columns]

        # Convert all to string safely
        df = df.astype(str)

        # Combine all text (for messy files)
        full_text = df.apply(lambda row: " ".join(row.values), axis=1)

        # ---------------- UTR ----------------
        utr = full_text.str.extract(r'([A-Z0-9]{12,})')[0]
        utr = utr.dropna()
        result["top_utr"] = utr.value_counts().head(10).to_dict()

        # ---------------- ACCOUNTS ----------------
        acc = full_text.str.extract(r'(\d{9,})')[0]
        acc = acc.dropna()
        result["most_frequent_person"] = acc.value_counts().head(10).to_dict()

        # ---------------- LOCATIONS (same as accounts sent) ----------------
        result["top_locations"] = result["most_frequent_person"]

        # ---------------- BANKS (basic keywords) ----------------
        banks = full_text.str.extract(
            r'(SBI|HDFC|ICICI|AXIS|PNB|KOTAK|YES BANK|BOB|UNION BANK)'
        )[0]
        banks = banks.dropna()
        result["top_banks"] = banks.value_counts().head(10).to_dict()

    except Exception as e:
        result["error"] = str(e)

    return result


# -------------------------------
# API
# -------------------------------
@app.get("/")
def home():
    return {"status": "alive"}


@app.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):

    try:
        # LIMIT FILE SIZE (prevent crash)
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:  # 5MB limit
            return {
                "status": "success",
                "data": {"error": "File too large"}
            }

        # Try reading file safely
        try:
            if file.filename.endswith(".csv"):
                df = pd.read_csv(pd.io.common.BytesIO(content))
            else:
                df = pd.read_excel(pd.io.common.BytesIO(content))
        except:
            return {
                "status": "success",
                "data": {"error": "File format not supported or corrupted"}
            }

        if df is None or df.empty:
            return {
                "status": "success",
                "data": {"error": "No data found in file"}
            }

        result = safe_analyze(df)

        return {
            "status": "success",
            "data": result
        }

    except Exception as e:
        return {
            "status": "success",
            "data": {"error": str(e)}
        }
