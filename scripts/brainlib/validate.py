"""Post-write validation: the safety net behind direct Write."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import frontmatter

TYPES = {"source", "entity", "concept", "domain", "comparison", "question",
         "overview", "meta", "area", "goal", "person", "decision", "runbook"}
# A runbook is the one page kind read while something is broken, so it is the
# one kind worth validating structurally. These three sections are what turns
# a narrative into a procedure someone else can execute: when it applies, what
# to do, and — the section every informal runbook omits — how to know it
# worked. Headings are matched accent- and case-insensitively.
RUNBOOK_SECTIONS = ("quando usar", "passos", "verificacao")
STATUSES = {"seed", "developing", "mature", "evergreen"}
REQUIRED_KEYS = ("type", "title", "created", "updated", "tags", "status")
HOT_WORD_LIMIT = 500
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ANTERIOR = re.compile(r"\banterior\b", re.IGNORECASE)
_H_DATE_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_H_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_date(s: str) -> date | None:
    if not _DATE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def check_schema(meta: dict) -> list[str]:
    errors = []
    for key in REQUIRED_KEYS:
        if key not in meta:
            errors.append(f"missing frontmatter key: {key}")
    if "type" in meta and meta["type"] not in TYPES:
        errors.append(f"invalid type: {meta['type']!r}")
    if "status" in meta and meta["status"] not in STATUSES:
        errors.append(f"invalid status: {meta['status']!r}")
    created = _parse_date(str(meta.get("created", "")))
    updated = _parse_date(str(meta.get("updated", "")))
    if "created" in meta and created is None:
        errors.append(f"created is not YYYY-MM-DD: {meta['created']!r}")
    if "updated" in meta and updated is None:
        errors.append(f"updated is not YYYY-MM-DD: {meta['updated']!r}")
    if created and updated and updated < created:
        errors.append(f"updated {updated} before created {created}")
    return errors


def check_runbook(text: str) -> list[str]:
    """A runbook without a verification section is a story, not a procedure."""
    from . import extract
    titles = {extract._fold(t) for _i, _lvl, t in extract.iter_headings(text)}
    missing = [s for s in RUNBOOK_SECTIONS
               if not any(t.startswith(s) or s in t for t in titles)]
    if missing:
        return [f"runbook sem secao obrigatoria: {', '.join(missing)} "
                f"(esperado: {', '.join(RUNBOOK_SECTIONS)})"]
    return []


def check_hot(text: str) -> list[str]:
    errors = []
    _, body = frontmatter.split(text)
    words = len(body.split())
    if words > HOT_WORD_LIMIT:
        errors.append(f"hot.md has {words} words (contract: {HOT_WORD_LIMIT}); overwrite, never append")
    for line in body.splitlines():
        if line.startswith("#") and _ANTERIOR.search(line):
            errors.append(f"hot.md has an 'anterior' section: {line.strip()!r}; overwrite the whole file")
    return errors


def _heading_date(line: str) -> date | None:
    m = _H_DATE_ISO.search(line)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _H_DATE_BR.search(line)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def check_ledger_chronology(text: str) -> list[str]:
    last: date | None = None
    for line in text.splitlines():
        if not line.startswith(("## ", "### ")):
            continue
        d = _heading_date(line)
        if d is None:
            continue
        if last is not None and d < last:
            return [
                f"ledger chronology: {line.strip()!r} ({d}) comes after a newer entry ({last}); "
                "insert records in chronological position, do not blind-append"
            ]
        last = d
    return []


def _raw_manifest_path(vault: Path) -> Path:
    return vault / ".vault-meta" / "raw-manifest.json"


def _check_raw(vault: Path, rel: str) -> list[str]:
    mp = _raw_manifest_path(vault)
    manifest = {"files": []}
    if mp.exists():
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {"files": []}
    name = rel.split("/", 1)[1] if "/" in rel else rel
    if name in manifest["files"]:
        return [f".raw/ is immutable: {name} already exists; ingest creates, never edits"]
    manifest["files"].append(name)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return []


def _log_state_path(vault: Path) -> Path:
    return vault / ".vault-meta" / "log-state.json"


LOG_STATE_VERSION = 2


def _body_of(text: str) -> bytes:
    _, body = frontmatter.split(text)
    return body.encode("utf-8")


def _log_entries_of(text: str) -> bytes:
    """Everything from the first '## ' heading on.

    The comparison has to skip the file's fixed prologue (the `# Operations
    Log` title and anything above the first entry): prepending an entry below
    a title means the old *body* is no longer a suffix of the new one, so
    hashing the whole body flagged every legitimate append as tampering.
    """
    _, body = frontmatter.split(text)
    if body.startswith("## "):
        return body.encode("utf-8")
    i = body.find("\n## ")
    return b"" if i == -1 else body[i + 1:].encode("utf-8")


def update_log_state(vault: Path, text: str) -> None:
    entries = _log_entries_of(text)
    p = _log_state_path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"version": LOG_STATE_VERSION, "length": len(entries),
                    "sha256": hashlib.sha256(entries).hexdigest()}),
        encoding="utf-8",
    )


def check_log(vault: Path, text: str, by_brain: bool) -> list[str]:
    sp = _log_state_path(vault)
    if by_brain or not sp.exists():
        update_log_state(vault, text)
        return []
    try:
        state = json.loads(sp.read_text(encoding="utf-8"))
        old_len, old_hash = int(state["length"]), state["sha256"]
        version = int(state.get("version", 1))
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        update_log_state(vault, text)
        return []
    if version != LOG_STATE_VERSION:
        update_log_state(vault, text)  # state written by an older format: re-baseline, never block
        return []
    entries = _log_entries_of(text)
    # entries[-old_len:] misbehaves when old_len == 0 (Python slicing treats -0
    # as 0, returning the whole body instead of an empty prefix), which would
    # falsely block the very first append to a log with no entries yet.
    if len(entries) >= old_len and hashlib.sha256(entries[len(entries) - old_len:]).hexdigest() == old_hash:
        update_log_state(vault, text)
        return []
    return ["wiki/log.md is append-at-top only: existing entries were edited or removed; restore them and prepend the new entry"]


def validate_file(vault: Path, path: Path, by_brain: bool = False) -> Report:
    r = Report()
    try:
        rel = path.resolve().relative_to(vault.resolve()).as_posix()
    except ValueError:
        return r  # outside vault: not our business
    if rel.startswith(".raw/"):
        r.errors += _check_raw(vault, rel)
        return r
    if not rel.endswith(".md") or not rel.startswith("wiki/"):
        return r
    name = rel[len("wiki/"):]
    if name == "index.md":
        if not by_brain:
            r.errors.append("wiki/index.md is compiled; run 'brain compile-index', never edit it")
        return r
    text = path.read_text(encoding="utf-8")
    if name == "hot.md":
        r.errors += check_hot(text)
        return r
    if name == "log.md":
        r.errors += check_log(vault, text, by_brain)
        return r
    block, _ = frontmatter.split(text)
    if block is None:
        r.errors.append(f"no frontmatter in {rel}")
        return r
    try:
        meta = frontmatter.parse(block)
    except frontmatter.FrontmatterError as e:
        r.errors.append(f"frontmatter error in {rel}: {e}")
        return r
    if name.startswith("folds/"):
        return r  # archives: parseable is enough
    r.errors += check_schema(meta)
    if str(meta.get("type", "")) == "runbook":
        r.errors += check_runbook(text)
    if name.startswith(("contracts/", "areas/")):
        r.warnings += check_ledger_chronology(text)
    return r
