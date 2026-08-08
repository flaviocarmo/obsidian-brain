import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "recompile-index.py"


def _run(event, vault):
    env = dict(os.environ, BRAIN_VAULT=str(vault))
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, env=env, timeout=60)


def test_wiki_write_compiles_when_index_stale(vault):
    idx = vault / "wiki/index.md"
    old = time.time() - 3600
    os.utime(idx, (old, old))
    page = vault / "wiki/sources/Pagina Um.md"
    r = _run({"tool_input": {"file_path": str(page)}}, vault)
    assert r.returncode == 0
    assert "obsidian-brain" in idx.read_text(encoding="utf-8")  # recompiled by us


def test_recent_index_only_marks_dirty(vault):
    idx = vault / "wiki/index.md"
    idx.write_text("fresh", encoding="utf-8")  # mtime = now
    page = vault / "wiki/sources/Pagina Um.md"
    r = _run({"tool_input": {"file_path": str(page)}}, vault)
    assert r.returncode == 0
    assert idx.read_text(encoding="utf-8") == "fresh"
    assert (vault / ".vault-meta/index-dirty").exists()


def test_outside_wiki_is_noop(vault):
    r = _run({"tool_input": {"file_path": str(vault / ".raw/x.md")}}, vault)
    assert r.returncode == 0
    assert not (vault / ".vault-meta/index-dirty").exists()
