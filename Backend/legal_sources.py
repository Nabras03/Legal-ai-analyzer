"""Loads Swedish statutes and splits them into one chunk per section (paragraf).

The source text is Riksdagen's plain-text export, e.g.
https://data.riksdagen.se/dokument/sfs-1915-218.text, saved under
legal_sources/. A section is the natural unit to retrieve: it is what lawyers
cite ("36 § AvtL") and is short enough to quote in full.
"""

import re
from dataclasses import asdict, dataclass
from pathlib import Path

SOURCES_DIR = Path(__file__).parent / "legal_sources"

_CHAPTER = re.compile(r"^(\d+) kap\. (.+)$")
_SECTION = re.compile(r"^(\d+ ?[a-z]?) §\s+")


@dataclass
class Section:
    id: str        # "36 §"
    law: str       # "AvtL"
    chapter: str   # "3 kap. Om rättshandlingars ogiltighet"
    text: str
    url: str
    # Model-written plain-language summary, used only to improve retrieval;
    # never shown to the user as if it were the law.
    summary: str = ""

    def citation(self) -> str:
        return f"{self.id} {self.law}"

    def to_dict(self) -> dict:
        return asdict(self)


def parse_statute(raw: str, law: str, url_for) -> list[Section]:
    """Split a Riksdagen text export into sections.

    `url_for` maps a section number like "36" to a link to that section.
    Transitional provisions (Övergångsbestämmelser) are skipped.
    """
    sections: list[Section] = []
    chapter = ""
    current: tuple[str, list[str]] | None = None

    def flush():
        if current:
            num, lines = current
            text = "\n".join(lines).strip()
            sections.append(Section(f"{num} §", law, chapter, text, url_for(num.replace(" ", ""))))

    for line in raw.replace("\r\n", "\n").split("\n"):
        if line.startswith("Övergångsbestämmelser"):
            break
        if m := _CHAPTER.match(line):
            flush()
            current = None
            chapter = f"{m.group(1)} kap. {m.group(2)}"
        elif m := _SECTION.match(line):
            flush()
            current = (m.group(1), [line])
        elif current:
            current[1].append(line)
    flush()
    return sections


def load_avtalslagen() -> list[Section]:
    raw = (SOURCES_DIR / "avtalslagen.txt").read_text(encoding="utf-8")
    return parse_statute(raw, "AvtL", lambda num: f"https://lagen.nu/1915:218#P{num}")
