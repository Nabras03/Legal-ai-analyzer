"""Grounds each flagged risk in the text of Avtalslagen (retrieval-augmented).

For every risk the most similar statute sections are retrieved, then one
model call judges, for all risks at once, which of those sections actually
apply. The answer is checked in code the same way contract citations are:
a section the model names must be one it was shown for that risk, and its
quote must appear in that section's text.
"""

import json
import re
from typing import Protocol

from google import genai
from google.genai import types
from pydantic import BaseModel, TypeAdapter

from citations import find_citation
from retrieval import LegalIndex

CANDIDATES_PER_RISK = 5

LEGAL_PROMPT = """You assess risks found in a contract against sections of the Swedish Contracts Act (Avtalslagen, 1915:218).

You will receive JSON: a list of risks, each with an "index", a description of the risk, the clause it was found in, and "candidates": statute sections that a search found to be possibly related.

For each risk, decide which candidate sections genuinely apply to it. Many risks have no directly applicable section in this statute — then return an empty list. Never force a connection: a section only applies if its content actually bears on this kind of term or situation.

Return only a JSON array, one entry per risk:
[
  {
    "index": <the risk's index>,
    "legalBasis": [
      {
        "section": "<the section id exactly as given, e.g. '36 §'>",
        "quote": "<a short verbatim quote, copied character for character from that section's text, showing why it applies>",
        "explanation": "<one or two sentences in English on how the section could apply to this term>"
      }
    ]
  }
]

Rules:
- Only use sections from that risk's own "candidates". Do not cite any other law or section.
- Quotes must be copied exactly from the section text — do not modernize, translate or correct the old Swedish. Every quote is checked against the statute.
- Use cautious language ("may", "could be adjusted under"). Do not state how a court would rule and do not give legal advice."""


class LegalBasis(BaseModel):
    section: str
    law: str
    quote: str
    explanation: str
    url: str
    quoteVerified: bool


class RiskLike(Protocol):
    description: str
    explanation: str
    citation: str


class _Claim(BaseModel):
    section: str
    quote: str
    explanation: str


class _Assessment(BaseModel):
    index: int
    legalBasis: list[_Claim]


_assessments = TypeAdapter(list[_Assessment])
_SECTION_NUMBER = re.compile(r"\d+")


def _section_id(raw: str) -> str | None:
    """Normalize "36", "36 §" or "36 § AvtL" to "36 §"."""
    m = _SECTION_NUMBER.search(raw)
    return f"{m.group(0)} §" if m else None


def assess(client: genai.Client, model: str, index: LegalIndex, risks: list[RiskLike]) -> list[list[LegalBasis]]:
    """Return the verified legal basis for each risk, in the same order."""
    if not risks:
        return []

    queries = [f"{r.description}. {r.explanation} Clause: {r.citation}" for r in risks]
    candidates = index.search(client, queries, k=CANDIDATES_PER_RISK)

    payload = [
        {
            "index": i,
            "risk": r.description,
            "why": r.explanation,
            "clause": r.citation,
            "candidates": [{"section": s.id, "text": s.text} for s, _ in hits],
        }
        for i, (r, hits) in enumerate(zip(risks, candidates))
    ]
    response = client.models.generate_content(
        model=model,
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=LEGAL_PROMPT, response_mime_type="application/json"
        ),
    )
    assessments = _assessments.validate_json(response.text or "")

    results: list[list[LegalBasis]] = [[] for _ in risks]
    for a in assessments:
        if not 0 <= a.index < len(risks):
            continue
        shown = {s.id: s for s, _ in candidates[a.index]}
        seen: set[str] = set()
        for claim in a.legalBasis:
            section = shown.get(_section_id(claim.section) or "")
            # A section the model wasn't shown for this risk is not grounded
            # in retrieval, so it is dropped rather than displayed.
            if section is None or section.id in seen:
                continue
            seen.add(section.id)
            results[a.index].append(LegalBasis(
                section=section.id,
                law=section.law,
                quote=claim.quote,
                explanation=claim.explanation,
                url=section.url,
                quoteVerified=find_citation(section.text, claim.quote) is not None,
            ))
    return results
