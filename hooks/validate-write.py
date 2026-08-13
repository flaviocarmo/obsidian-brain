"""PostToolUse hook: validate every Write/Edit that lands inside the vault.

Contract: NEVER break the session. Internal errors exit 0 with a stderr
note; only real validation violations emit {"decision": "block"}.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_payload import target_paths  # noqa: E402 - sibling module, path set above

REPO = Path(__file__).resolve().parents[1]
BRAIN = REPO / "scripts" / "brain.py"


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
        vault = _vault()
        if vault is None:
            return 0
        targets = target_paths(event)
        if not targets:
            return 0
        errors: list[str] = []
        warns: list[str] = []
        for target in targets:
            try:
                target.resolve().relative_to(vault.resolve())
            except ValueError:
                continue  # outside the vault: not our business
            proc = subprocess.run(
                [sys.executable, str(BRAIN), "--vault", str(vault), "validate", str(target)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            if proc.returncode == 1:
                errors += [l for l in proc.stdout.splitlines() if l.startswith("ERROR: ")]
            warns += [l for l in proc.stdout.splitlines() if l.startswith("WARN: ")]
        if errors:
            print(json.dumps({"decision": "block", "reason": "\n".join(errors)}))
        elif warns:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n".join(warns),
            }}))
        return 0
    except Exception as e:  # noqa: BLE001 - hook must never break the session
        print(f"validate-write hook error (ignored): {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
