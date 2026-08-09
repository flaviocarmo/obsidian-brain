"""Deterministic vault health checks. Read-only unless --write."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import conflicts, extract, frontmatter, validate

_WIKILINK = re.compile(r"\[\[([^\]\|#]+)")
_STALE = re.compile(r"\[!stale\]", re.IGNORECASE)


@dataclass
class Finding:
    severity: str  # error | warning | info
    path: str
    message: str

    def to_dict(self) -> dict:
        return {"severity": self.severity, "path": self.path, "message": self.message}


def _pages(vault: Path) -> list[Path]:
    wiki = vault / "wiki"
    out = []
    for p in sorted(wiki.rglob("*.md")):
        rel = p.relative_to(wiki)
        if rel.name in {"index.md", "hot.md", "log.md"} and len(rel.parts) == 1:
            continue
        if rel.parts[0] in {"folds", "meta"}:
            continue
        out.append(p)
    return out


def run(vault: Path) -> list[Finding]:
    wiki = vault / "wiki"
    pages = _pages(vault)
    stems = {p.stem.casefold(): p for p in pages}
    inbound: set[str] = set()
    findings: list[Finding] = []

    for p in pages:
        rel = p.relative_to(vault).as_posix()
        text = p.read_text(encoding="utf-8")
        block, body = frontmatter.split(text)
        if block is None:
            findings.append(Finding("error", rel, "no frontmatter"))
            continue
        try:
            meta = frontmatter.parse(block)
            for e in validate.check_schema(meta):
                findings.append(Finding("error", rel, e))
        except frontmatter.FrontmatterError as e:
            findings.append(Finding("error", rel, f"frontmatter: {e}"))

        for target in _WIKILINK.findall(body):
            t = target.strip().casefold()
            if t in stems:
                inbound.add(t)
            else:
                findings.append(Finding("warning", rel, f"dead wikilink: [[{target.strip()}]]"))

        lines = body.splitlines()
        heads = extract.iter_headings(body)
        for idx, (i, level, title) in enumerate(heads):
            nxt = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
            if not any(l.strip() for l in lines[i + 1:nxt]):
                if idx + 1 < len(heads) and heads[idx + 1][1] > level:
                    continue  # parent heading followed by subsection is fine
                findings.append(Finding("warning", rel, f"empty section: {title!r}"))

        if _STALE.search(body):
            findings.append(Finding("info", rel, "has [!stale] marker to revisit"))

    for p in pages:
        rel_parts = p.relative_to(wiki).parts
        if len(rel_parts) == 1:
            continue
        if p.stem.casefold() not in inbound:
            findings.append(Finding("info", p.relative_to(vault).as_posix(), f"orphan page: {p.stem} has no inbound links"))

    hot = wiki / "hot.md"
    if hot.exists():
        for e in validate.check_hot(hot.read_text(encoding="utf-8")):
            findings.append(Finding("error", "wiki/hot.md", e))

    idx_file = wiki / "index.md"
    if not idx_file.exists():
        findings.append(Finding("warning", "wiki/index.md", "index missing; run 'brain compile-index'"))
    else:
        idx_mtime = idx_file.stat().st_mtime
        if any(p.stat().st_mtime > idx_mtime for p in pages):
            findings.append(Finding("warning", "wiki/index.md", "index older than newest page; run 'brain compile-index'"))
        listed = idx_file.read_text(encoding="utf-8").count("- [[")
        if listed != len(pages):
            findings.append(Finding("warning", "wiki/index.md", f"index lists {listed} pages, vault has {len(pages)}"))

    # cross-page contradictions: same identifier, incompatible claims
    for c in conflicts.find([(p, p.relative_to(vault).as_posix()) for p in pages]):
        findings.append(Finding("warning", c.mentions[0].page, c.message()))
    return findings


def report_markdown(findings: list[Finding]) -> str:
    today = date.today().isoformat()
    lines = [
        "---", "type: meta", 'title: "Lint Report"', f"created: {today}",
        f"updated: {today}", "tags: [lint]", "status: seed", "---", "",
        f"# Lint Report ({today})", "",
    ]
    if not findings:
        lines.append("Sem achados.")
    for f in findings:
        lines.append(f"- **{f.severity}** `{f.path}`: {f.message}")
    return "\n".join(lines) + "\n"
