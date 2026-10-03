from types import SimpleNamespace

import numpy as np
import pytest

import legal_check
from legal_check import _section_id
from retrieval import LegalIndex

RISK = SimpleNamespace(description="One-sided non-compete", explanation="Too broad.", citation="shall not compete")


@pytest.fixture(scope="module")
def index():
    return LegalIndex.load()


def embedding_near(index, *section_ids):
    """A query vector whose nearest sections are the given ones."""
    rows = [i for i, s in enumerate(index.sections) if s.id in section_ids]
    return index.vectors[rows].sum(axis=0)


def test_committed_index_matches_the_statute(index):
    assert len(index.sections) == 41
    assert index.vectors.shape == (41, 768)
    assert np.allclose(np.linalg.norm(index.vectors, axis=1), 1, atol=1e-4)
    assert all(s.summary for s in index.sections)


def test_search_ranks_the_nearest_sections_first(index, fake_client):
    client = fake_client(embedding=embedding_near(index, "36 §", "38 §"))
    [hits] = index.search(client, ["q"], k=5)
    assert {s.id for s, _ in hits[:2]} == {"36 §", "38 §"}


@pytest.mark.parametrize("raw, expected", [
    ("36 §", "36 §"), ("36", "36 §"), ("36 § AvtL", "36 §"), ("§ 38", "38 §"), ("none", None),
])
def test_section_id_normalization(raw, expected):
    assert _section_id(raw) == expected


def test_keeps_only_grounded_sections_and_verifies_quotes(index, fake_client):
    answer = [{"index": 0, "legalBasis": [
        {"section": "36 § AvtL", "quote": "Avtalsvillkor får jämkas", "explanation": "ok"},
        {"section": "38", "quote": "this is not in the statute", "explanation": "bad quote"},
        {"section": "36 §", "quote": "Avtalsvillkor får jämkas", "explanation": "duplicate"},
        {"section": "99 §", "quote": "x", "explanation": "does not exist"},
    ]}, {"index": 5, "legalBasis": []}]
    client = fake_client(answer, embedding=embedding_near(index, "36 §", "38 §"))

    [bases] = legal_check.assess(client, "model", index, [RISK])

    assert [(b.section, b.quoteVerified) for b in bases] == [("36 §", True), ("38 §", False)]
    assert bases[0].url == "https://lagen.nu/1915:218#P36"


def test_drops_sections_the_model_was_not_shown(index, fake_client):
    shown = embedding_near(index, "38 §")
    [hits] = index.search(fake_client(embedding=shown), ["q"], k=legal_check.CANDIDATES_PER_RISK)
    not_shown = next(s.id for s in index.sections if s.id not in {h.id for h, _ in hits})
    answer = [{"index": 0, "legalBasis": [{"section": not_shown, "quote": "x", "explanation": "x"}]}]

    [bases] = legal_check.assess(fake_client(answer, embedding=shown), "model", index, [RISK])

    assert bases == []


def test_no_risks_means_no_api_calls(index, fake_client):
    client = fake_client()
    assert legal_check.assess(client, "model", index, []) == []
    assert client.models.generate_calls == 0
