import json
import os
from typing import Annotated, Literal, Union

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from citations import find_citation

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# The JSON contract app/analyze/page.tsx renders. The Pydantic models below
# mirror it, so a malformed model response is rejected here, not in the UI.
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
      "citation": "<a short verbatim quote, copied character for character from the document, showing where this risk was found>"
    }
  ]
}

Rules:
- Return definitions only when they are explicitly stated or clearly supported by the document. Do not invent or infer a legal definition that is not supported by the text.
- If no such definitions exist, return "definitions": [] (empty array).
- If no risks are found, return "risks": [] (empty array) — do not invent one.
- Do not state anything in any field that is not actually present or directly implied in the document. Do not provide legal advice or conclusions beyond what the text says.
- "citation" must be copied exactly from the document — do not paraphrase, summarize, translate or correct it. Every citation is checked against the original text.
- "riskLevel" must be exactly one of: "low", "medium", "high" — no other values.
- Output must be valid JSON and nothing else — no explanations, no markdown formatting, no surrounding text."""

MODEL = "gemini-3.6-flash"
ANALYZE_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    response_mime_type="application/json",
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


class Definition(BaseModel):
    term: str
    definition: str


class Risk(BaseModel):
    description: str
    explanation: str
    affectedParty: str
    riskLevel: Literal["low", "medium", "high"]
    citation: str
    # Filled in by us, not the model: where the citation sits in the input.
    citationVerified: bool = False
    citationSpan: tuple[int, int] | None = None


class LegalAnalysis(BaseModel):
    isLegalDocument: Literal[True]
    summary: str
    documentType: str
    definitions: list[Definition]
    risks: list[Risk]


class NotLegalAnalysis(BaseModel):
    isLegalDocument: Literal[False]
    reason: str


analysis_adapter = TypeAdapter(
    Annotated[Union[LegalAnalysis, NotLegalAnalysis], Field(discriminator="isLegalDocument")]
)


def verify_citations(analysis: LegalAnalysis, document: str) -> None:
    """Flag each risk whose citation can't be found in the analyzed text."""
    for risk in analysis.risks:
        risk.citationSpan = find_citation(document, risk.citation)
        risk.citationVerified = risk.citationSpan is not None


@app.get("/")
def home():
    return {"message": "Hello from FastAPI"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    if not request.text.strip():
        return {"error": "No text provided to analyze."}

    try:
        response = client.models.generate_content(
            model=MODEL, contents=request.text, config=ANALYZE_CONFIG
        )
    except errors.ClientError as e:
        if e.code == 429:
            return {"error": "Gemini API rate limit reached. Wait a bit and try again."}
        raise
    except errors.ServerError:
        return {"error": "Gemini is temporarily unavailable. Try again in a moment."}

    try:
        result = analysis_adapter.validate_python(json.loads(response.text or ""))
    except (json.JSONDecodeError, ValidationError):
        return {"error": "The model returned an unexpected format."}

    if isinstance(result, LegalAnalysis):
        verify_citations(result, request.text)

    return {"result": result.model_dump()}
