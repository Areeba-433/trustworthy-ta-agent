from fastapi import FastAPI

app = FastAPI(title="Trustworthy TA Agent")

@app.get("/")
def root():
    return {"status": "Trustworthy TA Agent backend running"}
