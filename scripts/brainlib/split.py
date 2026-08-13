"""Move a section out of a page that got too big, without losing the trail.

Detecting a bloated page and stopping at a warning is useless: the page keeps
growing and every future read pays for it. But splitting is not something to
do behind someone's back either — *which* section leaves is a semantic call.

So the split is: the human (or agent) names the cut, the tool performs it
correctly. Correctly means three things that are easy to get wrong by hand:

* The heading STAYS in the original, with a pointer under it. That is what
  keeps `[[Page#Section]]` links resolving — deleting the heading is how a
  manual split silently breaks inbound anchors.
* The new page inherits `type`, `status` and `tags` from its origin, so it
  passes the schema validator on the first try instead of coming back invalid.
* Nothing is written without a plan being shown first: `--apply` is a separate
  decision from seeing what would happen.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import extract, frontmatter

_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


class SplitError(Exception):
    pass


@dataclass
class Plan:
    source: Path
    section_title: str
    new_page: Path
    new_title: str
    moved_tokens: int
    remaining_tokens: int
    anchor_links: list[str] = field(default_factory=list)
    new_body: str = ""
    source_after: str = ""

    def describe(self, vault: Path) -> str:
        lines = [
            f"split: {self.source.relative_to(vault).as_posix()}",
            f"  secao      : {self.section_title!r} (~{self.moved_tokens} tokens)",
            f"  nova pagina: {self.new_page.relative_to(vault).as_posix()} (titulo {self.new_title!r})",
            f"  origem fica: ~{self.remaining_tokens} tokens, com o heading e um ponteiro",
        ]
        if self.anchor_links:
            lines.append(f"  links de ancora que continuam validos ({len(self.anchor_links)}): "
                         + ", ".join(self.anchor_links[:5]))
        lines.append("  nada foi escrito; repita com --apply para efetivar")
        return "\n".join(lines)


def _safe_filename(title: str) -> str:
    return _ILLEGAL.sub("-", title).strip().rstrip(".") or "Sem Titulo"


def _inherit(meta: dict, title: str) -> str:
    today = date.today().isoformat()
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tag_line = "[" + ", ".join(str(t) for t in tags) + "]" if tags else "[]"
    return (
        "---\n"
        f"type: {meta.get('type', 'concept')}\n"
        f'title: "{title}"\n'
        f"created: {today}\n"
        f"updated: {today}\n"
        f"tags: {tag_line}\n"
        f"status: {meta.get('status', 'seed')}\n"
        "---\n"
    )


def plan(vault: Path, page: str, heading: str, to: str | None = None,
         title: str | None = None) -> Plan:
    source = extract.resolve_page(vault, page)
    text = source.read_text(encoding="utf-8")
    block, body = frontmatter.split(text)
    if block is None:
        raise SplitError(f"{source.name}: sem frontmatter, nao da para herdar type/status")
    meta = frontmatter.parse(block)

    lines = body.splitlines()
    wanted = extract._fold(heading)
    hits = [s for s in extract.toc(body) if extract._fold(s.title) == wanted]
    if not hits:
        hits = [s for s in extract.toc(body) if extract._fold(s.title).startswith(wanted)]
    if not hits:
        raise SplitError(f"secao nao encontrada: {heading!r}")
    if len(hits) > 1:
        raise SplitError(f"secao ambigua ({len(hits)} correspondencias): {heading!r}")
    section = hits[0]

    new_title = title or section.title.strip().lstrip("#").strip()
    dest_dir = (vault / "wiki" / to) if to else source.parent
    new_page = dest_dir / f"{_safe_filename(new_title)}.md"
    if new_page.exists():
        raise SplitError(f"ja existe: {new_page.name}")

    moved = "\n".join(lines[section.start + 1:section.end]).strip("\n")
    new_body = _inherit(meta, new_title) + f"\n# {new_title}\n\n{moved}\n"

    pointer = (f"> Movido para [[{new_title}]] em {date.today().isoformat()} "
               f"(a pagina passava de {extract.estimate_tokens(body)} tokens).")
    kept = lines[:section.start + 1] + ["", pointer, ""] + lines[section.end:]
    source_after = (block if block.startswith("---") else f"---\n{block}\n---\n") + "\n".join(kept)
    if not source_after.endswith("\n"):
        source_after += "\n"

    anchors = []
    for other in (vault / "wiki").rglob("*.md"):
        if other == source:
            continue
        try:
            if f"[[{source.stem}#{section.title}" in other.read_text(encoding="utf-8"):
                anchors.append(other.relative_to(vault).as_posix())
        except OSError:
            continue

    return Plan(
        source=source, section_title=section.title, new_page=new_page, new_title=new_title,
        moved_tokens=extract.estimate_tokens(moved),
        remaining_tokens=extract.estimate_tokens("\n".join(kept)),
        anchor_links=sorted(anchors), new_body=new_body, source_after=source_after,
    )


def apply(p: Plan) -> None:
    p.new_page.parent.mkdir(parents=True, exist_ok=True)
    p.new_page.write_text(p.new_body, encoding="utf-8")
    p.source.write_text(p.source_after, encoding="utf-8")


def main_cli(vault: Path, page: str, heading: str, to: str | None,
             title: str | None, do_apply: bool) -> int:
    import sys
    try:
        p = plan(vault, page, heading, to, title)
    except (SplitError, extract.ExtractError, frontmatter.FrontmatterError) as e:
        print(f"split: {e}", file=sys.stderr)
        return 1
    if not do_apply:
        print(p.describe(vault))
        return 0
    apply(p)
    print(f"split aplicado: {p.new_page.relative_to(vault).as_posix()} criada; "
          f"origem agora com ~{p.remaining_tokens} tokens")
    return 0
