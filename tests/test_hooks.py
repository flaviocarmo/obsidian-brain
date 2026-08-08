import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "validate-write.py"


def _run_hook(event: dict, env_vault: str) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ, BRAIN_VAULT=env_vault)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True, text=True, env=env, timeout=30,
    )


def test_outside_vault_is_silent(vault, tmp_path):
    outside = tmp_path / "outro" ; outside.mkdir()
    f = outside / "x.md"; f.write_text("x", encoding="utf-8")
    r = _run_hook({"tool_input": {"file_path": str(f)}}, str(vault))
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_violation_blocks(vault):
    bad = vault / "wiki/sources/SemFm.md"
    bad.write_text("# sem frontmatter\n", encoding="utf-8")
    r = _run_hook({"tool_input": {"file_path": str(bad)}}, str(vault))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "block" and "frontmatter" in out["reason"]


def test_good_write_is_silent(vault):
    good = vault / "wiki/sources/Pagina Um.md"
    r = _run_hook({"tool_input": {"file_path": str(good)}}, str(vault))
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_broken_event_is_silent():
    import os
    r = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", capture_output=True,
        text=True, env=dict(os.environ, BRAIN_VAULT="C:/nope"), timeout=30,
    )
    assert r.returncode == 0
