import json
import os

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.api_core.exceptions import ResourceExhausted
from pydantic import BaseModel

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Same contract as frontend/app/api/analyze/route.ts, so both backends
# return a shape app/analyze/page.tsx can render without changes.
SYSTEM_PROMPT = """You are a legal document analyzer. You will receive a piece of text and must return your analysis as a single valid JSON object — no markdown, no code fences, no text outside the JSON.

First, determine whether the input is a legal document or clause at all. If it is NOT legal text (e.g. a grocery list, casual conversation, unrelated content), return only:
{
  "isLegalDocument": false,
  "reason": "<one short sentence explaining why this doesn't appear to be legal text>"
}

If it IS legal text, return exactly this structure:

{
  "isLegalDocument": true,
  "summary": "<a 3-sentence summary of the document>",
  "documentType": "<the type of document or clause, e.g. 'Confidentiality clause', 'Termination clause', 'Employment contract'. If uncertain, say 'Unclear' rather than guessing.>",
  "definitions": [
    {
      "term": "<exact term as it appears in the document>",
      "definition": "<the definition, stated explicitly or clearly supported by the document's wording>"
    }
  ],
  "risks": [
    {
      "description": "<what the risk is>",
      "explanation": "<why this is risky, in one or two sentences>",
      "affectedParty": "<who this risk applies to>",
      "riskLevel": "low" | "medium" | "high",
      "citation": "<the exact paragraph, section title, or keyword phrase from the document where this risk was found>"
    }
  ]
}

Rules:
- Return definitions only when they are explicitly stated or clearly supported by the document. Do not invent or infer a legal definition that is not supported by the text.
- If no such definitions exist, return "definitions": [] (empty array).
- If no risks are found, return "risks": [] (empty array) — do not invent one.
- Do not state anything in any field that is not actually present or directly implied in the document. Do not provide legal advice or conclusions beyond what the text says.
- "riskLevel" must be exactly one of: "low", "medium", "high" — no other values.
- Output must be valid JSON and nothing else — no explanations, no markdown formatting, no surrounding text."""

model = genai.GenerativeModel(
    "gemini-3.6-flash",
    system_instruction=SYSTEM_PROMPT,
    generation_config={"response_mime_type": "application/json"},
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # byt till din frontend-domän i produktion
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
    if not request.text.strip():
        return {"error": "No text provided to analyze."}

    try:
        response = model.generate_content(
            request.text, request_options={"retry": None}
        )
    except ResourceExhausted:
        return {"error": "Gemini API rate limit reached. Wait a bit and try again."}

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError:
        return {"error": "The model returned an unexpected format."}

    return {"result": result}
