import pytest
from fastapi.testclient import TestClient
from google.genai import errors

import main

CLAUSE = "The Supplier may increase the fees at any time and by any amount."

ANALYSIS = {
    "isLegalDocument": True,
    "summary": "s",
    "documentType": "Price clause",
    "definitions": [],
    "risks": [{
        "description": "Unilateral price increases",
        "explanation": "The supplier can raise prices without limit.",
        "affectedParty": "Customer",
        "riskLevel": "high",
        "citation": "may increase the fees at any time",
    }],
}

LEGAL = [{"index": 0, "legalBasis": [
    {"section": "36 §", "quote": "Avtalsvillkor får jämkas", "explanation": "May be adjusted as unfair."},
]}]


@pytest.fixture
def api(monkeypatch):
    # A fresh, generous limiter per test so tests don't share request counts.
    monkeypatch.setattr(main, "limiter", main.RateLimiter(per_minute=100, per_day=100, global_per_day=100))
    return TestClient(main.app)


@pytest.fixture
def near_36():
    i = next(i for i, s in enumerate(main.legal_index.sections) if s.id == "36 §")
    return main.legal_index.vectors[i]


def test_full_pipeline(api, monkeypatch, fake_client, near_36):
    monkeypatch.setattr(main, "client", fake_client(ANALYSIS, LEGAL, embedding=near_36))

    result = api.post("/analyze", json={"text": CLAUSE}).json()["result"]

    risk = result["risks"][0]
    assert risk["citationVerified"] is True
    assert CLAUSE[risk["citationSpan"][0]:risk["citationSpan"][1]] == "may increase the fees at any time"
    assert result["legalCheckAvailable"] is True
    assert risk["legalBasis"][0]["section"] == "36 §"
    assert risk["legalBasis"][0]["quoteVerified"] is True


def test_made_up_citation_is_flagged(api, monkeypatch, fake_client, near_36):
    invented = {**ANALYSIS, "risks": [{**ANALYSIS["risks"][0], "citation": "fees may be doubled monthly"}]}
    monkeypatch.setattr(main, "client", fake_client(invented, LEGAL, embedding=near_36))

    risk = api.post("/analyze", json={"text": CLAUSE}).json()["result"]["risks"][0]

    assert risk["citationVerified"] is False
    assert risk["citationSpan"] is None


def test_not_legal_text(api, monkeypatch, fake_client):
    client = fake_client({"isLegalDocument": False, "reason": "A shopping list."})
    monkeypatch.setattr(main, "client", client)

    result = api.post("/analyze", json={"text": "milk, eggs"}).json()["result"]

    assert result == {"isLegalDocument": False, "reason": "A shopping list."}
    assert client.models.generate_calls == 1  # no legal check for non-legal text


@pytest.mark.parametrize("bad", [
    "not json",
    {**ANALYSIS, "risks": [{**ANALYSIS["risks"][0], "riskLevel": "severe"}]},
    {"isLegalDocument": True, "summary": "missing fields"},
])
def test_malformed_model_output_is_rejected(api, monkeypatch, fake_client, bad):
    monkeypatch.setattr(main, "client", fake_client(bad))
    assert api.post("/analyze", json={"text": CLAUSE}).json() == {"error": "The model returned an unexpected format."}


def test_legal_check_failure_still_returns_analysis(api, monkeypatch, fake_client, near_36):
    monkeypatch.setattr(main, "client", fake_client(ANALYSIS, "garbage", embedding=near_36))

    result = api.post("/analyze", json={"text": CLAUSE}).json()["result"]

    assert result["legalCheckAvailable"] is False
    assert result["risks"][0]["legalBasis"] is None
    assert result["risks"][0]["citationVerified"] is True


def _raise(error):
    def run(text):
        raise error
    return run


@pytest.mark.parametrize("error, message", [
    (errors.ClientError(429, {"error": {"code": 429, "message": "", "status": "RESOURCE_EXHAUSTED"}}), "rate limit"),
    (errors.ServerError(503, {"error": {"code": 503, "message": "", "status": "UNAVAILABLE"}}), "temporarily unavailable"),
])
def test_api_errors_become_friendly_messages(api, monkeypatch, error, message):
    monkeypatch.setattr(main, "run_analysis", _raise(error))
    assert message in api.post("/analyze", json={"text": CLAUSE}).json()["error"]


def test_too_long_text_is_rejected_without_calling_gemini(api, monkeypatch):
    monkeypatch.setattr(main, "run_analysis", _raise(AssertionError("should not be called")))
    assert "too long" in api.post("/analyze", json={"text": "x" * (main.MAX_TEXT_CHARS + 1)}).json()["error"]


def test_rate_limit_returns_429_without_calling_gemini(api, monkeypatch):
    monkeypatch.setattr(main, "limiter", main.RateLimiter(per_minute=1, per_day=10, global_per_day=10))
    monkeypatch.setattr(main, "run_analysis", lambda text: main.NotLegalAnalysis(isLegalDocument=False, reason="r"))
    assert api.post("/analyze", json={"text": CLAUSE}).status_code == 200

    monkeypatch.setattr(main, "run_analysis", _raise(AssertionError("should not be called")))
    response = api.post("/analyze", json={"text": CLAUSE})
    assert response.status_code == 429
    assert "per minute" in response.json()["error"]


def test_empty_text(api):
    assert api.post("/analyze", json={"text": "   "}).json() == {"error": "No text provided to analyze."}
