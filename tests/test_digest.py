import json
import subprocess
import sys
from pathlib import Path

from brainlib import digest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "capture-session.py"


def _enqueue(vault, session_id, transcript, ts=1):
    q = vault / ".vault-meta" / "capture-queue.jsonl"
    q.parent.mkdir(exist_ok=True)
    with q.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"session_id": session_id, "transcript_path": str(transcript),
                            "cwd": "x", "ts": ts}) + "\n")


def test_pending_dedupes_and_skips_missing(vault, tmp_path):
    t1 = tmp_path / "t1.jsonl"
    t1.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t1, ts=1)
    _enqueue(vault, "s1", t1, ts=2)          # duplicate: keep latest
    _enqueue(vault, "s2", tmp_path / "gone.jsonl", ts=3)  # transcript missing
    items = digest.pending(vault)
    assert len(items) == 1 and items[0]["session_id"] == "s1" and items[0]["ts"] == 2


def test_mark_done_excludes_from_pending(vault, tmp_path):
    t1 = tmp_path / "t1.jsonl"
    t1.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t1)
    digest.mark_done(vault, digest.pending(vault))
    assert digest.pending(vault) == []


def test_dry_run_lists_without_calling_claude(vault, tmp_path):
    t1 = tmp_path / "t1.jsonl"
    t1.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t1)
    rc, msg = digest.run(vault, dry_run=True)
    assert rc == 0 and "1 session(s) pending" in msg and "s1" in msg


def test_empty_queue_is_noop(vault):
    rc, msg = digest.run(vault, dry_run=False, claude_cmd="definitely-not-a-command")
    assert rc == 0 and "queue empty" in msg


def test_prompt_mentions_transcripts_and_guardrails(vault, tmp_path):
    t1 = tmp_path / "t1.jsonl"
    t1.write_text("{}", encoding="utf-8")
    prompt = digest.build_prompt(vault, [{"session_id": "s1", "transcript_path": str(t1), "cwd": "c"}])
    assert str(t1) in prompt
    assert "wiki/journal/" in prompt and "wiki/contracts/" in prompt


def test_capture_hook_appends_and_dedupes(vault, tmp_path):
    import os
    env = dict(os.environ, BRAIN_VAULT=str(vault))
    event = {"session_id": "abc", "transcript_path": str(tmp_path / "t.jsonl"), "cwd": "w"}
    for _ in range(2):
        r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                           capture_output=True, text=True, env=env, timeout=30)
        assert r.returncode == 0
    lines = (vault / ".vault-meta" / "capture-queue.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # consecutive same-session stops collapse into one line


def test_capture_hook_broken_event_is_silent(vault):
    import os
    r = subprocess.run([sys.executable, str(HOOK)], input="not json",
                       capture_output=True, text=True,
                       env=dict(os.environ, BRAIN_VAULT=str(vault)), timeout=30)
    assert r.returncode == 0


def test_prompt_states_the_frontmatter_schema(vault, tmp_path):
    """The digest writes unattended; if the prompt does not pin the schema the
    model invents one and the pages land invalid."""
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    prompt = digest.build_prompt(vault, [{"session_id": "s", "transcript_path": str(t), "cwd": "c"}])
    for required in ("type: source", "status: mature", "tags: [palavra", "SEM '#'"):
        assert required in prompt
