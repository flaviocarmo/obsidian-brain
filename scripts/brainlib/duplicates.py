"""Near-duplicate page detection.

Two pages about the same thing are worse than one: the reader finds whichever
comes first and never learns the other exists, so updates land on one copy and
queries return the stale one. Exact filename collisions cannot happen (the
filesystem forbids them), so the useful signal is *near* duplication of titles.

Two deliberate restrictions, both learned from the real vault:

- Only pages in the SAME top-level folder are compared. A `journal/` session
  page and a `domains/` concept page about the same subject are the intended
  pattern (the session records, the domain page distils), not a duplicate.
- Dated session prefixes and the `email-scan` marker are stripped before
  comparison, otherwise the 200+ session pages all look alike.
"""

import itertools
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

SIMILARITY_THRESHOLD = 0.75
MIN_TOKENS = 2

_SESSION_PREFIX = re.compile(r"^sessao \d{4}-\d{2}-\d{2}\s*")
_SCAN_MARKER = re.compile(r"^email-scan[-\s]?")
_WORD = re.compile(r"[a-z0-9]+")

# Portuguese and English function words carry no topical signal.
STOPWORDS = frozenset({
    "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
    "o", "a", "os", "as", "para", "com", "por", "um", "uma", "ao", "aos",
    "the", "of", "to", "in", "and", "for", "on", "at",
})


@dataclass
class Duplicate:
    similarity: float
    page_a: str
    page_b: str

    def message(self) -> str:
        return (f"possivel duplicata ({self.similarity:.0%} de similaridade no titulo): "
                f"{self.page_a} <> {self.page_b}")


def _fold(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def title_tokens(stem: str) -> set[str]:
    """Short tokens are dropped as noise EXCEPT when they carry a digit:
    ordinals and counters ("3a", "5a", "dia-1", "v2") are usually the only
    thing distinguishing two otherwise identical titles, so discarding them
    makes distinct pages look like duplicates."""
    s = _SCAN_MARKER.sub("", _SESSION_PREFIX.sub("", _fold(stem)))
    return {t for t in _WORD.findall(s)
            if t not in STOPWORDS and (len(t) > 2 or any(c.isdigit() for c in t))}


def similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find(pages: list[tuple[Path, str]],
         threshold: float = SIMILARITY_THRESHOLD) -> list[Duplicate]:
    """pages: (absolute path, vault-relative path like 'wiki/journal/X.md')."""
    by_folder: dict[str, list[tuple[str, set[str]]]] = {}
    for path, rel in pages:
        parts = rel.split("/")
        folder = parts[1] if len(parts) > 2 else "(raiz)"
        tokens = title_tokens(path.stem)
        if len(tokens) < MIN_TOKENS:
            continue  # too short to judge; a 1-word title says nothing
        by_folder.setdefault(folder, []).append((rel, tokens))

    found: list[Duplicate] = []
    for entries in by_folder.values():
        for (rel_a, tok_a), (rel_b, tok_b) in itertools.combinations(sorted(entries), 2):
            score = similarity(tok_a, tok_b)
            if score >= threshold:
                found.append(Duplicate(score, rel_a, rel_b))
    return sorted(found, key=lambda d: -d.similarity)
