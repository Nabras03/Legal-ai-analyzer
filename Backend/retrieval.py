"""Semantic search over statute sections.

The corpus is small (Avtalslagen has 41 sections), so the index is a JSON file
of precomputed embeddings searched with plain cosine similarity. That keeps
the backend free of a vector-database dependency; `LegalIndex` is the only
thing that would change if the corpus grew enough to need one.
"""

import json
from pathlib import Path

import numpy as np
from google import genai
from google.genai import types

from legal_sources import Section

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
INDEX_PATH = Path(__file__).parent / "legal_index" / "avtalslagen.json"


def embed(client: genai.Client, texts: list[str], task_type: str) -> np.ndarray:
    """Embed texts and return unit-length row vectors."""
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIM),
    )
    vectors = np.array([e.values for e in response.embeddings], dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def section_document(section: Section) -> str:
    """The text embedded for a section.

    The statute is written in 1915 Swedish, while queries are modern English
    or Swedish; the plain-language summary bridges that vocabulary gap.
    """
    return f"{section.citation()}, {section.chapter}\n{section.summary}\n{section.text}"


class LegalIndex:
    def __init__(self, sections: list[Section], vectors: np.ndarray):
        self.sections = sections
        self.vectors = vectors

    @classmethod
    def build(cls, client: genai.Client, sections: list[Section]) -> "LegalIndex":
        vectors = embed(client, [section_document(s) for s in sections], "RETRIEVAL_DOCUMENT")
        return cls(sections, vectors)

    def save(self, path: Path = INDEX_PATH) -> None:
        path.parent.mkdir(exist_ok=True)
        data = {
            "embeddingModel": EMBEDDING_MODEL,
            "sections": [
                {**s.to_dict(), "embedding": [round(float(x), 6) for x in v]}
                for s, v in zip(self.sections, self.vectors)
            ],
        }
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> "LegalIndex":
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["embeddingModel"] != EMBEDDING_MODEL:
            raise RuntimeError(f"{path} was built with {data['embeddingModel']}; rebuild it with build_index.py")
        sections = [Section(**{k: v for k, v in s.items() if k != "embedding"}) for s in data["sections"]]
        vectors = np.array([s["embedding"] for s in data["sections"]], dtype=np.float32)
        return cls(sections, vectors)

    def search(self, client: genai.Client, queries: list[str], k: int = 3) -> list[list[tuple[Section, float]]]:
        """Return the k most similar sections, with scores, for each query."""
        scores = embed(client, queries, "RETRIEVAL_QUERY") @ self.vectors.T
        results = []
        for row in scores:
            top = np.argsort(-row)[:k]
            results.append([(self.sections[i], float(row[i])) for i in top])
        return results
