from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
import os

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-flash-latest")

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], #  byt till din frontend-domän i produktion
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    text: str

@app.get("/")
def home():
    return {"message": "Hello from FastAPI"}

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    prompt = f"""Analysera denna avtalsklausul. Svara ENDAST i JSON med nycklarna
documentType, riskLevel, summary:

{request.text}"""
    response = model.generate_content(prompt)
    return {"result": response.text}