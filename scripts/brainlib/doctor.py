"""Environment check: everything the plugin needs to work correctly.

basic-memory is a REQUIRED dependency: it is the search layer the query
skill relies on. Without it retrieval silently degrades to grep, which is
worse in a way nobody notices, so `brain doctor` fails loudly instead.
"""

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config

MIN_PYTHON = (3, 11)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fatal: bool = True

    def line(self) -> str:
        mark = "OK  " if self.ok else ("FAIL" if self.fatal else "WARN")
        return f"[{mark}] {self.name}: {self.detail}"


def check_python() -> Check:
    v = sys.version_info
    got = f"{v.major}.{v.minor}.{v.micro}"
    ok = (v.major, v.minor) >= MIN_PYTHON
    return Check("python", ok, f"{got} (minimo {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")


def check_vault(cli_override: str | None) -> tuple[Check, Path | None]:
    try:
        vault = config.vault_path(cli_override)
    except config.ConfigError as e:
        return Check("vault", False, str(e)), None
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return Check("vault", False, f"{vault} nao tem wiki/"), None
    pages = sum(1 for _ in wiki.rglob("*.md"))
    return Check("vault", True, f"{vault} ({pages} paginas)"), vault


def check_basic_memory() -> Check:
    """REQUIRED: the search layer. Degrading to grep is not acceptable."""
    exe = shutil.which("basic-memory")
    if not exe:
        return Check(
            "basic-memory", False,
            "nao encontrado no PATH. Instale: uv tool install basic-memory "
            "(depois: claude mcp add basic-memory -- basic-memory mcp)",
        )
    try:
        proc = subprocess.run([exe, "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return Check("basic-memory", False, f"{exe} nao respondeu: {e}")
    if proc.returncode != 0:
        return Check("basic-memory", False, f"{exe} saiu com {proc.returncode}")
    return Check("basic-memory", True, proc.stdout.strip() or exe)


def check_basic_memory_project(vault: Path | None) -> Check:
    """The vault must be indexed by a basic-memory project, else search misses it."""
    exe = shutil.which("basic-memory")
    if not exe or vault is None:
        return Check("basic-memory projeto", False, "pulado (basic-memory ou vault ausente)")
    try:
        proc = subprocess.run([exe, "project", "list", "--json"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=60)
        data = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return Check("basic-memory projeto", False, f"nao foi possivel listar projetos: {e}")

    def norm(p: str) -> str:
        return str(Path(p)).replace("\\", "/").rstrip("/").casefold()

    target = norm(str(vault))
    for proj in data.get("projects", []):
        # schema varies across basic-memory versions: local_path today, path before
        raw = proj.get("local_path") or proj.get("path") or ""
        if raw and norm(str(raw)) == target:
            name = proj.get("name", "?")
            default = " (default)" if proj.get("is_default") else ""
            return Check("basic-memory projeto", True, f"'{name}'{default} indexa o vault")
    names = ", ".join(str(p.get("name", "?")) for p in data.get("projects", [])) or "nenhum"
    return Check(
        "basic-memory projeto", False,
        f"nenhum projeto aponta para {vault} (existentes: {names}). "
        f'Rode: basic-memory project add <nome> "{vault}"',
    )


def check_hooks() -> Check:
    """Hooks live next to the package; missing files mean a broken install."""
    root = Path(__file__).resolve().parents[2]
    missing = [n for n in ("validate-write.py", "recompile-index.py", "capture-session.py")
               if not (root / "hooks" / n).is_file()]
    if missing:
        return Check("hooks", False, f"faltando: {', '.join(missing)}")
    return Check("hooks", True, "validate-write, recompile-index, capture-session")


def check_codex() -> Check:
    """Are the Codex copies still the ones this repo would produce?

    Claude Code loads the plugin from the repo, so `git pull` upgrades it.
    Codex runs from copies in ~/.agents/skills and ~/.codex/hooks.json, and a
    copy never announces that it is behind: the skills keep working, the old
    way, and the hooks keep pointing at whatever path they were installed with.
    Not having Codex at all is fine; having a stale install is what needs to be
    said out loud. Never fatal — Codex is optional.
    """
    from . import codex_install
    repo = Path(__file__).resolve().parents[2]
    version = codex_install.repo_version(repo) or "?"
    if not (Path.home() / ".codex").is_dir():
        return Check("codex", True, "nao instalado nesta maquina (ok)", fatal=False)
    manifest = codex_install.read_manifest()
    if not manifest:
        return Check("codex", False, "Codex presente mas o plugin nao foi instalado la: "
                                     "rode 'brain install-codex'", fatal=False)
    problems = []
    if manifest.get("version") != version:
        problems.append(f"copias na {manifest.get('version') or '?'}, repo na {version}")
    if manifest.get("repo") and Path(manifest["repo"]) != repo:
        problems.append(f"instaladas a partir de outro clone ({manifest['repo']})")
    stale_hooks = []
    try:
        hooks = json.loads(codex_install.hooks_file().read_text(encoding="utf-8"))
        for groups in hooks.get("hooks", {}).values():
            for group in groups:
                for handler in group.get("hooks", []):
                    cmd = handler.get("command", "")
                    if codex_install._is_ours(cmd) and str(repo) not in cmd:
                        stale_hooks.append(cmd)
    except (OSError, json.JSONDecodeError):
        pass
    if stale_hooks:
        problems.append(f"{len(stale_hooks)} hook(s) apontando para outro caminho")
    if problems:
        return Check("codex", False, "; ".join(problems) + " — rode 'brain install-codex' "
                     "e revise em /hooks (mudanca de hook reseta a confianca)", fatal=False)
    return Check("codex", True, f"skills e hooks na {version}", fatal=False)


def run(cli_override: str | None = None) -> tuple[int, str]:
    checks = [check_python()]
    vault_check, vault = check_vault(cli_override)
    checks.append(vault_check)
    bm = check_basic_memory()
    checks.append(bm)
    if bm.ok:
        checks.append(check_basic_memory_project(vault))
    checks.append(check_hooks())
    checks.append(check_codex())

    lines = [c.line() for c in checks]
    failed = [c for c in checks if not c.ok and c.fatal]
    if failed:
        lines.append(f"\n{len(failed)} requisito(s) nao atendido(s).")
        return 1, "\n".join(lines)
    lines.append("\nTudo pronto.")
    return 0, "\n".join(lines)
