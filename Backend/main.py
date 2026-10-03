import json
import os
from typing import Annotated, Literal, Union

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

import legal_check
from citations import find_citation
from legal_check import LegalBasis
from retrieval import INDEX_PATH, LegalIndex

load_dotenv()
# Gemini's free tier often answers 503 "high demand" for a few seconds at a
# time; retrying with backoff hides most of those. 429 (quota used up) is not
# retried, since waiting seconds won't help.
client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=4, initial_delay=1.0, max_delay=8.0, http_status_codes=[503]
        )
    ),
)

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

# Flash-Lite has a far higher free-tier daily quota than Flash.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
ANALYZE_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    response_mime_type="application/json",
)

# Built by build_index.py. Without it the app still works, just without
# legal-basis checks (build_index.py itself imports this module).
legal_index = LegalIndex.load() if INDEX_PATH.exists() else None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    # Comma-separated, e.g. "https://my-app.vercel.app"; set in production.
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# Roughly 8-10 pages. Keeps a public demo from spending quota on huge inputs.
MAX_TEXT_CHARS = 20_000


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
    # Sections of Avtalslagen that may apply; None if the check didn't run.
    legalBasis: list[LegalBasis] | None = None


class LegalAnalysis(BaseModel):
    isLegalDocument: Literal[True]
    summary: str
    documentType: str
    definitions: list[Definition]
    risks: list[Risk]
    legalCheckAvailable: bool = False


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


def add_legal_basis(analysis: LegalAnalysis) -> None:
    """Attach Avtalslagen sections to each risk. Best effort: if Gemini is
    unavailable or answers in the wrong shape, the analysis is still returned,
    just flagged as not checked."""
    if legal_index is None:
        return
    try:
        bases = legal_check.assess(client, MODEL, legal_index, analysis.risks)
    except (errors.APIError, ValidationError) as e:
        print(f"Legal basis check failed: {e}")
        return
    for risk, basis in zip(analysis.risks, bases):
        risk.legalBasis = basis
    analysis.legalCheckAvailable = True


@app.get("/")
def home():
    return {"message": "Hello from FastAPI"}


def run_analysis(text: str) -> LegalAnalysis | NotLegalAnalysis:
    """The full pipeline: analyze, verify citations, add legal basis.

    Raises google.genai.errors.APIError on API failures and ValueError if the
    model's answer doesn't match the schema. Used by the endpoint and by
    evaluate.py.
    """
    response = client.models.generate_content(model=MODEL, contents=text, config=ANALYZE_CONFIG)
    try:
        result = analysis_adapter.validate_python(json.loads(response.text or ""))
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError("The model returned an unexpected format.") from e

    if isinstance(result, LegalAnalysis):
        verify_citations(result, text)
        add_legal_basis(result)
    return result


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    if not request.text.strip():
        return {"error": "No text provided to analyze."}
    if len(request.text) > MAX_TEXT_CHARS:
        return {"error": f"Text is too long ({len(request.text):,} characters). The limit is {MAX_TEXT_CHARS:,}."}

    try:
        result = run_analysis(request.text)
    except errors.ClientError as e:
        if e.code == 429:
            return {"error": "Gemini API rate limit reached. Wait a bit and try again."}
        raise
    except errors.ServerError:
        return {"error": "Gemini is temporarily unavailable. Try again in a moment."}
    except ValueError as e:
        return {"error": str(e)}

    return {"result": result.model_dump()}
