"""Shared test setup. No test calls the Gemini API: the client is replaced
with fakes wherever a test reaches code that would use it."""

import json
import os
from types import SimpleNamespace

import pytest

# main.py reads the key at import time; a dummy is enough because the real
# client is never used to make a request in tests.
os.environ.setdefault("GEMINI_API_KEY", "test-key")


class FakeModels:
    """Stands in for client.models: returns canned responses, in order, and a
    fixed embedding for every text."""

    def __init__(self, responses: list[str], embedding):
        self.responses = list(responses)
        self.embedding = embedding
        self.generate_calls = 0

    def generate_content(self, **kwargs):
        self.generate_calls += 1
        return SimpleNamespace(text=self.responses.pop(0))

    def embed_content(self, model, contents, config):
        return SimpleNamespace(embeddings=[SimpleNamespace(values=list(self.embedding)) for _ in contents])


@pytest.fixture
def fake_client():
    """fake_client(*responses, embedding=...) -> object usable as a genai.Client.
    Responses may be dicts/lists (sent as JSON) or raw strings."""
    def make(*responses, embedding=()):
        texts = [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in responses]
        return SimpleNamespace(models=FakeModels(texts, embedding))
    return make
