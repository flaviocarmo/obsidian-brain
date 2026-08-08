"""PostToolUse hook: keep wiki/index.md compiled, with a 30s debounce."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRAIN = REPO / "scripts" / "brain.py"
DEBOUNCE_SECONDS = 30


def _vault() -> Path | None:
    raw = os.environ.get("BRAIN_VAULT")
    if not raw:
        cfg = Path.home() / ".claude" / "brain.json"
        if not cfg.exists():
            return None
        try:
            raw = json.loads(cfg.read_text(encoding="utf-8")).get("vault")
        except (OSError, json.JSONDecodeError):
            return None
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def main() -> int:
    try:
        event = json.load(sys.stdin)
        file_path = event.get("tool_input", {}).get("file_path")
        vault = _vault()
        if not file_path or vault is None:
            return 0
        try:
            rel = Path(file_path).resolve().relative_to(vault.resolve()).as_posix()
        except ValueError:
            return 0
        if not rel.startswith("wiki/") or rel == "wiki/index.md":
            return 0
        meta = vault / ".vault-meta"
        meta.mkdir(exist_ok=True)
        dirty = meta / "index-dirty"
        dirty.write_text(str(time.time()), encoding="utf-8")
        idx = vault / "wiki" / "index.md"
        if idx.exists() and time.time() - idx.stat().st_mtime < DEBOUNCE_SECONDS:
            return 0  # too soon; next hook run picks it up
        proc = subprocess.run(
            [sys.executable, str(BRAIN), "--vault", str(vault), "compile-index"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        if proc.returncode == 0:
            dirty.unlink(missing_ok=True)
        else:
            with (meta / "brain.log").open("a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] compile-index rc={proc.returncode}: {proc.stderr.strip()}\n")
        return 0
    except Exception as e:  # noqa: BLE001 - hook must never break the session
        print(f"recompile-index hook error (ignored): {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
