"""Compile wiki/index.md from page frontmatter. Human navigation artifact:
LLM sessions search via basic-memory instead of loading this file."""

from datetime import date
from pathlib import Path

from . import frontmatter

SKIP_FILES = {"index.md", "hot.md", "log.md"}
SKIP_DIRS = {"folds", "meta"}


def compile(vault: Path) -> str:
    wiki = vault / "wiki"
    groups: dict[str, list[str]] = {}
    total = 0
    for path in sorted(wiki.rglob("*.md")):
        rel = path.relative_to(wiki)
        if rel.name in SKIP_FILES and len(rel.parts) == 1:
            continue
        if rel.parts[0] in SKIP_DIRS:
            continue
        try:
            block, _ = frontmatter.split(path.read_text(encoding="utf-8"))
            meta = frontmatter.parse(block) if block else {}
        except (OSError, frontmatter.FrontmatterError):
            meta = {}
        bits = [str(meta.get("type", "?")), str(meta.get("status", "?"))]
        upd = str(meta.get("updated", ""))
        if upd:
            bits.append(upd[:10])
        folder = rel.parts[0] if len(rel.parts) > 1 else "(raiz)"
        groups.setdefault(folder, []).append(f"- [[{path.stem}]] ({', '.join(bits)})")
        total += 1

    out = [
        "---", "type: meta", 'title: "Wiki Index"',
        f"updated: {date.today().isoformat()}", "generated: obsidian-brain", "---",
        "# Wiki Index", "",
        f"> Artefato COMPILADO ({total} paginas). Nao editar a mao; regenerar com",
        "> `brain compile-index`. Sessoes LLM: buscar via basic-memory, nao carregar este arquivo.",
        "",
    ]
    for folder in sorted(groups):
        out.append(f"## {folder} ({len(groups[folder])})")
        out.extend(groups[folder])
        out.append("")
    (wiki / "index.md").write_text("\n".join(out), encoding="utf-8")
    return f"index.md compiled: {total} pages, {len(groups)} groups"
