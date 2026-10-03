"""Builds legal_index/avtalslagen.json from legal_sources/avtalslagen.txt.

Run once, and again only when the source text or embedding model changes:

    python build_index.py

Each section first gets a short plain-language summary (one model call for
the whole statute), then summary + text are embedded together. See
retrieval.section_document for why.
"""

import json

from google.genai import types
from pydantic import BaseModel, TypeAdapter

from legal_sources import Section, load_avtalslagen
from main import MODEL, client
from retrieval import INDEX_PATH, LegalIndex

SUMMARY_PROMPT = """You will receive the sections of a Swedish statute as JSON. For each section, write a summary of 2-3 sentences: first in plain modern English, then in plain modern Swedish. Describe what situations and contract terms the section covers, using the words a contract reader would use today (e.g. "unfair terms", "non-compete", "duress", "fraud", "authority to sign"). Do not add anything the section does not say.

Return only a JSON array: [{"id": "<section id exactly as given>", "summary": "<summary>"}]"""


class Summary(BaseModel):
    id: str
    summary: str


def summarize(sections: list[Section]) -> dict[str, str]:
    payload = json.dumps([{"id": s.id, "text": s.text} for s in sections], ensure_ascii=False)
    response = client.models.generate_content(
        model=MODEL,
        contents=payload,
        config=types.GenerateContentConfig(
            system_instruction=SUMMARY_PROMPT, response_mime_type="application/json"
        ),
    )
    summaries = TypeAdapter(list[Summary]).validate_json(response.text or "")
    by_id = {s.id: s.summary for s in summaries}
    missing = {s.id for s in sections} - by_id.keys()
    if missing:
        raise RuntimeError(f"Model returned no summary for: {sorted(missing)}")
    return by_id


if __name__ == "__main__":
    sections = load_avtalslagen()
    summaries = summarize(sections)
    for s in sections:
        s.summary = summaries[s.id]
    LegalIndex.build(client, sections).save()
    print(f"Indexed {len(sections)} sections -> {INDEX_PATH}")
