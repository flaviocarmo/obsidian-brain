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


def test_run_reports_pages_written_outside_the_scope(vault, tmp_path, monkeypatch):
    """A transcript talks about MEMORY.md, READMEs and configs; an unattended
    model can read that as an instruction and drop a file in the vault root."""
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    (vault / "wiki" / "journal").mkdir(parents=True, exist_ok=True)

    def fake_run(cmd, **kwargs):
        (vault / "wiki" / "journal" / "Sessao 2026-08-13 x.md").write_text("ok", encoding="utf-8")
        (vault / "MEMORY.md").write_text("nao devia estar aqui", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(digest.subprocess, "run", fake_run)
    rc, msg = digest.run(vault, skip_hot=True)
    assert rc == 0
    assert "wrote outside its scope: MEMORY.md" in msg


def test_scope_check_accepts_journal_and_log(vault):
    before = digest.snapshot_files(vault)
    (vault / "wiki" / "journal" / "Sessao.md").write_text("x", encoding="utf-8")
    (vault / "wiki" / "log.md").write_text("x", encoding="utf-8")
    assert digest.files_written_outside_scope(vault, before) == []
    (vault / "wiki" / "domains" / "intruso.md").write_text("x", encoding="utf-8")
    assert digest.files_written_outside_scope(vault, before) == ["wiki/domains/intruso.md"]


def test_prompt_forbids_writing_outside_journal_and_log(vault, tmp_path):
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    prompt = digest.build_prompt(vault, [{"session_id": "s", "transcript_path": str(t), "cwd": "c"}])
    assert "ESCOPO DE ESCRITA" in prompt and "RAIZ do vault" in prompt


def test_capture_hook_ignores_the_digest_child(vault, tmp_path):
    """The digest spawns a headless claude; its Stop hook must not enqueue it,
    or every run schedules a page about the previous run."""
    import os
    event = {"session_id": "digest-child", "transcript_path": str(tmp_path / "t.jsonl"), "cwd": "w"}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                       capture_output=True, text=True,
                       env=dict(os.environ, BRAIN_VAULT=str(vault), BRAIN_DIGEST="1"), timeout=30)
    assert r.returncode == 0
    assert not (vault / ".vault-meta" / "capture-queue.jsonl").exists()


def test_run_marks_the_child_process(vault, tmp_path, monkeypatch):
    """The marker has to reach the child env, otherwise the hook cannot see it."""
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs.get("env") or {})
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(digest.subprocess, "run", fake_run)
    rc, _ = digest.run(vault)
    assert rc == 0 and seen.get(digest.SELF_MARKER_ENV) == "1"


def test_run_recompiles_the_index(vault, tmp_path, monkeypatch):
    """Pages typed in Obsidian never fire the PostToolUse hook; the daily run
    is what keeps index.md honest."""
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    (vault / "wiki").mkdir(exist_ok=True)
    (vault / "wiki" / "typed-by-hand.md").write_text(
        "---\ntype: source\ntitle: \"Typed\"\nstatus: mature\n---\n\ncorpo\n", encoding="utf-8")
    monkeypatch.setattr(digest.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""))
    rc, _ = digest.run(vault)
    assert rc == 0
    assert "typed-by-hand" in (vault / "wiki" / "index.md").read_text(encoding="utf-8")


HOT_OK = ('---\ntype: meta\ntitle: "Hot Cache"\nupdated: 2026-08-13\n---\n\n'
          "# Recent Context\n\n## Last Updated\n\nEstado de hoje.\n")


def _write_hot(vault, text):
    (vault / "wiki").mkdir(exist_ok=True)
    hot = vault / "wiki" / "hot.md"
    hot.write_text(text, encoding="utf-8")
    return hot


