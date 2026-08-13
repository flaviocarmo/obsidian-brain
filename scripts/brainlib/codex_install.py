"""Install (and re-install, on every upgrade) the plugin into Codex CLI.

Claude Code loads skills and hooks straight from the plugin directory, so a
`git pull` is the whole upgrade. Codex has no plugin loader for this: skills
live in `~/.agents/skills/` and hooks in `~/.codex/hooks.json`, both as copies.
This command re-materialises those copies from the repo, which makes upgrading
`git pull && brain install-codex`.

Three things bite when doing it by hand, all handled here:

* `${CLAUDE_PLUGIN_ROOT}` does not exist outside Claude Code — every command in
  a copied SKILL.md has to be rewritten to the absolute repo path.
* `python` may not resolve in the environment Codex runs hooks in; the hook
  commands are pinned to the interpreter running this install.
* Codex silently skips hooks it has not been shown: after installing you must
  open `codex` and run `/hooks` to review and trust them, or they never fire.
"""

import json
import shutil
import sys
from pathlib import Path

SKILLS = ("query", "save", "ingest", "lint", "fold", "hot-cache")
PREFIX = "obsidian-brain-"


def skills_dir() -> Path:
    return Path.home() / ".agents" / "skills"


def hooks_file() -> Path:
    return Path.home() / ".codex" / "hooks.json"


def _rewrite_skill(text: str, repo: Path, name: str) -> str:
    out = []
    for line in text.splitlines():
        if line.startswith("name: "):
            line = f"name: {name}"
        out.append(line.replace("${CLAUDE_PLUGIN_ROOT}", str(repo)).replace("$CLAUDE_PLUGIN_ROOT", str(repo)))
    return "\n".join(out) + "\n"


def install_skills(repo: Path, dry_run: bool = False) -> list[str]:
    done = []
    for skill in SKILLS:
        src = repo / "skills" / skill
        if not (src / "SKILL.md").is_file():
            continue
        name = PREFIX + skill
        dest = skills_dir() / name
        if not dry_run:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            md = dest / "SKILL.md"
            md.write_text(_rewrite_skill(md.read_text(encoding="utf-8"), repo, name), encoding="utf-8")
        done.append(name)
    return done


def build_hooks(repo: Path, python: str) -> dict:
    def cmd(script: str) -> str:
        return f'"{python}" "{repo / "hooks" / script}"'
    return {
        "PostToolUse": [{
            "matcher": "apply_patch",
            "hooks": [
                {"type": "command", "timeout": 90, "command": cmd("validate-write.py")},
                {"type": "command", "timeout": 90, "command": cmd("recompile-index.py")},
            ],
        }],
        "Stop": [{
            "hooks": [{"type": "command", "timeout": 30, "command": cmd("capture-session.py")}],
        }],
    }


OUR_SCRIPTS = ("validate-write.py", "recompile-index.py", "capture-session.py")


def _is_ours(command: str) -> bool:
    return any(f"hooks{sep}{script}" in command for script in OUR_SCRIPTS for sep in ("\\", "/"))


def merge_hooks(existing: dict, ours: dict) -> dict:
    """Add our handlers without touching anyone else's.

    The user's hooks.json is shared with other tools; replacing the file would
    silently disable them. Our own handlers are identified by script name and
    replaced wholesale, so re-running after moving the repo or changing the
    interpreter refreshes the entry instead of leaving a stale twin behind
    (string equality is not enough: the same hook spelled with a different
    python path looks like a different hook).
    """
    merged = json.loads(json.dumps(existing)) if existing else {}
    hooks = merged.setdefault("hooks", {})
    for event in list(hooks):
        for group in hooks[event]:
            group["hooks"] = [h for h in group.get("hooks", []) if not _is_ours(h.get("command", ""))]
        hooks[event] = [g for g in hooks[event] if g.get("hooks")]
    for event, groups in ours.items():
        target = hooks.setdefault(event, [])
        for group in groups:
            same = next((g for g in target if g.get("matcher") == group.get("matcher")), None)
            if same is None:
                target.append({**({"matcher": group["matcher"]} if "matcher" in group else {}),
                               "hooks": list(group["hooks"])})
            else:
                same.setdefault("hooks", []).extend(group["hooks"])
        if not hooks[event]:
            del hooks[event]
    return merged


def install_hooks(repo: Path, python: str, dry_run: bool = False) -> Path:
    path = hooks_file()
    existing = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise OSError(f"{path} is not valid JSON; fix or move it before installing")
    merged = merge_hooks(existing, build_hooks(repo, python))
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copyfile(path, path.with_suffix(".json.bak"))
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return path


def main_cli(vault: Path, dry_run: bool = False) -> int:
    repo = Path(__file__).resolve().parents[2]
    python = sys.executable
    names = install_skills(repo, dry_run)
    path = install_hooks(repo, python, dry_run)
    prefix = "would install" if dry_run else "installed"
    print(f"{prefix} skills: {', '.join(names)} -> {skills_dir()}")
    print(f"{prefix} hooks -> {path}")
    print()
    print("Falta você fazer, uma vez:")
    print("  1. codex mcp add basic-memory -- basic-memory mcp")
    print("  2. abra `codex` e rode /hooks para REVISAR e CONFIAR nos hooks novos.")
    print("     Codex pula em silêncio hook não confiado — sem esse passo o vault")
    print("     fica sem validação de escrita no Codex.")
    print(f"  3. confira que {vault / 'AGENTS.md'} existe (contrato do vault para o Codex).")
    return 0
