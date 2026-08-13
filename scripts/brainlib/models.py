"""Mental models: standing answers to questions you declared worth answering.

The hot cache answers "what is going on right now" in 500 words, rewritten
nightly. A mental model generalises that: you write the question once, and the
answer is kept current in the background, so reading it costs a file read
instead of a retrieval plus an LLM call. Borrowed from Hindsight, which puts
it well — an agent that boots by loading its mental models "starts with a page
of settled knowledge instead of spending its first few seconds rediscovering
it".

The difference from a normal page is who writes it: you own the *question*
(frontmatter `question:`), the nightly run owns the *answer* (the body). So
the file is stable enough to link to and current enough to trust.

Refresh is deliberately conservative:

* Only models whose evidence changed are rewritten — a page updated after the
  model was. No change, no LLM call, no cost.
* A cap per run, because a vault with twenty models should not turn the
  nightly digest into twenty model calls.
* The rewrite is validated and rolled back if it breaks the schema or drops
  the question, the same contract the hot cache gets.
"""

import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import frontmatter, recall

MODEL_TIMEOUT_SECONDS = 600
DEFAULT_MODEL = "sonnet"
DEFAULT_REFRESH_LIMIT = 2
EVIDENCE_TOP = 8


@dataclass
class MentalModel:
    path: Path
    title: str
    question: str
    updated: str

    @property
    def rel(self) -> str:
        return self.path.name


def models_dir(vault: Path) -> Path:
    return vault / "wiki" / "models"


def load(vault: Path) -> list[MentalModel]:
    out = []
    for path in sorted(models_dir(vault).glob("*.md")) if models_dir(vault).is_dir() else []:
        try:
            block, _body = frontmatter.split(path.read_text(encoding="utf-8"))
            meta = frontmatter.parse(block) if block else {}
        except (OSError, frontmatter.FrontmatterError):
            continue
        if str(meta.get("type", "")) != "model":
            continue
        out.append(MentalModel(path=path, title=str(meta.get("title", path.stem)),
                               question=str(meta.get("question", "")),
                               updated=str(meta.get("updated", ""))))
    return out


def evidence_changed_since(vault: Path, model: MentalModel) -> bool:
    """Did anything the answer could depend on change after the last rewrite?

    Cheap and generous: any wiki page newer than the model's own file. Being
    generous is the right error here — a stale answer costs more than a
    needless refresh, and the refresh is capped anyway.
    """
    try:
        mtime = model.path.stat().st_mtime
    except OSError:
        return True
    for page in (vault / "wiki").rglob("*.md"):
        rel = page.relative_to(vault).as_posix()
        if rel.startswith(("wiki/models/", "wiki/folds/", "wiki/meta/")) or rel in (
                "wiki/index.md", "wiki/log.md", "wiki/hot.md"):
            continue
        try:
            if page.stat().st_mtime > mtime:
                return True
        except OSError:
            continue
    return False


def build_prompt(vault: Path, model: MentalModel, evidence: list[recall.Result]) -> str:
    lines = [
        "Voce mantem um MENTAL MODEL do vault Obsidian: a resposta permanente para UMA pergunta.",
        f"Vault: {vault}",
        f"Arquivo: {model.path}",
        f"PERGUNTA: {model.question}",
        "",
        "1. Leia as paginas de evidencia listadas abaixo (e outras que elas citarem, se precisar).",
        "2. REESCREVA O CORPO INTEIRO do arquivo com a resposta atual e completa.",
        "   Prosa objetiva, wikilinks [[Assim]] para as paginas que sustentam cada ponto.",
        "   Comece pelo veredito; depois o que sustenta; por fim o que ainda esta em aberto.",
        "3. NAO altere o frontmatter exceto 'updated' (ponha a data de hoje).",
        f"   A chave 'question' deve continuar exatamente: {model.question}",
        "4. Sem secao 'anterior', sem changelog: o arquivo e SOBRESCRITO, o historico vive no git.",
        "5. Se a evidencia nao responde a pergunta, diga isso explicitamente em vez de inventar.",
        "",
        "NAO escreva em nenhum outro arquivo.",
        "",
        "Evidencia (recall multi-rota):",
    ]
    lines += [f"- {r.file_path} ({'+'.join(sorted(r.routes))})" for r in evidence] or ["- (nenhuma)"]
    return "\n".join(lines)


def refresh_one(vault: Path, model: MentalModel, llm_model: str = DEFAULT_MODEL,
                claude_cmd: str = "claude") -> str:
    from . import digest, validate
    before = model.path.read_text(encoding="utf-8")
    evidence = recall.run(vault, model.question, top=EVIDENCE_TOP)
    try:
        proc = subprocess.run(
            [claude_cmd, "-p", build_prompt(vault, model, evidence), "--model", llm_model,
             "--allowed-tools", "Read,Write,Edit,Glob,Grep"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=MODEL_TIMEOUT_SECONDS,
            env={**__import__("os").environ, digest.SELF_MARKER_ENV: "1"},
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{model.rel}: nao atualizado ({e})"
    after = model.path.read_text(encoding="utf-8")
    if proc.returncode != 0 or after == before:
        if after != before:
            model.path.write_text(before, encoding="utf-8")
        return f"{model.rel}: inalterado"
    report = validate.validate_file(vault, model.path)
    if not report.ok:
        model.path.write_text(before, encoding="utf-8")
        return f"{model.rel}: rejeitado, anterior restaurado ({report.errors[0]})"
    return f"{model.rel}: atualizado"


def refresh(vault: Path, limit: int = DEFAULT_REFRESH_LIMIT, llm_model: str = DEFAULT_MODEL,
            claude_cmd: str = "claude", force: bool = False) -> list[str]:
    out = []
    for model in load(vault):
        if len(out) >= limit:
            break
        if not force and not evidence_changed_since(vault, model):
            continue
        out.append(refresh_one(vault, model, llm_model, claude_cmd))
    return out


def scaffold(vault: Path, question: str, title: str | None = None) -> Path:
    """Create the file that holds a question until the first refresh answers it."""
    today = date.today().isoformat()
    name = (title or question).strip().rstrip("?")
    safe = "".join(c for c in name if c not in '<>:"/\\|?*')[:80] or "Mental Model"
    path = models_dir(vault) / f"{safe}.md"
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntype: model\n"
        f'title: "{safe}"\n'
        f'question: "{question}"\n'
        f"created: {today}\nupdated: {today}\ntags: [mental-model]\nstatus: seed\n---\n\n"
        f"# {safe}\n\n"
        "> Ainda sem resposta: rode `brain models --refresh` (ou espere o digest desta noite).\n",
        encoding="utf-8")
    return path


def main_cli(vault: Path, question: str | None, do_refresh: bool, limit: int,
             force: bool) -> int:
    if question:
        try:
            path = scaffold(vault, question)
        except FileExistsError as e:
            print(f"models: ja existe: {e}")
            return 1
        print(f"models: criado {path.relative_to(vault).as_posix()}")
        return 0
    if do_refresh:
        results = refresh(vault, limit=limit, force=force)
        print("\n".join(results) if results else "models: nada a atualizar")
        return 0
    items = load(vault)
    if not items:
        print("models: nenhum mental model definido "
              '(crie com: brain models --question "sua pergunta")')
        return 0
    for m in items:
        stale = "desatualizado" if evidence_changed_since(vault, m) else "em dia"
        print(f"- {m.title} [{stale}, updated {m.updated}]\n    {m.question}")
    return 0