def test_refresh_hot_restores_previous_when_contract_breaks(vault, monkeypatch):
    """500 words is the whole point of the file; an unattended rewrite that blows
    past it must not survive, since the PostToolUse hook can only complain."""
    hot = _write_hot(vault, HOT_OK)
    before = hot.read_text(encoding="utf-8")

    def fake_run(cmd, **kwargs):
        hot.write_text(HOT_OK + ("palavra " * 600), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(digest.subprocess, "run", fake_run)
    msg = digest.refresh_hot(vault, [])
    assert "restored" in msg
    assert hot.read_text(encoding="utf-8") == before
    assert not list((vault / "wiki" / "folds").glob("*.md"))  # nothing archived on rollback


def test_refresh_hot_archives_the_superseded_version(vault, monkeypatch):
    hot = _write_hot(vault, HOT_OK)

    def fake_run(cmd, **kwargs):
        assert kwargs.get("env", {}).get(digest.SELF_MARKER_ENV) == "1"
        hot.write_text(HOT_OK.replace("Estado de hoje.", "Estado NOVO."), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(digest.subprocess, "run", fake_run)
    assert digest.refresh_hot(vault, []) == "hot: refreshed"
    archives = list((vault / "wiki" / "folds").glob("hot-cache-archive-*.md"))
    assert len(archives) == 1
    assert "Estado de hoje." in archives[0].read_text(encoding="utf-8")


def test_refresh_hot_keeps_previous_when_claude_fails(vault, monkeypatch):
    hot = _write_hot(vault, HOT_OK)
    monkeypatch.setattr(digest.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom"))
    msg = digest.refresh_hot(vault, [])
    assert "previous kept" in msg and hot.read_text(encoding="utf-8") == HOT_OK


def test_run_can_skip_the_hot_phase(vault, tmp_path, monkeypatch):
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    _write_hot(vault, HOT_OK)
    monkeypatch.setattr(digest.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""))
    rc, msg = digest.run(vault, skip_hot=True)
    assert rc == 0 and "hot: skipped" in msg


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


def test_run_folds_the_log_when_it_outgrows_the_cap(vault, tmp_path, monkeypatch):
    """The digest appends every night and fold was manual: anything that only
    grows and is trimmed by hand grows forever (this vault hit 53k tokens)."""
    from brainlib import fold as fold_mod
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    entries = "".join(
        f"## [2026-06-{d:02d}] Entrada {d}\n\n" + ("texto " * 500) + "\n\n" for d in range(28, 0, -1))
    (vault / "wiki/log.md").write_text(
        '---\ntype: meta\ntitle: "Log"\nupdated: 2026-06-28\n---\n\n# Operations Log\n\n' + entries,
        encoding="utf-8")
    monkeypatch.setattr(fold_mod, "MAX_LOG_TOKENS", 3000)
    monkeypatch.setattr(digest.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""))
    rc, msg = digest.run(vault, skip_hot=True)
    assert rc == 0 and "log:" in msg
    from brainlib import extract
    assert extract.estimate_tokens((vault / "wiki/log.md").read_text(encoding="utf-8")) <= 3000
    assert list((vault / "wiki/folds").glob("log-archive-*.md"))


def test_run_leaves_a_small_log_alone(vault, tmp_path, monkeypatch):
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    before = (vault / "wiki/log.md").read_text(encoding="utf-8")
    monkeypatch.setattr(digest.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""))
    rc, msg = digest.run(vault, skip_hot=True)
    assert rc == 0 and "dentro do teto" in msg
    assert (vault / "wiki/log.md").read_text(encoding="utf-8") == before


def test_hot_prompt_tells_the_rewrite_not_to_duplicate_mental_models(vault):
    """hot and models split by volatility: without saying so, the nightly
    rewrite copies durable facts back in and spends the 500-word budget
    repeating what is already written and kept current elsewhere."""
    from brainlib import models as models_mod
    models_mod.scaffold(vault, "Qual e o estado do contrato 071?")
    prompt = digest.build_hot_prompt(vault, [], models_mod.load(vault))
    assert "NAO repita no hot o conteudo deles" in prompt
    assert "Qual e o estado do contrato 071?" in prompt
    assert "VOLATIL" in prompt and "DURAVEL" in prompt


def test_hot_prompt_without_models_is_unchanged(vault):
    prompt = digest.build_hot_prompt(vault, [])
    assert "MENTAL MODELS" not in prompt


def test_run_reports_every_phase(vault, tmp_path, monkeypatch):
    """The model refresh was wired into the module and never called: the run
    said nothing about models, and nobody noticed for a night. Assert the
    phases the run must account for."""
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    monkeypatch.setattr(digest.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""))
    monkeypatch.setattr(digest, "refresh_hot", lambda *a, **k: "hot: refreshed")
    monkeypatch.setattr(digest, "refresh_models", lambda *a: "models: nada a atualizar")
    rc, msg = digest.run(vault)
    assert rc == 0
    for phase in ("digest:", "hot:", "models:", "log:", "index.md compiled"):
        assert phase in msg, f"fase ausente do relatorio: {phase}"


def test_index_recompiled_by_the_hook_is_not_a_scope_violation(vault, tmp_path, monkeypatch):
    """The recompile hook rewrites index.md because the digest wrote a page;
    reporting that trains the reader to ignore the warning."""
    t = tmp_path / "t.jsonl"
    t.write_text("{}", encoding="utf-8")
    _enqueue(vault, "s1", t)
    (vault / "wiki" / "journal").mkdir(parents=True, exist_ok=True)
    before = digest.snapshot_files(vault)
    (vault / "wiki" / "index.md").write_text("recompilado pelo hook", encoding="utf-8")
    assert digest.files_written_outside_scope(vault, before) == []
