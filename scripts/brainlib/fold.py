"""Extractive rollup: move old log.md entries into wiki/folds/ archives."""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import frontmatter, validate

_ENTRY = re.compile(r"^## \[(\d{4})-(\d{2})-(\d{2})\]", re.MULTILINE)


@dataclass
class FoldPlan:
    fm_block: str
    preamble: str = ""  # text between frontmatter and the first "## [date]" entry
    keep: list[str] = field(default_factory=list)
    archive: dict[str, list[str]] = field(default_factory=dict)

    def summary(self) -> str:
        moved = sum(len(v) for v in self.archive.values())
        months = ", ".join(sorted(self.archive)) or "-"
        return f"fold: keep {len(self.keep)} entries; archive {moved} entries into months: {months}"


def _entries(body: str) -> list[tuple[date, str]]:
    marks = list(_ENTRY.finditer(body))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        out.append((d, body[m.start():end].rstrip() + "\n"))
    return out


MAX_LOG_TOKENS = 15000


def plan(vault: Path, keep_days: int = 30, today: date | None = None,
         max_tokens: int = MAX_LOG_TOKENS) -> FoldPlan:
    today = today or date.today()
    cutoff = today - timedelta(days=keep_days)
    text = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    block, body = frontmatter.split(text)
    marks = list(_ENTRY.finditer(body))
    preamble = body[: marks[0].start()] if marks else body
    fp = FoldPlan(fm_block=block or "type: meta\ntitle: \"Log\"", preamble=preamble.strip("\n"))
    entries = _entries(body)
    kept: list[tuple[date, str]] = []
    for d, entry in entries:
        if d >= cutoff:
            kept.append((d, entry))
        else:
            fp.archive.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(entry)

    # A date cutoff alone does not bound the file: 45 entries landed in the
    # first 13 days of one month here, so "last 30 days" still left a 50k-token
    # log. Keep archiving the oldest of what survived until the file fits.
    def size(items: list[tuple[date, str]]) -> int:
        return max(1, len("\n".join(e for _d, e in items)) // 4)

    while len(kept) > 1 and size(kept) > max_tokens:
        d, entry = kept.pop()  # entries are newest-first; the tail is the oldest
        fp.archive.setdefault(f"{d.year:04d}-{d.month:02d}", []).insert(0, entry)

    fp.keep = [e for _d, e in kept]
    return fp


def apply(vault: Path, fp: FoldPlan) -> str:
    folds = vault / "wiki" / "folds"
    folds.mkdir(parents=True, exist_ok=True)
    for month, entries in sorted(fp.archive.items()):
        target = folds / f"log-archive-{month}.md"
        if target.exists():
            base = target.read_text(encoding="utf-8").rstrip() + "\n\n"
        else:
            base = (
                f"---\ntype: meta\ntitle: \"Log Archive {month}\"\n"
                f"created: {date.today().isoformat()}\nupdated: {date.today().isoformat()}\n"
                "tags: [log-archive]\nstatus: evergreen\n---\n\n"
            )
        target.write_text(base + "\n".join(entries) + "\n", encoding="utf-8")

    log_path = vault / "wiki" / "log.md"
    meta_dir = vault / ".vault-meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        # Destructive single-file rewrite: keep a pre-apply backup.
        (meta_dir / "log.md.bak").write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")

    preamble = f"{fp.preamble}\n\n" if fp.preamble else ""
    new_log = "---\n" + fp.fm_block.strip() + "\n---\n\n" + preamble + "\n".join(fp.keep) + "\n"
    log_path.write_text(new_log, encoding="utf-8")
    validate.update_log_state(vault, new_log)
    return fp.summary()
