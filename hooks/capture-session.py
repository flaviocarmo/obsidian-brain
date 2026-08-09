"""Stop hook: enqueue the session for the daily digest.

Deterministic and instant: appends one JSON line to
<vault>/.vault-meta/capture-queue.jsonl. The LLM work happens later in
`brain digest`. Contract: NEVER break the session — internal errors exit 0.
"""

import json
import os
import sys
import time
from pathlib import Path


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
        session_id = event.get("session_id")
        transcript = event.get("transcript_path")
        vault = _vault()
        if not session_id or not transcript or vault is None:
            return 0
        meta = vault / ".vault-meta"
        meta.mkdir(exist_ok=True)
        queue = meta / "capture-queue.jsonl"
        line = json.dumps({
            "session_id": session_id,
            "transcript_path": transcript,
            "cwd": event.get("cwd", ""),
            "ts": int(time.time()),
        })
        # skip duplicate consecutive appends from the same session
        if queue.exists():
            try:
                last = queue.read_text(encoding="utf-8").rstrip("\n").rsplit("\n", 1)[-1]
                if last and json.loads(last).get("session_id") == session_id:
                    prev = json.loads(last)
                    prev["ts"] = int(time.time())
                    lines = queue.read_text(encoding="utf-8").rstrip("\n").split("\n")
                    lines[-1] = json.dumps(prev)
                    queue.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    return 0
            except (json.JSONDecodeError, OSError):
                pass
        with queue.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return 0
    except Exception as e:  # noqa: BLE001 - hook must never break the session
        print(f"capture-session hook error (ignored): {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
