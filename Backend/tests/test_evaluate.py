import evaluate

CASES = [
    {
        "id": "a",
        "text": "1. Risky clause here. 2. Benign clause here. 3. Other text.",
        "isLegal": True,
        "risks": [{"anchor": "Risky clause here.", "level": "high", "sections": ["36 §"]}],
        "benign": ["Benign clause here."],
    },
    {"id": "b", "text": "milk, eggs", "isLegal": False},
]


def span(anchor: str) -> list[int]:
    start = CASES[0]["text"].index(anchor)
    return [start, start + len(anchor)]


def risk(anchor, level="high", sections=(), retrieved=()):
    return {
        "citationSpan": span(anchor) if anchor else None,
        "riskLevel": level,
        "description": "d",
        "citation": "c",
        "legalBasis": [{"section": s, "quoteVerified": True} for s in sections],
        "retrieved": list(retrieved),
    }


def run_with(outputs):
    return {"timestamp": "t", "model": "m", "embeddingModel": "e", "outputs": outputs}


def test_perfect_run():
    counts, notes = evaluate.score(CASES, run_with({
        "a": {"output": {"isLegalDocument": True, "legalCheckAvailable": True,
                         "risks": [risk("Risky clause here.", sections=["36 §"], retrieved=["36 §"])]}},
        "b": {"output": {"isLegalDocument": False, "reason": "r"}},
    }))
    assert counts["classified"] == 2
    assert (counts["found"], counts["expected"]) == (1, 1)
    assert (counts["predicted_tp"], counts["predicted"]) == (1, 1)
    assert counts["basis_hit"] == counts["retrieval_hit"] == 1
    assert notes == []


def test_counts_misses_false_alarms_and_wrong_sections():
    counts, notes = evaluate.score(CASES, run_with({
        "a": {"output": {"isLegalDocument": True, "legalCheckAvailable": True, "risks": [
            risk("Risky clause here.", level="medium", sections=["31 §"], retrieved=["36 §"]),
            risk("Benign clause here.", level="low"),
            risk("Other text."),
            risk(None),
        ]}},
        "b": {"output": {"isLegalDocument": True, "legalCheckAvailable": True, "risks": []}},
    }))
    assert counts["classified"] == 1
    assert (counts["predicted_tp"], counts["predicted"]) == (1, 4)
    assert counts["benign_flagged"] == counts["unlabelled"] == counts["unverified"] == 1
    assert (counts["level_exact"], counts["level_close"]) == (0, 1)
    assert (counts["basis_hit"], counts["retrieval_hit"]) == (0, 1)
    assert len(notes) == 6


def test_errors_are_counted_not_scored():
    counts, notes = evaluate.score(CASES, run_with({"a": {"error": "429 RESOURCE_EXHAUSTED"}}))
    assert (counts["cases"], counts["errors"], counts["expected"]) == (1, 1, 0)


def test_case_file_anchors_are_valid():
    cases = evaluate.load_cases()
    assert len(cases) == 23
