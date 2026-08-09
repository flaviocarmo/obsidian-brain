"""Cross-page contradiction detection.

A vault that grows by accretion ends up asserting two different things about
the same fact in two different pages, and the reader only notices when both
pages happen to be open. This module finds those pairs deterministically, by
joining pages on strong identifiers (invoice/service-order/bill numbers) and
comparing what each page says about them.

Only ONE rule survived contact with a real vault: status contradiction with
a recency guard. "Pending in May, issued in August" is progress, not a
conflict, so a page is only reported when it still claims *pending* while an
OLDER page already claims *issued*. Comparing money values was tried and
dropped: gross, net and retention figures for the same invoice legitimately
differ, and the rule flooded the report.

It never picks a winner: it reports both sides with each page's `updated`
date so a human decides. Automatic resolution is exactly the failure mode
this is meant to catch.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import frontmatter

# Strong identifiers: stable, human-assigned, unlikely to collide by accident.
IDENTIFIERS = (
    re.compile(r"\bNFS?[-\s]?(?:e\s)?n?º?\s?(\d{3,5})\b", re.IGNORECASE),
    re.compile(r"\bOS\s?n?º?\s?(\d{2,3}/\d{4})\b", re.IGNORECASE),
    re.compile(r"\bFatura\s?n?º?\s?(\d{1,3}/\d{4})\b", re.IGNORECASE),
)
_KINDS = ("NF", "OS", "Fatura")

_MONEY = re.compile(r"R\$\s?([\d.]{1,15},\d{2})")
# Pending wins over issued when both appear on the same line ("NF a emitir").
_PENDING = re.compile(
    r"pend[êe]nte|pendentes|\bpend\b|aguardando|a emitir|n[ãa]o emitida|"
    r"sem emiss[ãa]o|⏳|a confirmar",
    re.IGNORECASE,
)
_ISSUED = re.compile(r"emitida|emitidas|\bpaga\b|✅|\bNFS?\s?\d{3,5}\b", re.IGNORECASE)


@dataclass
class Mention:
    page: str
    updated: str
    line_no: int
    line: str
    money: set[str] = field(default_factory=set)
    status: str = ""  # "issued" | "pending" | ""


@dataclass
class Conflict:
    identifier: str
    kind: str
    reason: str
    mentions: list[Mention]

    def message(self) -> str:
        sides = " vs ".join(
            f"{m.page} (updated {m.updated or '?'}, linha {m.line_no})" for m in self.mentions
        )
        return f"conflito em {self.kind} {self.identifier}: {self.reason} — {sides}"


def _money_on(line: str) -> set[str]:
    return set(_MONEY.findall(line))


def _status_of(line: str) -> str:
    if _PENDING.search(line):
        return "pending"
    if _ISSUED.search(line):
        return "issued"
    return ""


def scan_page(path: Path, rel: str) -> list[tuple[str, str, Mention]]:
    """Return (kind, identifier, mention) for every strong id found in the body."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    block, body = frontmatter.split(text)
    updated = ""
    offset = 0
    if block:
        try:
            updated = str(frontmatter.parse(block).get("updated", ""))
        except frontmatter.FrontmatterError:
            updated = ""
        # report FILE line numbers, not body-relative ones: the reader opens
        # the file in an editor, and an off-by-frontmatter number is useless
        offset = len(block.splitlines()) + 2  # two --- delimiters
    out = []
    for i, line in enumerate(body.splitlines(), start=1 + offset):
        for kind, pattern in zip(_KINDS, IDENTIFIERS):
            for ident in pattern.findall(line):
                out.append((kind, ident, Mention(
                    page=rel, updated=updated, line_no=i, line=line.strip()[:160],
                    money=_money_on(line), status=_status_of(line),
                )))
    return out


def find(pages: list[tuple[Path, str]]) -> list[Conflict]:
    """pages: (absolute path, vault-relative path). Same-page mentions never conflict."""
    index: dict[tuple[str, str], list[Mention]] = defaultdict(list)
    for path, rel in pages:
        for kind, ident, mention in scan_page(path, rel):
            index[(kind, ident)].append(mention)

    conflicts: list[Conflict] = []
    for (kind, ident), mentions in sorted(index.items()):
        by_page: dict[str, list[Mention]] = defaultdict(list)
        for m in mentions:
            by_page[m.page].append(m)
        if len(by_page) < 2:
            continue  # a single page may say many things; that is its business

        # A page that records BOTH states is a ledger tracking progress: its
        # latest word is "issued". Only a page that never says issued counts
        # as claiming the thing is still pending.
        issued: list[Mention] = []
        pending: list[Mention] = []
        for _page, ms in by_page.items():
            has_issued = any(m.status == "issued" for m in ms)
            has_pending = any(m.status == "pending" for m in ms)
            if has_issued:
                issued.append(next(m for m in ms if m.status == "issued"))
            elif has_pending:
                pending.append(next(m for m in ms if m.status == "pending"))

        if not issued or not pending:
            continue

        # Recency guard: only anomalous if the page still saying "pending" is
        # at least as recent as the page saying "issued".
        newest_issued = max(issued, key=lambda m: m.updated or "")
        stale_pending = [m for m in pending if (m.updated or "") >= (newest_issued.updated or "")]
        if not stale_pending:
            continue
        conflicts.append(Conflict(
            ident, kind,
            "pagina mais recente ainda diz pendente enquanto outra ja diz emitida/paga",
            [max(stale_pending, key=lambda m: m.updated or ""), newest_issued],
        ))
    return conflicts
