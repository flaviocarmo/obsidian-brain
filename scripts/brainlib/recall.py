"""Recall by several routes at once, fused into one ranking.

Semantic search is good at "what was that thing about certificates" and bad at
"NF 1142" — the exact identifier is precisely what an embedding blurs. The
vault is full of those: invoice and service-order numbers, hostnames,
addresses. Hindsight fuses four retrieval strategies with reciprocal rank
fusion for this reason; this is the cheap version of the same idea, over the
index we already have.

Three routes:

* **hybrid** — basic-memory's vector + FTS search, the general case.
* **title** — a title match is a strong signal that a page IS the subject,
  not merely mentions it.
* **identifier** — deterministic grep for strong identifiers appearing in the
  query (NF/OS/Fatura numbers, IPv4, host-shaped tokens). No embedding
  involved, so `NF 1142` finds the page that says `NF 1142` and nothing else.

Fusion is reciprocal rank fusion: each route contributes `1/(k + rank)`, so a
page found by two routes outranks one found deeply by a single route, and no
route needs its scores to be comparable with another's.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import conflicts, frontmatter

RRF_K = 60
DEFAULT_TOP = 8
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOSTISH = re.compile(r"\b[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*\d[a-z0-9\-_]*\b", re.IGNORECASE)


@dataclass
class Result:
    file_path: str
    title: str
    routes: dict[str, int] = field(default_factory=dict)  # route -> rank (1-based)
    snippet: str = ""

    @property
    def score(self) -> float:
        return sum(1.0 / (RRF_K + rank) for rank in self.routes.values())

    def line(self) -> str:
        routes = "+".join(sorted(self.routes))
        return f"[{self.score:.4f}] {self.title}  ({routes})\n    {self.file_path}"


def identifiers_in(query: str) -> list[str]:
    """Strong, exact tokens worth grepping for, in the order they appear."""
    found: list[str] = []
    for pattern in conflicts.IDENTIFIERS:
        found += [m if isinstance(m, str) else m[0] for m in pattern.findall(query)]
    found += _IPV4.findall(query)
    found += [h for h in _HOSTISH.findall(query) if len(h) >= 4]
    seen, out = set(), []
    for f in found:
        if f.lower() not in seen:
            seen.add(f.lower())
            out.append(f)
    return out


def _search(query: str, flag: str | None, bm_cmd: str, timeout: int = 60) -> list[dict]:
    cmd = [bm_cmd, "tool", "search-notes", query]
    if flag:
        cmd.append(flag)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        return json.loads(proc.stdout).get("results", [])
    except json.JSONDecodeError:
        return []


def grep_identifiers(vault: Path, tokens: list[str], limit: int = 10) -> list[tuple[str, str, str]]:
    """(file_path, title, line) for pages literally containing a token.

    Deterministic on purpose: this is the route that does not care how a
    sentence was phrased, only that the number is there.
    """
    if not tokens:
        return []
    hits: list[tuple[str, str, str]] = []
    lowered = [t.lower() for t in tokens]
    for path in sorted((vault / "wiki").rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        if "/folds/" in rel or "/meta/" in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        block, body = frontmatter.split(text)
        title = path.stem
        if block:
            try:
                title = str(frontmatter.parse(block).get("title", path.stem))
            except frontmatter.FrontmatterError:
                pass
        low = body.lower()
        for token in lowered:
            if token in low:
                line = next((l.strip() for l in body.splitlines() if token in l.lower()), "")
                hits.append((rel, title, line[:160]))
                break
        if len(hits) >= limit:
            break
    return hits


def run(vault: Path, query: str, top: int = DEFAULT_TOP, bm_cmd: str = "basic-memory") -> list[Result]:
    merged: dict[str, Result] = {}

    def add(route: str, rank: int, file_path: str, title: str, snippet: str = "") -> None:
        item = merged.setdefault(file_path, Result(file_path=file_path, title=title))
        item.routes.setdefault(route, rank)
        if snippet and not item.snippet:
            item.snippet = snippet

    for route, flag in (("hybrid", "--hybrid"), ("title", "--title")):
        for rank, hit in enumerate(_search(query, flag, bm_cmd), start=1):
            path = hit.get("file_path") or hit.get("permalink", "")
            if path:
                add(route, rank, path, hit.get("title", path),
                    (hit.get("matched_chunk") or "")[:200])

    for rank, (path, title, line) in enumerate(grep_identifiers(vault, identifiers_in(query)), start=1):
        add("identifier", rank, path, title, line)

    return sorted(merged.values(), key=lambda r: r.score, reverse=True)[:top]


def main_cli(vault: Path, query: str, top: int, as_json: bool) -> int:
    results = run(vault, query, top)
    if as_json:
        print(json.dumps([{"file_path": r.file_path, "title": r.title,
                           "score": round(r.score, 5), "routes": r.routes,
                           "snippet": r.snippet} for r in results], ensure_ascii=False, indent=2))
        return 0
    if not results:
        print("recall: nada encontrado")
        return 0
    ident = identifiers_in(query)
    if ident:
        print(f"identificadores na consulta: {', '.join(ident)}\n")
    for r in results:
        print(r.line())
    return 0
