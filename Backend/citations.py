"""Checks that the quotes the model cites actually appear in the analyzed text.

The model is asked for verbatim quotes, but it can paraphrase, fix typos or
invent text outright. Matching is forgiving about things that don't change
meaning (case, whitespace, double quotes, an elided "...") and strict about the
words themselves.
"""

import re

# Double quotes are dropped entirely: the model often adds or removes them
# around a phrase, and they never change what a clause says.
_CHAR_MAP = str.maketrans({
    '"': None, "\u201c": None, "\u201d": None, "\u201e": None,
    "\u2018": "'", "\u2019": "'",
    "\u00a0": " ",
})
_ELLIPSIS = re.compile(r"\s*(?:\.{3}|\u2026)\s*")
_WRAPPING = "\"'\u201c\u201d\u201e\u2018\u2019 .,;:"


def _normalize(text: str) -> tuple[str, list[int]]:
    """Lowercase, unify quotes and collapse whitespace.

    Also returns, for each character of the normalized string, its index in
    the original text, so matches can be mapped back to original offsets.
    """
    chars: list[str] = []
    index: list[int] = []
    prev_space = True  # drops leading whitespace
    for i, ch in enumerate(text):
        ch = ch.translate(_CHAR_MAP)
        if not ch:
            continue
        if ch.isspace():
            if prev_space:
                continue
            ch = " "
            prev_space = True
        else:
            prev_space = False
        chars.append(ch.lower())
        index.append(i)
    if chars and chars[-1] == " ":
        chars.pop()
        index.pop()
    return "".join(chars), index


def find_citation(document: str, citation: str) -> tuple[int, int] | None:
    """Return the (start, end) span of `citation` in `document`, or None.

    A citation containing "..." is treated as several fragments that must
    appear in order; the span then covers all of them.
    """
    parts = [p for p in _ELLIPSIS.split(citation.strip(_WRAPPING)) if p.strip()]
    if not parts:
        return None

    norm_doc, index = _normalize(document)
    pos = 0
    start = None
    for part in parts:
        norm_part, _ = _normalize(part)
        found = norm_doc.find(norm_part, pos)
        if found == -1:
            return None
        if start is None:
            start = found
        pos = found + len(norm_part)
    return index[start], index[pos - 1] + 1
