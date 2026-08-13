"""Daily digest: turn queued session transcripts into journal pages.

The Stop hook enqueues sessions in .vault-meta/capture-queue.jsonl with
zero LLM cost; this module batches the pending ones into ONE headless
`claude -p` run that writes wiki/journal/ pages and a log entry following
the vault conventions. Contract ledgers, hot.md and index.md are out of
scope for the automatic path (curated saves stay human-triggered).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

DIGEST_TIMEOUT_SECONDS = 1800
DEFAULT_MODEL = "haiku"
# Marks the headless child so its own Stop hook does not enqueue it: without
# this the digest digests itself every single day.
SELF_MARKER_ENV = "BRAIN_DIGEST"


def _queue_path(vault: Path) -> Path:
    return vault / ".vault-meta" / "capture-queue.jsonl"


def _done_path(vault: Path) -> Path:
    return vault / ".vault-meta" / "digest-done.jsonl"


def pending(vault: Path) -> list[dict]:
    qp = _queue_path(vault)
    if not qp.exists():
        return []
    done_ids: set[str] = set()
    dp = _done_path(vault)
    if dp.exists():
        for line in dp.read_text(encoding="utf-8").splitlines():
            try:
                done_ids.add(json.loads(line)["session_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    latest: dict[str, dict] = {}
    for line in qp.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
            latest[item["session_id"]] = item
        except (json.JSONDecodeError, KeyError):
            continue
    out = []
    for sid, item in latest.items():
        if sid in done_ids:
            continue
        if not Path(item.get("transcript_path", "")).is_file():
            continue  # transcript gone; nothing to digest
        out.append(item)
    return sorted(out, key=lambda i: i.get("ts", 0))


def mark_done(vault: Path, items: list[dict]) -> None:
    dp = _done_path(vault)
    dp.parent.mkdir(parents=True, exist_ok=True)
    with dp.open("a", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps({"session_id": item["session_id"], "ts": item.get("ts", 0)}) + "\n")


def build_prompt(vault: Path, items: list[dict]) -> str:
    lines = [
        "Voce e o digest automatico do vault Obsidian (second brain profissional).",
        f"Vault: {vault}",
        "",
        "Para CADA transcript abaixo (JSONL de uma sessao do Claude Code):",
        "1. Leia o suficiente para entender o que a sessao fez (Read com limit/offset; "
        "transcripts grandes: comece pelo fim, que resume o desfecho).",
        "2. Escreva UMA pagina em wiki/journal/ nomeada 'Sessao YYYY-MM-DD <tema curto>.md' "
        "(data da sessao). Conteudo: o que foi feito, decisoes, fatos novos, pendencias "
        "que ficaram. Prosa objetiva, wikilinks [[Assim]] para paginas que ja existem.",
        "",
        "   FRONTMATTER EXATAMENTE NESTE FORMATO (o hook de validacao rejeita o resto):",
        "   ---",
        "   type: source",
        "   title: \"Titulo Humano da Sessao\"",
        "   created: YYYY-MM-DD",
        "   updated: YYYY-MM-DD",
        "   tags: [palavra, outra-palavra]",
        "   status: mature",
        "   ---",
        "   REGRAS: tags SEM '#' (em YAML '#' abre comentario e quebra o bloco inteiro); "
        "sem objetos aninhados; datas no formato YYYY-MM-DD; type e status apenas com os "
        "valores acima. Nao acrescente 'permalink' (o basic-memory adiciona sozinho).",
        "3. Se ja existir pagina de sessao do mesmo dia sobre o mesmo trabalho, ATUALIZE-a "
        "em vez de criar outra (busque antes em wiki/journal/).",
        "4. Adicione UMA entrada no TOPO de wiki/log.md: '## [YYYY-MM-DD] digest | <titulo>' "
        "com 2-3 bullets. O corpo antigo do log fica intacto.",
        "",
        "NAO toque em: wiki/contracts/ (ledgers sao curadoria manual), wiki/hot.md, "
        "wiki/index.md, .raw/. Sessao trivial ainda vira pagina, apenas curta.",
        "",
        "Transcripts pendentes:",
    ]
    for item in items:
        lines.append(f"- {item['transcript_path']} (cwd da sessao: {item.get('cwd', '?')})")
    return "\n".join(lines)


def run(vault: Path, model: str = DEFAULT_MODEL, dry_run: bool = False,
        claude_cmd: str = "claude") -> tuple[int, str]:
    items = pending(vault)
    if not items:
        return 0, "digest: queue empty, nothing to do"
    if dry_run:
        listing = "\n".join(f"- {i['session_id']} ({i['transcript_path']})" for i in items)
        return 0, f"digest dry-run: {len(items)} session(s) pending\n{listing}"
    proc = subprocess.run(
        [claude_cmd, "-p", build_prompt(vault, items), "--model", model,
         "--allowed-tools", "Read,Write,Edit,Grep,Glob"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=DIGEST_TIMEOUT_SECONDS,
        env={**os.environ, SELF_MARKER_ENV: "1"},
    )
    if proc.returncode != 0:
        return 1, f"digest: claude exited {proc.returncode}: {proc.stderr.strip()[:400]}"
    mark_done(vault, items)
    return 0, f"digest: {len(items)} session(s) digested\n{recompile_index(vault)}\n{proc.stdout.strip()[-600:]}"


def recompile_index(vault: Path) -> str:
    """The PostToolUse hook only fires for pages an agent writes; anything typed
    straight into Obsidian leaves index.md stale until someone recompiles. The
    daily run is the natural place to close that gap (no LLM involved)."""
    try:
        from . import index as index_mod
        return index_mod.compile(vault)
    except OSError as e:
        return f"index: recompile failed: {e}"


def main_cli(vault: Path, model: str | None, dry_run: bool) -> int:
    try:
        rc, msg = run(vault, model=model or DEFAULT_MODEL, dry_run=dry_run)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"digest: {e}", file=sys.stderr)
        return 1
    print(msg)
    return rc
