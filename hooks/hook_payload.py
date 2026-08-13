"""Which files did the tool call touch?

Claude Code names the file directly (`tool_input.file_path`, one per call).
Codex edits through `apply_patch`, whose `tool_input.command` is the patch
text itself and carries no path field — the paths are inside the envelope:

    *** Begin Patch
    *** Update File: wiki/journal/Sessao.md
    @@ ...
    *** Add File: wiki/domains/infra/Nova.md
    *** Delete File: wiki/old.md
    *** Move to: wiki/journal/Renomeada.md
    *** End Patch

So both agents can share one validator, this returns a LIST of absolute paths
for either shape. Relative paths (what a patch normally carries) resolve
against the hook payload's `cwd`, not the hook process's own directory.
"""

import re
from pathlib import Path

# "*** Update File: <path>"; Move carries the destination of the preceding file.
_PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$", re.MULTILINE)
_PATCH_MOVE = re.compile(r"^\*\*\* Move to: (.+?)\s*$", re.MULTILINE)


def paths_from_patch(patch_text: str) -> list[str]:
    if not patch_text:
        return []
    return _PATCH_PATH.findall(patch_text) + _PATCH_MOVE.findall(patch_text)


def target_paths(event: dict) -> list[Path]:
    """Absolute paths the tool call wrote, deduplicated, order preserved."""
    tool_input = event.get("tool_input") or {}
    base = Path(event.get("cwd") or ".")
    raw: list[str] = []

    direct = tool_input.get("file_path")
    if direct:
        raw.append(direct)

    # apply_patch puts the patch in `command`; some payloads use `input`/`patch`.
    for key in ("command", "input", "patch"):
        value = tool_input.get(key)
        if isinstance(value, str) and "*** Begin Patch" in value:
            raw += paths_from_patch(value)

    out: list[Path] = []
    seen = set()
    for item in raw:
        p = Path(item)
        p = p if p.is_absolute() else base / p
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out
