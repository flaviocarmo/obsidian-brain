"""Section extractor: the read-side answer to 250KB ledger pages."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


class ExtractError(Exception):
    pass


@dataclass
class Section:
    level: int
    title: str
    start: int  # 0-based line index of the heading
    end: int    # exclusive
    tokens: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _fold(s: str) -> str:
    """Casefold + strip accents so 'Identificação' matches 'identificacao'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold().strip()


def toc(text: str) -> list[Section]:
    lines = text.splitlines()
    heads: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    sections = []
    for idx, (start, level, title) in enumerate(heads):
        end = len(lines)
        for j in range(idx + 1, len(heads)):
            if heads[j][1] <= level:
                end = heads[j][0]
                break
        chunk = "\n".join(lines[start:end])
        sections.append(Section(level, title, start, end, estimate_tokens(chunk)))
    return sections


def get_sections(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    wanted = _fold(heading)
    all_sections = toc(text)
    exact = [s for s in all_sections if _fold(s.title) == wanted]
    hits = exact or [s for s in all_sections if _fold(s.title).startswith(wanted)]
    return ["\n".join(lines[s.start:s.end]) + "\n" for s in hits]


def resolve_page(vault: Path, ident: str) -> Path:
    as_path = vault / ident
    if as_path.suffix == ".md" and as_path.is_file():
        return as_path
    wanted = _fold(ident)
    pages = [p for p in (vault / "wiki").rglob("*.md")]
    exact = [p for p in pages if _fold(p.stem) == wanted]
    if len(exact) == 1:
        return exact[0]
    prefix = [p for p in pages if _fold(p.stem).startswith(wanted)]
    if len(prefix) == 1:
        return prefix[0]
    # last chance: permalink in frontmatter
    for p in pages:
        try:
            meta, _ = frontmatter.load(p)
        except frontmatter.FrontmatterError:
            continue
        if _fold(str(meta.get("permalink", ""))) == wanted:
            return p
    pool = exact or prefix
    if pool:
        names = ", ".join(sorted(p.stem for p in pool)[:8])
        raise ExtractError(f"ambiguous page {ident!r}: {names}")
    raise ExtractError(f"page not found: {ident!r}")
