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


def plan(vault: Path, keep_days: int = 30, today: date | None = None) -> FoldPlan:
    today = today or date.today()
    cutoff = today - timedelta(days=keep_days)
    text = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    block, body = frontmatter.split(text)
    marks = list(_ENTRY.finditer(body))
    preamble = body[: marks[0].start()] if marks else body
    fp = FoldPlan(fm_block=block or "type: meta\ntitle: \"Log\"", preamble=preamble.strip("\n"))
    for d, entry in _entries(body):
        if d >= cutoff:
            fp.keep.append(entry)
        else:
            fp.archive.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(entry)
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
