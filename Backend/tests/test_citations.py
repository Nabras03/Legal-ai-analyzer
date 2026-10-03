import pytest

from citations import find_citation

DOC = (
    "Section 4.2  The Contractor shall indemnify\n the Client for “any and all” losses, "
    "including the Client's own negligence."
)


def quoted(citation: str) -> str | None:
    span = find_citation(DOC, citation)
    return DOC[span[0]:span[1]] if span else None


@pytest.mark.parametrize("citation", [
    "The Contractor shall indemnify the Client",
    "the contractor shall INDEMNIFY the client",                # case
    "The   Contractor shall\tindemnify the Client",             # whitespace
    "any and all losses",                                       # quotes dropped
    'for "any and all" losses',                                 # straight vs curly quotes
    '"including the Client’s own negligence."',            # wrapping quotes, apostrophe, trailing dot
    "The Contractor shall indemnify ... own negligence",        # elided middle
    "The Contractor shall indemnify … own negligence",     # unicode ellipsis
])
def test_finds_citations_that_differ_only_in_form(citation):
    assert find_citation(DOC, citation) is not None


@pytest.mark.parametrize("citation", [
    "The Contractor must indemnify the Client",   # paraphrase
    "unlimited liability",                        # invented
    "own negligence ... Contractor shall",        # fragments out of order
    "",
    '"..."',
])
def test_rejects_citations_with_different_words(citation):
    assert find_citation(DOC, citation) is None


def test_span_maps_back_to_original_text():
    assert quoted("the client for any and all losses") == "the Client for “any and all” losses"


def test_elided_citation_spans_all_fragments():
    assert quoted("The Contractor ... own negligence") == DOC[DOC.index("The Contractor"):DOC.index(".", 50)]
