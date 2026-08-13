import json
from pathlib import Path

from brainlib import codex_install

REPO = Path(__file__).resolve().parents[1]


def test_skill_rewrite_pins_the_repo_path_and_renames():
    """${CLAUDE_PLUGIN_ROOT} is a Claude Code variable; in Codex it expands to
    nothing and the skill's commands silently point at the filesystem root."""
    text = ('---\nname: save\ndescription: x\n---\n\n'
            'python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" lint\n')
    out = codex_install._rewrite_skill(text, Path("/repo"), "obsidian-brain-save")
    assert "CLAUDE_PLUGIN_ROOT" not in out
    assert "/repo/scripts/brain.py" in out.replace("\\", "/")
    assert "name: obsidian-brain-save" in out


def test_merge_keeps_other_tools_hooks():
    """hooks.json is shared; overwriting it disables whatever else lives there."""
    existing = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "outra-coisa.ps1"}]}]}}
    merged = codex_install.merge_hooks(existing, codex_install.build_hooks(Path("/repo"), "py"))
    assert merged["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "outra-coisa.ps1"
    assert "PostToolUse" in merged["hooks"] and "Stop" in merged["hooks"]


def test_merge_is_idempotent():
    ours = codex_install.build_hooks(Path("/repo"), "py")
    once = codex_install.merge_hooks({}, ours)
    twice = codex_install.merge_hooks(once, ours)
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)
    assert len(twice["hooks"]["PostToolUse"][0]["hooks"]) == 2


def test_reinstall_with_another_interpreter_replaces_instead_of_duplicating():
    """Same hook spelled with a different python path is not a different hook;
    string equality left a stale twin that ran the old repo copy."""
    first = codex_install.merge_hooks({}, codex_install.build_hooks(Path("/repo"), "/old/python"))
    second = codex_install.merge_hooks(first, codex_install.build_hooks(Path("/repo"), "/new/python"))
    commands = [h["command"] for g in second["hooks"]["PostToolUse"] for h in g["hooks"]]
    assert len(commands) == 2
    assert all("/new/python" in c for c in commands)


def test_moving_the_repo_does_not_leave_the_old_hook_behind():
    first = codex_install.merge_hooks({}, codex_install.build_hooks(Path("/old/repo"), "py"))
    second = codex_install.merge_hooks(first, codex_install.build_hooks(Path("/new/repo"), "py"))
    commands = [h["command"] for g in second["hooks"]["Stop"] for h in g["hooks"]]
    assert len(commands) == 1 and "old" not in commands[0]


def test_hook_commands_pin_the_interpreter():
    hooks = codex_install.build_hooks(Path("/repo"), "/usr/bin/python3.13")
    cmd = hooks["PostToolUse"][0]["hooks"][0]["command"]
    assert cmd.startswith('"/usr/bin/python3.13"')
    assert "validate-write.py" in cmd


def test_post_tool_use_matches_apply_patch():
    """Codex edits files through apply_patch; a matcher on anything else means
    the validator never runs."""
    assert codex_install.build_hooks(Path("/repo"), "py")["PostToolUse"][0]["matcher"] == "apply_patch"


def test_dry_run_touches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(codex_install, "skills_dir", lambda: tmp_path / "skills")
    monkeypatch.setattr(codex_install, "hooks_file", lambda: tmp_path / "hooks.json")
    names = codex_install.install_skills(REPO, dry_run=True)
    codex_install.install_hooks(REPO, "py", dry_run=True)
    assert names and not (tmp_path / "skills").exists() and not (tmp_path / "hooks.json").exists()


def test_install_is_repeatable(tmp_path, monkeypatch):
    monkeypatch.setattr(codex_install, "skills_dir", lambda: tmp_path / "skills")
    monkeypatch.setattr(codex_install, "hooks_file", lambda: tmp_path / "hooks.json")
    for _ in range(2):
        codex_install.install_skills(REPO, dry_run=False)
        codex_install.install_hooks(REPO, "py", dry_run=False)
    skill = tmp_path / "skills" / "obsidian-brain-save" / "SKILL.md"
    assert skill.is_file() and "name: obsidian-brain-save" in skill.read_text(encoding="utf-8")
    hooks = json.loads((tmp_path / "hooks.json").read_text(encoding="utf-8"))
    assert len(hooks["hooks"]["Stop"][0]["hooks"]) == 1  # no duplicates on re-run
