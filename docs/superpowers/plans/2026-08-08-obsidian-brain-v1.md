# obsidian-brain v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugin de Claude Code, Windows nativo, que substitui o claude-obsidian: CLI `brain.py` (extract/validate/lint/compile-index/hot-check/fold), 2 hooks PostToolUse e 6 skills, com retrieval delegado ao basic-memory.

**Architecture:** Toda operação determinística mora no pacote Python `scripts/brainlib/` exposto pelo CLI `scripts/brain.py`; skills carregam só julgamento de LLM; hooks validam cada Write/Edit no vault e recompilam o index com debounce. Escrita é direta (tool Write), sem staging: violação volta como feedback no turno.

**Tech Stack:** Python 3.11+ stdlib pura (sem PyYAML, sem deps), pytest para testes, formato de plugin do Claude Code (`.claude-plugin/plugin.json`, `hooks/hooks.json`, `skills/*/SKILL.md`).

## Global Constraints

- Repo: `C:\drive-d\projetos\obsidian-brain` (todos os paths abaixo relativos a ele).
- Python >= 3.11, stdlib pura. Proibido adicionar dependência de runtime.
- Testes: pytest; **nenhum print de caractere fora de ASCII em teste** (console cp1252 não pode quebrar teste). Conteúdo de fixture pode ter acento; saída de teste não.
- CLI: exit 0 = ok, 1 = violação, 2 = erro de uso. `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` no entrypoint.
- Config: `~/.claude/brain.json` com `{"vault": "<path>"}`; env `BRAIN_VAULT` tem precedência (é o que os testes usam). Nada de path de vault hardcoded.
- Vault-alvo real: taxonomia Modo D (`wiki/` com concepts/areas/sources/people/goals/learning/resources/questions/meta/folds; `hot.md` <= 500 palavras; `index.md` compilado; `log.md` append no topo com entradas `## [YYYY-MM-DD] ...`).
- Schema universal de página: keys obrigatórias `type,title,created,updated,tags,status`; `type` em `source|entity|concept|domain|comparison|question|overview|meta|area|goal|person`; `status` em `seed|developing|mature|evergreen`; datas `YYYY-MM-DD`; **sem nested objects** no frontmatter.
- Arquivos exceção ao schema (na raiz de `wiki/`): `hot.md`, `index.md`, `log.md` (regras próprias); `wiki/folds/**` só precisa de frontmatter parseável.
- Commits em português brasileiro, Conventional Commits, **sem** trailer de coautoria.
- Comentários de código em inglês. Line endings: deixar o git decidir (repo já converte LF→CRLF no checkout).
- Hooks nunca podem impedir a sessão de funcionar: erro interno de hook = exit 0 com aviso; só violação de validação bloqueia (via JSON `decision: block`).

## File Structure

```
.claude-plugin/plugin.json         # manifest do plugin
.claude-plugin/marketplace.json    # marketplace local de 1 plugin
scripts/brain.py                   # shim CLI (2 linhas úteis); pacote fica em brainlib/
scripts/brainlib/__init__.py
scripts/brainlib/cli.py            # argparse, wiring dos subcomandos, exit codes
scripts/brainlib/config.py         # brain.json + BRAIN_VAULT
scripts/brainlib/frontmatter.py    # parser/serializer do YAML restrito
scripts/brainlib/extract.py        # TOC, seção por heading, resolução de página
scripts/brainlib/validate.py       # schema, hot contract, index/log/.raw guards, ledger
scripts/brainlib/lint.py           # checks de saúde do vault
scripts/brainlib/index.py          # compile-index (port do _scripts/compile_index.py)
scripts/brainlib/fold.py           # rollup do log.md para wiki/folds/
hooks/hooks.json                   # declaração PostToolUse
hooks/validate-write.py            # hook: valida Write/Edit no vault
hooks/recompile-index.py           # hook: index-dirty + debounce 30s
skills/{save,query,ingest,lint,fold,hot-cache}/SKILL.md
tests/conftest.py                  # fixture make_vault (mini-vault em tmp_path)
tests/test_config.py  test_frontmatter.py  test_extract.py  test_validate.py
tests/test_index.py   test_lint.py         test_fold.py     test_hooks.py
README.md                          # já existe; atualizar status no fim
```

Nota de nome: a spec dizia `scripts/brain/`; pacote chama `brainlib/` porque `brain.py` e `brain/` no mesmo diretório colidem na resolução de import. `brain.py` é só shim.

---

### Task 1: Scaffold do repo + CLI esqueleto

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `scripts/brain.py`, `scripts/brainlib/__init__.py`, `scripts/brainlib/cli.py`, `tests/conftest.py`, `tests/test_cli_skeleton.py`, `.gitignore`

**Interfaces:**
- Produces: `brainlib.cli.main(argv: list[str] | None = None) -> int` (exit code); shim `scripts/brain.py` executável com `python scripts/brain.py <cmd>`; conftest com `sys.path` apontando para `scripts/`.

- [ ] **Step 1: Escrever teste que falha**

`tests/conftest.py`:

```python
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
```

`tests/test_cli_skeleton.py`:

```python
from brainlib import cli


def test_no_args_is_usage_error(capsys):
    assert cli.main([]) == 2


def test_unknown_command_is_usage_error():
    assert cli.main(["nope"]) == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cli_skeleton.py -v` (cwd = raiz do repo)
Expected: FAIL, `ModuleNotFoundError: brainlib` ou `AttributeError: main`

- [ ] **Step 3: Implementação mínima**

`scripts/brainlib/__init__.py`: vazio.

`scripts/brainlib/cli.py`:

```python
"""obsidian-brain CLI. Exit codes: 0 ok, 1 violation, 2 usage error."""

import argparse
import sys

COMMANDS = ("extract", "validate", "lint", "compile-index", "hot-check", "fold")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brain", description="obsidian-brain CLI")
    p.add_argument("--vault", help="override vault path (else BRAIN_VAULT or ~/.claude/brain.json)")
    sub = p.add_subparsers(dest="command")
    for name in COMMANDS:
        sub.add_parser(name)
    return p


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args, _rest = build_parser().parse_known_args(argv)
    if not args.command:
        print("usage: brain <command>; commands: " + ", ".join(COMMANDS), file=sys.stderr)
        return 2
    if args.command not in COMMANDS:
        return 2
    print(f"{args.command}: not implemented yet", file=sys.stderr)
    return 2
```

Obs.: `argparse` com subparser desconhecido chama `sys.exit(2)` sozinho; capturar não é preciso, o teste de comando desconhecido passa via `SystemExit`. Se `SystemExit` vazar no teste, envolver: no `main`, trocar `parse_known_args` por try/except `SystemExit` retornando 2:

```python
    try:
        args, _rest = build_parser().parse_known_args(argv)
    except SystemExit:
        return 2
```

`scripts/brain.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brainlib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
```

`.claude-plugin/plugin.json`:

```json
{
  "name": "obsidian-brain",
  "version": "0.1.0",
  "description": "Second brain em vault Obsidian, Windows nativo: validacao por hook, extrator de secao, lint, fold. Retrieval via basic-memory.",
  "author": { "name": "Flavio Carmo" }
}
```

`.claude-plugin/marketplace.json`:

```json
{
  "name": "obsidian-brain-marketplace",
  "owner": { "name": "Flavio Carmo" },
  "plugins": [
    {
      "name": "obsidian-brain",
      "source": "./",
      "description": "Second brain em vault Obsidian, Windows nativo."
    }
  ]
}
```

`.gitignore`:

```
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cli_skeleton.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: scaffold do plugin com CLI esqueleto e manifests"
```

---

### Task 2: config.py

**Files:**
- Create: `scripts/brainlib/config.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `config.vault_path(cli_override: str | None = None) -> Path`. Precedência: argumento > env `BRAIN_VAULT` > `~/.claude/brain.json`. Erros viram `config.ConfigError(str)`.

- [ ] **Step 1: Teste que falha**

`tests/test_config.py`:

```python
import json

import pytest

from brainlib import config


def test_env_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(tmp_path))
    assert config.vault_path() == tmp_path


def test_cli_override_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", "C:/nope")
    assert config.vault_path(str(tmp_path)) == tmp_path


def test_brain_json(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_VAULT", raising=False)
    cfg_dir = tmp_path / ".claude"
    cfg_dir.mkdir()
    (cfg_dir / "brain.json").write_text(json.dumps({"vault": str(tmp_path)}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "brain.json")
    assert config.vault_path() == tmp_path


def test_missing_vault_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_VAULT", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "absent.json")
    with pytest.raises(config.ConfigError):
        config.vault_path()


def test_nonexistent_dir_raises(monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", "C:/definitely/not/here-xyz")
    with pytest.raises(config.ConfigError):
        config.vault_path()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL, `ModuleNotFoundError` ou `AttributeError`

- [ ] **Step 3: Implementação**

`scripts/brainlib/config.py`:

```python
"""Vault location resolution: CLI arg > BRAIN_VAULT env > ~/.claude/brain.json."""

import json
import os
from pathlib import Path

CONFIG_FILE = Path.home() / ".claude" / "brain.json"


class ConfigError(Exception):
    pass


def vault_path(cli_override: str | None = None) -> Path:
    raw = cli_override or os.environ.get("BRAIN_VAULT")
    if not raw:
        if not CONFIG_FILE.exists():
            raise ConfigError(f"no vault configured: set BRAIN_VAULT or create {CONFIG_FILE}")
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"cannot read {CONFIG_FILE}: {e}") from e
        raw = data.get("vault")
        if not raw:
            raise ConfigError(f"{CONFIG_FILE} has no 'vault' key")
    p = Path(raw)
    if not p.is_dir():
        raise ConfigError(f"vault path is not a directory: {p}")
    return p.resolve()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_config.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: resolucao de vault via env e brain.json"
```

---

### Task 3: frontmatter.py (YAML restrito)

**Files:**
- Create: `scripts/brainlib/frontmatter.py`, `tests/test_frontmatter.py`

**Interfaces:**
- Produces:
  - `frontmatter.split(text: str) -> tuple[str | None, str]` (bloco YAML sem delimitadores, corpo)
  - `frontmatter.parse(yaml_text: str) -> dict[str, str | list[str]]`, levanta `FrontmatterError` em nested object/tab
  - `frontmatter.serialize(data: dict) -> str` (com `---` delimitadores, newline final)
  - `frontmatter.load(path: Path) -> tuple[dict, str]` (meta, corpo); `FrontmatterError` se sem frontmatter

- [ ] **Step 1: Testes que falham**

`tests/test_frontmatter.py`:

```python
import pytest

from brainlib import frontmatter as fm

DOC = """---
type: source
title: "Pagina de Teste: com dois-pontos"
created: 2026-05-06
updated: 2026-05-10
tags:
- financeiro
- notas-fiscais
status: mature
related:
- "[[Outra Pagina]]"
sources: []
---

# Corpo

Texto.
"""


def test_split():
    block, body = fm.split(DOC)
    assert block is not None and block.startswith("type: source")
    assert body.startswith("\n# Corpo")


def test_split_no_frontmatter():
    block, body = fm.split("# Sem nada\n")
    assert block is None and body == "# Sem nada\n"


def test_parse_scalars_and_lists():
    meta = fm.parse(fm.split(DOC)[0])
    assert meta["type"] == "source"
    assert meta["title"] == "Pagina de Teste: com dois-pontos"
    assert meta["tags"] == ["financeiro", "notas-fiscais"]
    assert meta["related"] == ["[[Outra Pagina]]"]
    assert meta["sources"] == []


def test_inline_list():
    meta = fm.parse("tags: [a, b, c]")
    assert meta["tags"] == ["a", "b", "c"]


def test_nested_object_rejected():
    with pytest.raises(fm.FrontmatterError):
        fm.parse("metadata:\n  type: user")


def test_roundtrip():
    block, _ = fm.split(DOC)
    meta = fm.parse(block)
    again = fm.parse(fm.split(fm.serialize(meta) + "\ncorpo")[0])
    assert again == meta
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_frontmatter.py -v`
Expected: FAIL

- [ ] **Step 3: Implementação**

`scripts/brainlib/frontmatter.py`:

```python
"""Restricted-YAML frontmatter for Modo D vaults.

Supported: `key: scalar`, `key:` + dash list, inline `[a, b]`, quoted
strings, empty list `[]`. Nested mappings are a schema violation by design
(Obsidian Properties UI does not support them).
"""

import re
from pathlib import Path

_DELIM = "---"
_KEY = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")


class FrontmatterError(Exception):
    pass


def split(text: str) -> tuple[str | None, str]:
    if not text.startswith(_DELIM + "\n"):
        return None, text
    # find closing delimiter on its own line
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    block = text[len(_DELIM) + 1 : end]
    rest = text[end + len("\n---") :]
    if rest.startswith("\n"):
        rest = rest[1:]
    return block, rest


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def parse(yaml_text: str) -> dict:
    meta: dict = {}
    current_list: str | None = None
    for raw in yaml_text.splitlines():
        if "\t" in raw:
            raise FrontmatterError("tab character in frontmatter")
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith(("  ", "    ")) and not line.lstrip().startswith("-"):
            raise FrontmatterError(f"nested object not allowed: {line.strip()!r}")
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_list is None:
                raise FrontmatterError(f"list item without key: {stripped!r}")
            meta[current_list].append(_unquote(stripped[2:]))
            continue
        m = _KEY.match(stripped)
        if not m:
            raise FrontmatterError(f"unparseable line: {stripped!r}")
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            meta[key] = []
            current_list = key
        elif value == "[]":
            meta[key] = []
            current_list = None
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [_unquote(x) for x in inner.split(",")] if inner else []
            current_list = None
        else:
            meta[key] = _unquote(value)
            current_list = None
    return meta


def _quote_if_needed(v: str) -> str:
    if v == "" or ":" in v or v.startswith(("[", "'", '"', "-", "{", "*", "&")):
        return '"' + v.replace('"', '\\"') + '"'
    return v


def serialize(data: dict) -> str:
    out = [_DELIM]
    for key, value in data.items():
        if isinstance(value, list):
            if not value:
                out.append(f"{key}: []")
            else:
                out.append(f"{key}:")
                out.extend(f"- {_quote_if_needed(str(item))}" for item in value)
        else:
            out.append(f"{key}: {_quote_if_needed(str(value))}")
    out.append(_DELIM)
    return "\n".join(out) + "\n"


def load(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    block, body = split(text)
    if block is None:
        raise FrontmatterError(f"no frontmatter: {path}")
    return parse(block), body
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_frontmatter.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: parser e serializer de frontmatter YAML restrito"
```

---

### Task 4: extract.py (TOC, seção, resolução de página)

**Files:**
- Create: `scripts/brainlib/extract.py`, `tests/test_extract.py`
- Modify: `tests/conftest.py` (fixture `make_vault`)

**Interfaces:**
- Consumes: `frontmatter.split`, `frontmatter.load`, `config.vault_path`
- Produces:
  - `extract.Section` dataclass: `level: int, title: str, start: int, end: int, tokens: int` (linhas 0-based, `end` exclusivo, tokens ~= chars/4)
  - `extract.toc(text: str) -> list[Section]`
  - `extract.get_sections(text: str, heading: str) -> list[str]` (todas as ocorrências; match case-insensitive exato, senão prefixo; inclui subseções)
  - `extract.resolve_page(vault: Path, ident: str) -> Path` levanta `ExtractError` com candidatos se ambíguo/ausente
  - `extract.estimate_tokens(text: str) -> int`

- [ ] **Step 1: Fixture de vault em conftest**

Adicionar ao `tests/conftest.py`:

```python
import pytest


@pytest.fixture
def vault(tmp_path):
    """Minimal Modo D vault used across tests."""
    wiki = tmp_path / "wiki"
    for sub in ("areas", "sources", "concepts", "meta", "folds"):
        (wiki / sub).mkdir(parents=True)
    (tmp_path / ".raw").mkdir()
    (tmp_path / ".vault-meta").mkdir()

    def page(rel, title, type_="source", status="mature", body="Corpo.\n", extra=""):
        text = (
            "---\n"
            f"type: {type_}\n"
            f'title: "{title}"\n'
            "created: 2026-05-01\n"
            "updated: 2026-06-01\n"
            "tags: [teste]\n"
            f"status: {status}\n"
            f"{extra}"
            "---\n\n"
            f"{body}"
        )
        p = wiki / rel
        p.write_text(text, encoding="utf-8")
        return p

    page("sources/Pagina Um.md", "Pagina Um", body="# Pagina Um\n\nTexto A.\n\nLink [[Contrato Grande]].\n")
    page(
        "areas/Contrato Grande.md",
        "Contrato Grande",
        type_="area",
        body=(
            "# Contrato Grande\n\n"
            "## Identificacao\n\nDados.\n\n"
            "## Faturas 2026\n\nFatura 1.\n\n"
            "### NFs emitidas\n\nNF 100.\n\n"
            "## Faturas 2026\n\nBloco duplicado.\n"
        ),
    )
    (wiki / "hot.md").write_text(
        "---\ntype: meta\ntitle: \"Hot Cache\"\nupdated: 2026-06-01\n---\n\n# Recent Context\n\nCurto.\n",
        encoding="utf-8",
    )
    (wiki / "log.md").write_text(
        "---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-01\n---\n\n"
        "## [2026-06-01] Entrada nova\n\ndetalhe\n\n"
        "## [2026-05-01] Entrada velha\n\ndetalhe\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("---\ntype: meta\ntitle: \"Wiki Index\"\nupdated: 2026-06-01\n---\n# Wiki Index\n", encoding="utf-8")
    return tmp_path
```

- [ ] **Step 2: Testes que falham**

`tests/test_extract.py`:

```python
import pytest

from brainlib import extract


def test_toc_levels_and_tokens(vault):
    text = (vault / "wiki/areas/Contrato Grande.md").read_text(encoding="utf-8")
    sections = extract.toc(text)
    titles = [s.title for s in sections]
    assert "Identificacao" in titles
    assert titles.count("Faturas 2026") == 2
    assert all(s.tokens > 0 for s in sections)


def test_get_section_includes_subsections(vault):
    text = (vault / "wiki/areas/Contrato Grande.md").read_text(encoding="utf-8")
    parts = extract.get_sections(text, "faturas 2026")
    assert len(parts) == 2
    assert "NFs emitidas" in parts[0]
    assert "Bloco duplicado" in parts[1]


def test_get_section_prefix_and_accent_insensitive_exact_first():
    text = "# T\n\n## Identificacao Completa\n\nA.\n\n## Ident\n\nB.\n"
    assert extract.get_sections(text, "ident") == ["## Ident\n\nB.\n"]
    assert "A." in extract.get_sections(text, "identificacao")[0]


def test_resolve_by_title_and_path(vault):
    p = extract.resolve_page(vault, "contrato grande")
    assert p.name == "Contrato Grande.md"
    p2 = extract.resolve_page(vault, "wiki/sources/Pagina Um.md")
    assert p2.name == "Pagina Um.md"


def test_resolve_missing_raises(vault):
    with pytest.raises(extract.ExtractError):
        extract.resolve_page(vault, "nao existe")


def test_big_page_estimate():
    body = "# T\n" + ("## S\n" + "x" * 400 + "\n") * 700  # ~280KB
    assert extract.estimate_tokens(body) > 8000
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL

- [ ] **Step 4: Implementação**

`scripts/brainlib/extract.py`:

```python
"""Section extractor: the read-side answer to 250KB ledger pages."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


class ExtractError(Exception):
    pass


@dataclass
class Section:
    level: int
    title: str
    start: int  # 0-based line index of the heading
    end: int    # exclusive
    tokens: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _fold(s: str) -> str:
    """Casefold + strip accents so 'Identificação' matches 'identificacao'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold().strip()


def toc(text: str) -> list[Section]:
    lines = text.splitlines()
    heads: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    sections = []
    for idx, (start, level, title) in enumerate(heads):
        end = len(lines)
        for j in range(idx + 1, len(heads)):
            if heads[j][1] <= level:
                end = heads[j][0]
                break
        chunk = "\n".join(lines[start:end])
        sections.append(Section(level, title, start, end, estimate_tokens(chunk)))
    return sections


def get_sections(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    wanted = _fold(heading)
    all_sections = toc(text)
    exact = [s for s in all_sections if _fold(s.title) == wanted]
    hits = exact or [s for s in all_sections if _fold(s.title).startswith(wanted)]
    return ["\n".join(lines[s.start:s.end]) + "\n" for s in hits]


def resolve_page(vault: Path, ident: str) -> Path:
    as_path = vault / ident
    if as_path.suffix == ".md" and as_path.is_file():
        return as_path
    wanted = _fold(ident)
    pages = [p for p in (vault / "wiki").rglob("*.md")]
    exact = [p for p in pages if _fold(p.stem) == wanted]
    if len(exact) == 1:
        return exact[0]
    prefix = [p for p in pages if _fold(p.stem).startswith(wanted)]
    if len(prefix) == 1:
        return prefix[0]
    # last chance: permalink in frontmatter
    for p in pages:
        try:
            meta, _ = frontmatter.load(p)
        except frontmatter.FrontmatterError:
            continue
        if _fold(str(meta.get("permalink", ""))) == wanted:
            return p
    pool = exact or prefix
    if pool:
        names = ", ".join(sorted(p.stem for p in pool)[:8])
        raise ExtractError(f"ambiguous page {ident!r}: {names}")
    raise ExtractError(f"page not found: {ident!r}")
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_extract.py -v`
Expected: 6 PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: extrator de secao com TOC e resolucao de pagina"
```

---

### Task 5: CLI `brain extract`

**Files:**
- Modify: `scripts/brainlib/cli.py`
- Create: `tests/test_cli_extract.py`

**Interfaces:**
- Consumes: `extract.*`, `config.vault_path`
- Produces: `brain extract <pagina> [--heading X] [--toc] [--level N]`; sem flags devolve página inteira se < 8000 tokens estimados, senão TOC + instrução. Constante `cli.FULL_PAGE_TOKEN_LIMIT = 8000`.

- [ ] **Step 1: Testes que falham**

`tests/test_cli_extract.py`:

```python
from brainlib import cli


def test_extract_toc(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Contrato Grande", "--toc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Faturas 2026" in out and "tokens" in out


def test_extract_heading(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Contrato Grande", "--heading", "identificacao"])
    out = capsys.readouterr().out
    assert rc == 0 and "Dados." in out


def test_extract_small_page_returns_full(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Pagina Um"])
    assert rc == 0 and "Texto A." in capsys.readouterr().out


def test_extract_big_page_returns_toc(vault, capsys, monkeypatch):
    big = "# T\n\n" + "".join(f"## Sec {i}\n" + "x" * 2000 + "\n" for i in range(60))
    page = vault / "wiki/sources/Grande.md"
    page.write_text(
        "---\ntype: source\ntitle: \"Grande\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: []\nstatus: mature\n---\n\n" + big,
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    rc = cli.main(["extract", "Grande"])
    out = capsys.readouterr().out
    assert rc == 0 and "--heading" in out and "xxxx" not in out


def test_extract_missing_page(vault, capsys, monkeypatch):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["extract", "Nao Existe"]) == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cli_extract.py -v`
Expected: FAIL (comando não implementado devolve 2)

- [ ] **Step 3: Implementação**

Em `scripts/brainlib/cli.py`, substituir o corpo por dispatch real. Estrutura final do arquivo:

```python
"""obsidian-brain CLI. Exit codes: 0 ok, 1 violation, 2 usage error."""

import argparse
import sys

from . import config, extract

FULL_PAGE_TOKEN_LIMIT = 8000


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brain", description="obsidian-brain CLI")
    p.add_argument("--vault")
    sub = p.add_subparsers(dest="command")

    ext = sub.add_parser("extract")
    ext.add_argument("page")
    ext.add_argument("--heading")
    ext.add_argument("--toc", action="store_true")
    ext.add_argument("--level", type=int, default=None)

    sub.add_parser("validate").add_argument("file")
    lint = sub.add_parser("lint")
    lint.add_argument("--json", action="store_true")
    lint.add_argument("--write", action="store_true")
    sub.add_parser("compile-index")
    sub.add_parser("hot-check")
    fold = sub.add_parser("fold")
    fold.add_argument("--apply", action="store_true")
    return p


def _cmd_extract(args) -> int:
    vault = config.vault_path(args.vault)
    try:
        path = extract.resolve_page(vault, args.page)
    except extract.ExtractError as e:
        print(f"extract: {e}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if args.heading:
        parts = extract.get_sections(text, args.heading)
        if not parts:
            print(f"extract: heading not found: {args.heading!r}", file=sys.stderr)
            return 1
        print(f"\n{'-' * 8}\n".join(parts))
        return 0
    sections = extract.toc(text)
    if args.level:
        sections = [s for s in sections if s.level <= args.level]
    if args.toc or extract.estimate_tokens(text) >= FULL_PAGE_TOKEN_LIMIT:
        rel = path.as_posix()
        print(f"# TOC: {path.stem} ({extract.estimate_tokens(text)} tokens estimados)")
        for s in sections:
            print(f"{'  ' * (s.level - 1)}- {s.title} (~{s.tokens} tokens)")
        if not args.toc:
            print(f"\nPagina grande. Use: brain extract \"{path.stem}\" --heading \"<titulo>\"")
        return 0
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        args = build_parser().parse_args(argv)
    except SystemExit:
        return 2
    try:
        if args.command == "extract":
            return _cmd_extract(args)
    except config.ConfigError as e:
        print(f"config: {e}", file=sys.stderr)
        return 2
    if not args.command:
        print("usage: brain <command>", file=sys.stderr)
        return 2
    print(f"{args.command}: not implemented yet", file=sys.stderr)
    return 2
```

Nota: os testes do Task 1 continuam passando (`main([])` = 2; comando desconhecido cai no `SystemExit` = 2).

- [ ] **Step 4: Rodar tudo e ver passar**

Run: `python -m pytest -v`
Expected: PASS geral

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: subcomando extract no CLI"
```

---

### Task 6: validate.py (schema, hot, index, .raw)

**Files:**
- Create: `scripts/brainlib/validate.py`, `tests/test_validate.py`

**Interfaces:**
- Consumes: `frontmatter.*`
- Produces:
  - `validate.Report` dataclass: `errors: list[str]`, `warnings: list[str]`, propriedade `ok -> bool` (sem errors)
  - `validate.validate_file(vault: Path, path: Path, by_brain: bool = False) -> Report`
  - `validate.check_hot(text: str) -> list[str]` (erros do contrato do hot.md)
  - Constantes: `TYPES`, `STATUSES`, `REQUIRED_KEYS`, `HOT_WORD_LIMIT = 500`
- Regras nesta task: schema universal em `wiki/**.md`; exceções hot/index/log; `folds/**` só parseável; hot.md (500 palavras, sem heading com "anterior"); index.md bloqueado sem `by_brain`; `.raw/` imutável via manifest `.vault-meta/raw-manifest.json`; arquivos não-.md e fora de wiki/.raw = ok silencioso. (log.md e ledger ficam nas Tasks 7 e 8.)

- [ ] **Step 1: Testes que falham**

`tests/test_validate.py`:

```python
import json

from brainlib import validate


def _v(vault, rel, **kw):
    return validate.validate_file(vault, vault / rel, **kw)


def test_good_page_passes(vault):
    assert _v(vault, "wiki/sources/Pagina Um.md").ok


def test_missing_frontmatter_fails(vault):
    p = vault / "wiki/sources/Solta.md"
    p.write_text("# Sem frontmatter\n", encoding="utf-8")
    r = _v(vault, "wiki/sources/Solta.md")
    assert not r.ok and any("frontmatter" in e for e in r.errors)


def test_bad_type_and_status_fail(vault):
    p = vault / "wiki/sources/Ruim.md"
    p.write_text(
        "---\ntype: banana\ntitle: \"R\"\ncreated: 2026-01-01\nupdated: 2025-12-31\n"
        "tags: []\nstatus: verde\n---\ncorpo\n",
        encoding="utf-8",
    )
    r = _v(vault, "wiki/sources/Ruim.md")
    joined = " ".join(r.errors)
    assert "type" in joined and "status" in joined and "updated" in joined


def test_nested_frontmatter_fails(vault):
    p = vault / "wiki/sources/Nested.md"
    p.write_text("---\ntype: source\nmetadata:\n  a: b\n---\ncorpo\n", encoding="utf-8")
    assert not _v(vault, "wiki/sources/Nested.md").ok


def test_hot_over_500_words_fails(vault):
    hot = vault / "wiki/hot.md"
    hot.write_text(
        "---\ntype: meta\ntitle: \"Hot\"\nupdated: 2026-06-01\n---\n\n" + ("palavra " * 501),
        encoding="utf-8",
    )
    r = _v(vault, "wiki/hot.md")
    assert not r.ok and any("500" in e for e in r.errors)


def test_hot_anterior_section_fails(vault):
    hot = vault / "wiki/hot.md"
    hot.write_text(
        "---\ntype: meta\ntitle: \"Hot\"\nupdated: 2026-06-01\n---\n\n"
        "## Last Updated\n\nok\n\n## Last Updated (anterior)\n\nnope\n",
        encoding="utf-8",
    )
    assert not _v(vault, "wiki/hot.md").ok


def test_index_blocked_unless_by_brain(vault):
    assert not _v(vault, "wiki/index.md").ok
    assert _v(vault, "wiki/index.md", by_brain=True).ok


def test_raw_new_ok_edit_fails(vault):
    raw = vault / ".raw" / "artigo.md"
    raw.write_text("original", encoding="utf-8")
    assert _v(vault, ".raw/artigo.md").ok          # first sighting: registered
    assert not _v(vault, ".raw/artigo.md").ok      # second write: immutable
    manifest = json.loads((vault / ".vault-meta/raw-manifest.json").read_text(encoding="utf-8"))
    assert "artigo.md" in manifest["files"]


def test_non_md_ignored(vault):
    (vault / "_attachments").mkdir(exist_ok=True)
    p = vault / "_attachments/foto.png"
    p.write_bytes(b"\x89PNG")
    assert _v(vault, "_attachments/foto.png").ok
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_validate.py -v`
Expected: FAIL

- [ ] **Step 3: Implementação**

`scripts/brainlib/validate.py`:

```python
"""Post-write validation: the safety net behind direct Write."""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import frontmatter

TYPES = {"source", "entity", "concept", "domain", "comparison", "question",
         "overview", "meta", "area", "goal", "person"}
STATUSES = {"seed", "developing", "mature", "evergreen"}
REQUIRED_KEYS = ("type", "title", "created", "updated", "tags", "status")
HOT_WORD_LIMIT = 500
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ANTERIOR = re.compile(r"anterior", re.IGNORECASE)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_date(s: str) -> date | None:
    if not _DATE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def check_schema(meta: dict) -> list[str]:
    errors = []
    for key in REQUIRED_KEYS:
        if key not in meta:
            errors.append(f"missing frontmatter key: {key}")
    if "type" in meta and meta["type"] not in TYPES:
        errors.append(f"invalid type: {meta['type']!r}")
    if "status" in meta and meta["status"] not in STATUSES:
        errors.append(f"invalid status: {meta['status']!r}")
    created = _parse_date(str(meta.get("created", "")))
    updated = _parse_date(str(meta.get("updated", "")))
    if "created" in meta and created is None:
        errors.append(f"created is not YYYY-MM-DD: {meta['created']!r}")
    if "updated" in meta and updated is None:
        errors.append(f"updated is not YYYY-MM-DD: {meta['updated']!r}")
    if created and updated and updated < created:
        errors.append(f"updated {updated} before created {created}")
    return errors


def check_hot(text: str) -> list[str]:
    errors = []
    _, body = frontmatter.split(text)
    words = len(body.split())
    if words > HOT_WORD_LIMIT:
        errors.append(f"hot.md has {words} words (contract: {HOT_WORD_LIMIT}); overwrite, never append")
    for line in body.splitlines():
        if line.startswith("#") and _ANTERIOR.search(line):
            errors.append(f"hot.md has an 'anterior' section: {line.strip()!r}; overwrite the whole file")
    return errors


def _raw_manifest_path(vault: Path) -> Path:
    return vault / ".vault-meta" / "raw-manifest.json"


def _check_raw(vault: Path, rel: str) -> list[str]:
    mp = _raw_manifest_path(vault)
    manifest = {"files": []}
    if mp.exists():
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {"files": []}
    name = rel.split("/", 1)[1] if "/" in rel else rel
    if name in manifest["files"]:
        return [f".raw/ is immutable: {name} already exists; ingest creates, never edits"]
    manifest["files"].append(name)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return []


def validate_file(vault: Path, path: Path, by_brain: bool = False) -> Report:
    r = Report()
    try:
        rel = path.resolve().relative_to(vault.resolve()).as_posix()
    except ValueError:
        return r  # outside vault: not our business
    if rel.startswith(".raw/"):
        r.errors += _check_raw(vault, rel)
        return r
    if not rel.endswith(".md") or not rel.startswith("wiki/"):
        return r
    name = rel[len("wiki/"):]
    if name == "index.md":
        if not by_brain:
            r.errors.append("wiki/index.md is compiled; run 'brain compile-index', never edit it")
        return r
    text = path.read_text(encoding="utf-8")
    if name == "hot.md":
        r.errors += check_hot(text)
        return r
    if name == "log.md":
        return r  # Task 7 adds the append-at-top check here
    block, _ = frontmatter.split(text)
    if block is None:
        r.errors.append(f"no frontmatter in {rel}")
        return r
    try:
        meta = frontmatter.parse(block)
    except frontmatter.FrontmatterError as e:
        r.errors.append(f"frontmatter error in {rel}: {e}")
        return r
    if name.startswith("folds/"):
        return r  # archives: parseable is enough
    r.errors += check_schema(meta)
    return r
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_validate.py -v`
Expected: 9 PASS

- [ ] **Step 5: Wiring no CLI + commit**

Em `cli.py`, no dispatch de `main`, adicionar (o subparser `validate` do Task 5 ganha `--by-brain`):

```python
    val = sub.add_parser("validate")          # substitui a linha do Task 5
    val.add_argument("file")
    val.add_argument("--by-brain", action="store_true")
```

```python
        if args.command == "validate":
            from . import validate as validate_mod
            vault = config.vault_path(args.vault)
            report = validate_mod.validate_file(vault, Path(args.file), by_brain=args.by_brain)
            for w in report.warnings:
                print(f"WARN: {w}")
            for e in report.errors:
                print(f"ERROR: {e}")
            return 0 if report.ok else 1
```

(`from pathlib import Path` no topo do cli.py.) Teste rápido embutido em `tests/test_validate.py`:

```python
def test_cli_validate(vault, monkeypatch, capsys):
    from brainlib import cli
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["validate", str(vault / "wiki/sources/Pagina Um.md")]) == 0
    assert cli.main(["validate", str(vault / "wiki/index.md")]) == 1
```

Run: `python -m pytest -v` — Expected: PASS geral.

```bash
git add -A && git commit -m "feat: validate com schema universal, contrato do hot e guarda de index/.raw"
```

---

### Task 7: log.md append-no-topo (estado persistido)

**Files:**
- Modify: `scripts/brainlib/validate.py`
- Test: `tests/test_validate_log.py`

**Interfaces:**
- Produces:
  - `validate.check_log(vault: Path, text: str, by_brain: bool) -> list[str]`
  - `validate.update_log_state(vault: Path, text: str) -> None` (usada também pelo fold no Task 11)
  - Estado em `.vault-meta/log-state.json`: `{"length": <len do corpo>, "sha256": <hash do corpo>}`
- Mecânica: corpo = texto após frontmatter. Sem estado gravado: registra e passa. Com estado: se `len(novo) >= len(antigo)` e `sha256(novo[-len(antigo):]) == hash antigo`, é append no topo (frontmatter pode mudar), passa e atualiza estado. Qualquer outra coisa: violação, a não ser `by_brain` (fold), que atualiza o estado.

- [ ] **Step 1: Testes que falham**

`tests/test_validate_log.py`:

```python
from brainlib import validate


def _log_text(vault):
    return (vault / "wiki/log.md").read_text(encoding="utf-8")


def test_first_sight_registers_and_passes(vault):
    r = validate.validate_file(vault, vault / "wiki/log.md")
    assert r.ok
    assert (vault / ".vault-meta/log-state.json").exists()


def test_append_at_top_passes(vault):
    validate.validate_file(vault, vault / "wiki/log.md")  # register
    old = _log_text(vault)
    block_end = old.index("\n---", 3) + len("\n---\n")
    new = old[:block_end] + "\n## [2026-06-15] Novissima\n\nx\n" + old[block_end:]
    (vault / "wiki/log.md").write_text(new, encoding="utf-8")
    assert validate.validate_file(vault, vault / "wiki/log.md").ok


def test_middle_edit_fails(vault):
    validate.validate_file(vault, vault / "wiki/log.md")
    tampered = _log_text(vault).replace("Entrada velha", "Entrada adulterada")
    (vault / "wiki/log.md").write_text(tampered, encoding="utf-8")
    r = validate.validate_file(vault, vault / "wiki/log.md")
    assert not r.ok and any("append" in e for e in r.errors)


def test_by_brain_rewrites_state(vault):
    validate.validate_file(vault, vault / "wiki/log.md")
    (vault / "wiki/log.md").write_text("---\ntype: meta\ntitle: \"Log\"\nupdated: 2026-06-20\n---\n\nreescrito\n", encoding="utf-8")
    assert validate.validate_file(vault, vault / "wiki/log.md", by_brain=True).ok
    assert validate.validate_file(vault, vault / "wiki/log.md").ok  # state was refreshed
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_validate_log.py -v`
Expected: FAIL (`test_middle_edit_fails`; os outros passam por acaso porque log.md hoje devolve `Report()` vazio, o que confirma que o teste do middle edit é o que morde)

- [ ] **Step 3: Implementação**

Em `validate.py`, adicionar:

```python
import hashlib


def _log_state_path(vault: Path) -> Path:
    return vault / ".vault-meta" / "log-state.json"


def _body_of(text: str) -> bytes:
    _, body = frontmatter.split(text)
    return body.encode("utf-8")


def update_log_state(vault: Path, text: str) -> None:
    body = _body_of(text)
    p = _log_state_path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"length": len(body), "sha256": hashlib.sha256(body).hexdigest()}),
        encoding="utf-8",
    )


def check_log(vault: Path, text: str, by_brain: bool) -> list[str]:
    sp = _log_state_path(vault)
    if by_brain or not sp.exists():
        update_log_state(vault, text)
        return []
    try:
        state = json.loads(sp.read_text(encoding="utf-8"))
        old_len, old_hash = int(state["length"]), state["sha256"]
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        update_log_state(vault, text)
        return []
    body = _body_of(text)
    if len(body) >= old_len and hashlib.sha256(body[-old_len:]).hexdigest() == old_hash:
        update_log_state(vault, text)
        return []
    return ["wiki/log.md is append-at-top only: existing entries were edited or removed; restore them and prepend the new entry"]
```

E trocar o early-return do log em `validate_file`:

```python
    if name == "log.md":
        r.errors += check_log(vault, text, by_brain)
        return r
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_validate_log.py tests/test_validate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: log.md append-no-topo com estado persistido"
```

---

### Task 8: heurística de cronologia em ledger (aviso)

**Files:**
- Modify: `scripts/brainlib/validate.py`
- Test: `tests/test_validate_ledger.py`

**Interfaces:**
- Produces: `validate.check_ledger_chronology(text: str) -> list[str]` (warnings). Aplica-se a `wiki/areas/**`. Extrai datas de headings `##`/`###` nos formatos `DD/MM/YYYY` e `YYYY-MM-DD`; se a sequência de datas encontrada não for não-decrescente, avisa citando o primeiro heading fora de ordem. Nunca erro, sempre warning.

- [ ] **Step 1: Testes que falham**

`tests/test_validate_ledger.py`:

```python
from brainlib import validate


def test_chronological_ok():
    text = "# L\n\n## Pagamentos 10/03/2026\n\nx\n\n## Pagamentos 15/04/2026\n\ny\n"
    assert validate.check_ledger_chronology(text) == []


def test_out_of_order_warns():
    text = (
        "# L\n\n## Maio (2026-05-01)\n\nx\n\n## Junho (2026-06-01)\n\ny\n\n"
        "## Abril (2026-04-16)\n\nz\n"
    )
    warns = validate.check_ledger_chronology(text)
    assert len(warns) == 1 and "Abril" in warns[0]


def test_headings_without_dates_ignored():
    assert validate.check_ledger_chronology("# L\n\n## Contexto\n\nx\n") == []


def test_area_page_gets_warning_not_error(vault):
    p = vault / "wiki/areas/Contrato Grande.md"
    text = p.read_text(encoding="utf-8").replace(
        "## Identificacao",
        "## Registro 05/06/2026\n\nz\n\n## Registro 01/05/2026",
    )
    p.write_text(text, encoding="utf-8")
    r = validate.validate_file(vault, p)
    assert r.ok and len(r.warnings) == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_validate_ledger.py -v`
Expected: FAIL, `AttributeError: check_ledger_chronology`

- [ ] **Step 3: Implementação**

Em `validate.py`:

```python
_H_DATE_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_H_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _heading_date(line: str) -> date | None:
    m = _H_DATE_ISO.search(line)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _H_DATE_BR.search(line)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def check_ledger_chronology(text: str) -> list[str]:
    last: date | None = None
    for line in text.splitlines():
        if not line.startswith(("## ", "### ")):
            continue
        d = _heading_date(line)
        if d is None:
            continue
        if last is not None and d < last:
            return [
                f"ledger chronology: {line.strip()!r} ({d}) comes after a newer entry ({last}); "
                "insert records in chronological position, do not blind-append"
            ]
        last = d
    return []
```

E no fim de `validate_file`, antes do `return r` final (depois de `check_schema`):

```python
    if name.startswith("areas/"):
        r.warnings += check_ledger_chronology(text)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest -v`
Expected: PASS geral

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: aviso de cronologia em paginas ledger de areas"
```

---

### Task 9: index.py (port do compile_index) + `brain compile-index` + `brain hot-check`

**Files:**
- Create: `scripts/brainlib/index.py`, `tests/test_index.py`
- Modify: `scripts/brainlib/cli.py`

**Interfaces:**
- Consumes: `frontmatter`, `validate.check_hot`
- Produces:
  - `index.compile(vault: Path) -> str` mensagem de resumo; grava `wiki/index.md`
  - Comportamento idêntico ao `_scripts/compile_index.py` do vault: pula `index.md`, `hot.md`, `log.md` na raiz e o dir `folds/`; agrupa por pasta de 1º nível; linha `- [[stem]] (type, status, updated)`; frontmatter `type: meta` + `generated:`; total no cabeçalho
  - CLI `compile-index` (chama `index.compile`) e `hot-check` (roda `validate.check_hot` no hot.md, exit 1 se viola)

- [ ] **Step 1: Testes que falham**

`tests/test_index.py`:

```python
from brainlib import cli, index


def test_compile_lists_pages_by_folder(vault):
    index.compile(vault)
    out = (vault / "wiki/index.md").read_text(encoding="utf-8")
    assert "## areas (1)" in out
    assert "- [[Contrato Grande]] (area, mature, 2026-06-01)" in out
    assert "hot" not in out.split("## ")[0].lower() or "[[hot]]" not in out


def test_compile_skips_folds(vault):
    (vault / "wiki/folds/arquivo-velho.md").write_text(
        "---\ntype: meta\ntitle: \"X\"\n---\ncorpo", encoding="utf-8"
    )
    index.compile(vault)
    assert "arquivo-velho" not in (vault / "wiki/index.md").read_text(encoding="utf-8")


def test_compile_is_idempotent_module_date(vault, monkeypatch):
    index.compile(vault)
    first = (vault / "wiki/index.md").read_text(encoding="utf-8")
    index.compile(vault)
    assert first == (vault / "wiki/index.md").read_text(encoding="utf-8")


def test_cli_compile_and_hot_check(vault, monkeypatch, capsys):
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["compile-index"]) == 0
    assert cli.main(["hot-check"]) == 0
    (vault / "wiki/hot.md").write_text(
        "---\ntype: meta\ntitle: \"Hot\"\nupdated: 2026-06-01\n---\n\n" + "w " * 501,
        encoding="utf-8",
    )
    assert cli.main(["hot-check"]) == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_index.py -v`
Expected: FAIL

- [ ] **Step 3: Implementação**

`scripts/brainlib/index.py`:

```python
"""Compile wiki/index.md from page frontmatter. Human navigation artifact:
LLM sessions search via basic-memory instead of loading this file."""

from datetime import date
from pathlib import Path

from . import frontmatter

SKIP_FILES = {"index.md", "hot.md", "log.md"}
SKIP_DIRS = {"folds"}


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
```

Obs. sobre `test_compile_is_idempotent_module_date`: as duas execuções acontecem no mesmo dia, então o `updated:` não muda e o arquivo é byte-idêntico. Não mockar `date.today`.

No `cli.py`, dispatch:

```python
        if args.command == "compile-index":
            from . import index as index_mod
            print(index_mod.compile(config.vault_path(args.vault)))
            return 0
        if args.command == "hot-check":
            from . import validate as validate_mod
            hot = config.vault_path(args.vault) / "wiki" / "hot.md"
            errors = validate_mod.check_hot(hot.read_text(encoding="utf-8")) if hot.exists() else []
            for e in errors:
                print(f"ERROR: {e}")
            if not errors:
                print("hot.md ok")
            return 0 if not errors else 1
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest -v`
Expected: PASS geral

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: compile-index portado e hot-check no CLI"
```

---

### Task 10: lint.py + `brain lint`

**Files:**
- Create: `scripts/brainlib/lint.py`, `tests/test_lint.py`
- Modify: `scripts/brainlib/cli.py`

**Interfaces:**
- Consumes: `frontmatter`, `validate.check_schema`, `validate.check_hot`
- Produces:
  - `lint.Finding` dataclass: `severity: str` (`error|warning|info`), `path: str` (relativo ao vault), `message: str`
  - `lint.run(vault: Path) -> list[Finding]`
  - Checks: wikilinks mortos (warning), páginas órfãs sem inbound link (info; exclui `meta/`, `folds/`, raiz de wiki), frontmatter inválido/schema (error), seção vazia (warning), callout `[!stale]` presente (info), contrato do hot (error), index desatualizado (warning: qualquer página com mtime > mtime do index, ou contagem de `- [[` diferente do nº real de páginas)
  - CLI: `brain lint [--json] [--write]`; exit 1 se houver `error`, 0 caso contrário; `--write` grava `wiki/meta/lint-report.md`

- [ ] **Step 1: Testes que falham**

`tests/test_lint.py`:

```python
import json as jsonlib

from brainlib import cli, index, lint


def _sev(findings, s):
    return [f for f in findings if f.severity == s]


def test_dead_wikilink_detected(vault):
    p = vault / "wiki/sources/ComLinkMorto.md"
    p.write_text(
        "---\ntype: source\ntitle: \"ComLinkMorto\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: []\nstatus: seed\n---\n\nVer [[Pagina Fantasma]].\n",
        encoding="utf-8",
    )
    index.compile(vault)
    findings = lint.run(vault)
    assert any("Pagina Fantasma" in f.message for f in _sev(findings, "warning"))


def test_orphan_detected(vault):
    index.compile(vault)
    findings = lint.run(vault)
    # Pagina Um links Contrato Grande; nothing links Pagina Um -> orphan info
    assert any("Pagina Um" in f.message for f in _sev(findings, "info"))


def test_empty_section_detected(vault):
    p = vault / "wiki/concepts/Vazio.md"
    p.write_text(
        "---\ntype: concept\ntitle: \"Vazio\"\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: []\nstatus: seed\n---\n\n# Vazio\n\n## Secao Vazia\n\n## Outra\n\ntexto\n",
        encoding="utf-8",
    )
    index.compile(vault)
    findings = lint.run(vault)
    assert any("Secao Vazia" in f.message for f in findings)


def test_bad_schema_is_error_and_exit_1(vault, monkeypatch):
    (vault / "wiki/sources/Quebrada.md").write_text("---\ntype: banana\n---\nx\n", encoding="utf-8")
    index.compile(vault)
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    assert cli.main(["lint"]) == 1


def test_json_output(vault, monkeypatch, capsys):
    index.compile(vault)
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    cli.main(["lint", "--json"])
    data = jsonlib.loads(capsys.readouterr().out)
    assert isinstance(data, list) and all("severity" in f for f in data)


def test_write_report(vault, monkeypatch):
    index.compile(vault)
    monkeypatch.setenv("BRAIN_VAULT", str(vault))
    cli.main(["lint", "--write"])
    report = vault / "wiki/meta/lint-report.md"
    assert report.exists()
    assert report.read_text(encoding="utf-8").startswith("---")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_lint.py -v`
Expected: FAIL

- [ ] **Step 3: Implementação**

`scripts/brainlib/lint.py`:

```python
"""Deterministic vault health checks. Read-only unless --write."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import frontmatter, validate

_WIKILINK = re.compile(r"\[\[([^\]\|#]+)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_STALE = re.compile(r"\[!stale\]", re.IGNORECASE)


@dataclass
class Finding:
    severity: str  # error | warning | info
    path: str
    message: str

    def to_dict(self) -> dict:
        return {"severity": self.severity, "path": self.path, "message": self.message}


def _pages(vault: Path) -> list[Path]:
    wiki = vault / "wiki"
    out = []
    for p in sorted(wiki.rglob("*.md")):
        rel = p.relative_to(wiki)
        if rel.name in {"index.md", "hot.md", "log.md"} and len(rel.parts) == 1:
            continue
        if rel.parts[0] == "folds":
            continue
        out.append(p)
    return out


def run(vault: Path) -> list[Finding]:
    wiki = vault / "wiki"
    pages = _pages(vault)
    stems = {p.stem.casefold(): p for p in pages}
    inbound: set[str] = set()
    findings: list[Finding] = []

    for p in pages:
        rel = p.relative_to(vault).as_posix()
        text = p.read_text(encoding="utf-8")
        block, body = frontmatter.split(text)
        if block is None:
            findings.append(Finding("error", rel, "no frontmatter"))
            continue
        try:
            meta = frontmatter.parse(block)
            for e in validate.check_schema(meta):
                findings.append(Finding("error", rel, e))
        except frontmatter.FrontmatterError as e:
            findings.append(Finding("error", rel, f"frontmatter: {e}"))

        for target in _WIKILINK.findall(body):
            t = target.strip().casefold()
            if t in stems:
                inbound.add(t)
            else:
                findings.append(Finding("warning", rel, f"dead wikilink: [[{target.strip()}]]"))

        lines = body.splitlines()
        heads = [(i, len(m.group(1)), m.group(2)) for i, l in enumerate(lines) if (m := _HEADING.match(l))]
        for idx, (i, level, title) in enumerate(heads):
            nxt = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
            if not any(l.strip() for l in lines[i + 1:nxt]):
                if idx + 1 < len(heads) and heads[idx + 1][1] > level:
                    continue  # parent heading followed by subsection is fine
                findings.append(Finding("warning", rel, f"empty section: {title!r}"))

        if _STALE.search(body):
            findings.append(Finding("info", rel, "has [!stale] marker to revisit"))

    for p in pages:
        rel_parts = p.relative_to(wiki).parts
        if rel_parts[0] in {"meta",} or len(rel_parts) == 1:
            continue
        if p.stem.casefold() not in inbound:
            findings.append(Finding("info", p.relative_to(vault).as_posix(), f"orphan page: {p.stem} has no inbound links"))

    hot = wiki / "hot.md"
    if hot.exists():
        for e in validate.check_hot(hot.read_text(encoding="utf-8")):
            findings.append(Finding("error", "wiki/hot.md", e))

    idx_file = wiki / "index.md"
    if not idx_file.exists():
        findings.append(Finding("warning", "wiki/index.md", "index missing; run 'brain compile-index'"))
    else:
        idx_mtime = idx_file.stat().st_mtime
        if any(p.stat().st_mtime > idx_mtime for p in pages):
            findings.append(Finding("warning", "wiki/index.md", "index older than newest page; run 'brain compile-index'"))
        listed = idx_file.read_text(encoding="utf-8").count("- [[")
        if listed != len(pages):
            findings.append(Finding("warning", "wiki/index.md", f"index lists {listed} pages, vault has {len(pages)}"))
    return findings


def report_markdown(findings: list[Finding]) -> str:
    today = date.today().isoformat()
    lines = [
        "---", "type: meta", 'title: "Lint Report"', f"created: {today}",
        f"updated: {today}", "tags: [lint]", "status: seed", "---", "",
        f"# Lint Report ({today})", "",
    ]
    if not findings:
        lines.append("Sem achados.")
    for f in findings:
        lines.append(f"- **{f.severity}** `{f.path}`: {f.message}")
    return "\n".join(lines) + "\n"
```

CLI dispatch:

```python
        if args.command == "lint":
            import json as jsonlib
            from . import lint as lint_mod
            vault = config.vault_path(args.vault)
            findings = lint_mod.run(vault)
            if args.json:
                print(jsonlib.dumps([f.to_dict() for f in findings], ensure_ascii=True, indent=1))
            else:
                for f in findings:
                    print(f"{f.severity.upper()}: {f.path}: {f.message}")
                print(f"{len(findings)} findings")
            if args.write:
                out = vault / "wiki" / "meta" / "lint-report.md"
                out.write_text(lint_mod.report_markdown(findings), encoding="utf-8")
            return 1 if any(f.severity == "error" for f in findings) else 0
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest -v`
Expected: PASS geral. Atenção a um detalhe do fixture: `test_orphan_detected` exige que `Contrato Grande` receba link de `Pagina Um` (o fixture já tem `[[Contrato Grande]]`).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: lint deterministico com report opcional"
```

---

### Task 11: fold.py + `brain fold`

**Files:**
- Create: `scripts/brainlib/fold.py`, `tests/test_fold.py`
- Modify: `scripts/brainlib/cli.py`

**Interfaces:**
- Consumes: `frontmatter`, `validate.update_log_state`
- Produces:
  - `fold.plan(vault: Path, keep_days: int = 30, today: date | None = None) -> FoldPlan`
  - `FoldPlan` dataclass: `keep: list[str]` (entradas que ficam), `archive: dict[str, list[str]]` (chave `YYYY-MM`, entradas que saem), `summary() -> str`
  - `fold.apply(vault: Path, fp: FoldPlan) -> str`: grava/append `wiki/folds/log-archive-YYYY-MM.md`, reescreve `log.md` com as entradas mantidas, chama `validate.update_log_state`
  - Entrada de log = bloco começando em `## [YYYY-MM-DD]` até a próxima entrada
  - CLI: `brain fold` (dry-run, imprime `summary()`), `brain fold --apply`

- [ ] **Step 1: Testes que falham**

`tests/test_fold.py`:

```python
from datetime import date

from brainlib import fold, validate


TODAY = date(2026, 6, 20)


def test_plan_splits_by_age(vault):
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    assert len(fp.keep) == 1 and "2026-06-01" in fp.keep[0]
    assert list(fp.archive) == ["2026-05"]
    assert "2026-05-01" in fp.archive["2026-05"][0]


def test_dry_run_does_not_touch_files(vault):
    before = (vault / "wiki/log.md").read_text(encoding="utf-8")
    fold.plan(vault, keep_days=30, today=TODAY)
    assert (vault / "wiki/log.md").read_text(encoding="utf-8") == before
    assert not list((vault / "wiki/folds").glob("log-archive-*.md"))


def test_apply_moves_and_updates_state(vault):
    validate.validate_file(vault, vault / "wiki/log.md")  # register state
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    fold.apply(vault, fp)
    log = (vault / "wiki/log.md").read_text(encoding="utf-8")
    assert "2026-05-01" not in log and "2026-06-01" in log
    archive = (vault / "wiki/folds/log-archive-2026-05.md").read_text(encoding="utf-8")
    assert "Entrada velha" in archive
    # rewritten log passes validation because apply refreshed the state
    assert validate.validate_file(vault, vault / "wiki/log.md").ok


def test_apply_appends_to_existing_archive(vault):
    arch = vault / "wiki/folds/log-archive-2026-05.md"
    arch.write_text("---\ntype: meta\ntitle: \"Log Archive 2026-05\"\n---\n\n## [2026-05-20] Ja arquivada\n\nx\n", encoding="utf-8")
    fp = fold.plan(vault, keep_days=30, today=TODAY)
    fold.apply(vault, fp)
    text = arch.read_text(encoding="utf-8")
    assert "Ja arquivada" in text and "Entrada velha" in text
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_fold.py -v`
Expected: FAIL

- [ ] **Step 3: Implementação**

`scripts/brainlib/fold.py`:

```python
"""Extractive rollup: move old log.md entries into wiki/folds/ archives."""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import frontmatter, validate

_ENTRY = re.compile(r"^## \[(\d{4})-(\d{2})-(\d{2})\]", re.MULTILINE)


@dataclass
class FoldPlan:
    fm_block: str
    keep: list[str] = field(default_factory=list)
    archive: dict[str, list[str]] = field(default_factory=dict)

    def summary(self) -> str:
        moved = sum(len(v) for v in self.archive.values())
        months = ", ".join(sorted(self.archive)) or "-"
        return f"fold: keep {len(self.keep)} entries; archive {moved} entries into months: {months}"


def _entries(body: str) -> list[tuple[date, str]]:
    marks = list(_ENTRY.finditer(body))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        out.append((d, body[m.start():end].rstrip() + "\n"))
    return out


def plan(vault: Path, keep_days: int = 30, today: date | None = None) -> FoldPlan:
    today = today or date.today()
    cutoff = today - timedelta(days=keep_days)
    text = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    block, body = frontmatter.split(text)
    fp = FoldPlan(fm_block=block or "type: meta\ntitle: \"Log\"")
    for d, entry in _entries(body):
        if d >= cutoff:
            fp.keep.append(entry)
        else:
            fp.archive.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(entry)
    return fp


def apply(vault: Path, fp: FoldPlan) -> str:
    folds = vault / "wiki" / "folds"
    folds.mkdir(parents=True, exist_ok=True)
    for month, entries in sorted(fp.archive.items()):
        target = folds / f"log-archive-{month}.md"
        if target.exists():
            base = target.read_text(encoding="utf-8").rstrip() + "\n\n"
        else:
            base = (
                f"---\ntype: meta\ntitle: \"Log Archive {month}\"\n"
                f"created: {date.today().isoformat()}\nupdated: {date.today().isoformat()}\n"
                "tags: [log-archive]\nstatus: evergreen\n---\n\n"
            )
        target.write_text(base + "\n".join(entries) + "\n", encoding="utf-8")
    new_log = "---\n" + fp.fm_block.strip() + "\n---\n\n" + "\n".join(fp.keep) + "\n"
    (vault / "wiki" / "log.md").write_text(new_log, encoding="utf-8")
    validate.update_log_state(vault, new_log)
    return fp.summary()
```

CLI dispatch:

```python
        if args.command == "fold":
            from . import fold as fold_mod
            vault = config.vault_path(args.vault)
            fp = fold_mod.plan(vault)
            if args.apply:
                print(fold_mod.apply(vault, fp))
            else:
                print(fp.summary())
                print("dry-run; use 'brain fold --apply' to execute")
            return 0
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest -v`
Expected: PASS geral

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: fold do log.md para arquivos mensais em folds/"
```

---

### Task 12: hook validate-write.py + hooks.json

**Files:**
- Create: `hooks/hooks.json`, `hooks/validate-write.py`, `tests/test_hooks.py`

**Interfaces:**
- Consumes: CLI `brain validate` via subprocess (`sys.executable scripts/brain.py validate <file>`)
- Produces:
  - `hooks/validate-write.py`: lê evento JSON no stdin (`tool_input.file_path`); fora do vault ou config ausente = exit 0 silencioso; violação = stdout JSON `{"decision": "block", "reason": "<erros>"}` e exit 0; warnings = stdout JSON `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "<warns>"}}`
  - Vault resolvido por `BRAIN_VAULT` ou `~/.claude/brain.json` (mesma precedência do CLI)
  - Nunca lança exceção para fora: qualquer erro interno = stderr + exit 0

- [ ] **Step 1: Testes que falham**

`tests/test_hooks.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_hooks.py -v`
Expected: FAIL (hook não existe)

- [ ] **Step 3: Implementação**

`hooks/validate-write.py`:

```python
"""PostToolUse hook: validate every Write/Edit that lands inside the vault.

Contract: NEVER break the session. Internal errors exit 0 with a stderr
note; only real validation violations emit {"decision": "block"}.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRAIN = REPO / "scripts" / "brain.py"


def _vault() -> Path | None:
    raw = os.environ.get("BRAIN_VAULT")
    if not raw:
        cfg = Path.home() / ".claude" / "brain.json"
        if not cfg.exists():
            return None
        try:
            raw = json.loads(cfg.read_text(encoding="utf-8")).get("vault")
        except (OSError, json.JSONDecodeError):
            return None
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def main() -> int:
    try:
        event = json.load(sys.stdin)
        file_path = event.get("tool_input", {}).get("file_path")
        vault = _vault()
        if not file_path or vault is None:
            return 0
        target = Path(file_path)
        try:
            target.resolve().relative_to(vault.resolve())
        except ValueError:
            return 0
        proc = subprocess.run(
            [sys.executable, str(BRAIN), "--vault", str(vault), "validate", str(target)],
            capture_output=True, text=True, timeout=60,
        )
        errors = [l for l in proc.stdout.splitlines() if l.startswith("ERROR: ")]
        warns = [l for l in proc.stdout.splitlines() if l.startswith("WARN: ")]
        if proc.returncode == 1 and errors:
            print(json.dumps({"decision": "block", "reason": "\n".join(errors)}))
        elif warns:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n".join(warns),
            }}))
        return 0
    except Exception as e:  # noqa: BLE001 - hook must never break the session
        print(f"validate-write hook error (ignored): {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

`hooks/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/validate-write.py\"",
            "timeout": 90
          },
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/recompile-index.py\"",
            "timeout": 90
          }
        ]
      }
    ]
  }
}
```

(O segundo comando ainda não existe; criar `hooks/recompile-index.py` vazio com `exit 0` provisório para não quebrar, ou deixar o arquivo para a Task 13 e só declarar no hooks.json na Task 13. Escolher: declarar os dois já e criar o recompile provisório:)

```python
import sys
sys.exit(0)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_hooks.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: hook de validacao de escrita no vault"
```

---

### Task 13: hook recompile-index.py com debounce

**Files:**
- Modify: `hooks/recompile-index.py`
- Test: `tests/test_hook_recompile.py`

**Interfaces:**
- Consumes: CLI `brain compile-index` via subprocess
- Produces: hook que, para Write/Edit sob `<vault>/wiki/`, toca `.vault-meta/index-dirty` e recompila se a última compilação (mtime de `wiki/index.md`) tiver mais de 30s OU se o index não existir. Falha nunca bloqueia: loga em `.vault-meta/brain.log`, exit 0. Fora de `wiki/` = no-op.

- [ ] **Step 1: Testes que falham**

`tests/test_hook_recompile.py`:

```python
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "recompile-index.py"


def _run(event, vault):
    env = dict(os.environ, BRAIN_VAULT=str(vault))
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, env=env, timeout=60)


def test_wiki_write_compiles_when_index_stale(vault):
    idx = vault / "wiki/index.md"
    old = time.time() - 3600
    os.utime(idx, (old, old))
    page = vault / "wiki/sources/Pagina Um.md"
    r = _run({"tool_input": {"file_path": str(page)}}, vault)
    assert r.returncode == 0
    assert "obsidian-brain" in idx.read_text(encoding="utf-8")  # recompiled by us


def test_recent_index_only_marks_dirty(vault):
    idx = vault / "wiki/index.md"
    idx.write_text("fresh", encoding="utf-8")  # mtime = now
    page = vault / "wiki/sources/Pagina Um.md"
    r = _run({"tool_input": {"file_path": str(page)}}, vault)
    assert r.returncode == 0
    assert idx.read_text(encoding="utf-8") == "fresh"
    assert (vault / ".vault-meta/index-dirty").exists()


def test_outside_wiki_is_noop(vault):
    r = _run({"tool_input": {"file_path": str(vault / ".raw/x.md")}}, vault)
    assert r.returncode == 0
    assert not (vault / ".vault-meta/index-dirty").exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_hook_recompile.py -v`
Expected: FAIL (hook provisório não faz nada)

- [ ] **Step 3: Implementação**

`hooks/recompile-index.py`:

```python
"""PostToolUse hook: keep wiki/index.md compiled, with a 30s debounce."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRAIN = REPO / "scripts" / "brain.py"
DEBOUNCE_SECONDS = 30


def _vault() -> Path | None:
    raw = os.environ.get("BRAIN_VAULT")
    if not raw:
        cfg = Path.home() / ".claude" / "brain.json"
        if not cfg.exists():
            return None
        try:
            raw = json.loads(cfg.read_text(encoding="utf-8")).get("vault")
        except (OSError, json.JSONDecodeError):
            return None
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def main() -> int:
    try:
        event = json.load(sys.stdin)
        file_path = event.get("tool_input", {}).get("file_path")
        vault = _vault()
        if not file_path or vault is None:
            return 0
        try:
            rel = Path(file_path).resolve().relative_to(vault.resolve()).as_posix()
        except ValueError:
            return 0
        if not rel.startswith("wiki/") or rel == "wiki/index.md":
            return 0
        meta = vault / ".vault-meta"
        meta.mkdir(exist_ok=True)
        dirty = meta / "index-dirty"
        dirty.write_text(str(time.time()), encoding="utf-8")
        idx = vault / "wiki" / "index.md"
        if idx.exists() and time.time() - idx.stat().st_mtime < DEBOUNCE_SECONDS:
            return 0  # too soon; next hook run picks it up
        proc = subprocess.run(
            [sys.executable, str(BRAIN), "--vault", str(vault), "compile-index"],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode == 0:
            dirty.unlink(missing_ok=True)
        else:
            with (meta / "brain.log").open("a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] compile-index rc={proc.returncode}: {proc.stderr.strip()}\n")
        return 0
    except Exception as e:  # noqa: BLE001 - hook must never break the session
        print(f"recompile-index hook error (ignored): {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar tudo e ver passar**

Run: `python -m pytest -v`
Expected: PASS geral

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: hook de recompilacao do index com debounce de 30s"
```

---

### Task 14: as 6 skills

**Files:**
- Create: `skills/save/SKILL.md`, `skills/query/SKILL.md`, `skills/ingest/SKILL.md`, `skills/lint/SKILL.md`, `skills/fold/SKILL.md`, `skills/hot-cache/SKILL.md`

**Interfaces:**
- Consumes: CLI `brain` (os hooks fazem o enforcement; as skills só orientam o julgamento). Comando canônico dentro das skills: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" <cmd>` (quando a skill roda via plugin, `CLAUDE_PLUGIN_ROOT` existe; fallback: localizar `brain.py` pelo path do próprio SKILL.md, dois níveis acima em `scripts/`).
- Produces: skills invocáveis; sem passo de "rodar compile_index" manual em nenhuma delas (hook cuida).

Sem teste unitário aqui; verificação é estrutural (frontmatter de skill válido) e manual no fim (Task 15). Conteúdo integral dos 6 arquivos:

- [ ] **Step 1: `skills/query/SKILL.md`**

```markdown
---
name: query
description: Responder perguntas a partir do vault Obsidian (second brain). Use quando o usuário pedir "consulte o vault", "query o vault", "o que sabemos sobre X", "procure no vault". Fluxo: hot.md, busca basic-memory, extrator de seção. Somente leitura.
---

# Query do vault

Responda a partir do vault, sem modificar nenhum arquivo dele.

1. Leia `wiki/hot.md` (contexto recente, barato).
2. Busque com basic-memory: tool MCP `search_notes` (projeto `work`); sem MCP, CLI `basic-memory tool search-notes --query "<termos>"`; sem basic-memory, Grep no vault (`wiki/**/*.md`).
3. NUNCA carregue `wiki/index.md` ou `wiki/log.md` inteiros; log só via `grep "^## \[" wiki/log.md`.
4. Página candidata grande? NÃO leia inteira:
   - `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" extract "<pagina>" --toc`
   - depois `... extract "<pagina>" --heading "<secao>"`
   Páginas pequenas o extract devolve inteiras sozinho.

Regras de evidência:
- Cite a fonte mais específica: `[[Página#Heading]]`.
- Separe explicitamente o que é evidência do vault do que é inferência sua.
- Duas páginas divergindo sobre o mesmo fato: apresente as duas com as datas `updated`, aponte qual é mais recente, não escolha calado.
- O vault não cobre a pergunta: diga o que falta e pare. Não preencha com memória do modelo.
```

- [ ] **Step 2: `skills/save/SKILL.md`**

```markdown
---
name: save
description: Salvar conteúdo da conversa no vault Obsidian (second brain). Use com "/save", "salve no vault", "anote no vault", "registre isso". Decide tipo, pasta e formato; escreve com o tool Write; hooks validam e recompilam o index.
---

# Save no vault

O usuário escolheu o que preservar. Seu trabalho é julgamento: o que, onde e como. A validação é dos hooks, não sua.

1. **O quê**: destile o conteúdo aprovado (decisão, análise, sessão). Não despeje transcript.
2. **Onde** (pasta canônica em `wiki/`): sessão/snapshot em `sources/` (nome `Sessao YYYY-MM-DD <tema>.md`), decisão/conceito em `concepts/`, contrato/pendência viva em `areas/`, pessoa em `people/`. ANTES de criar, busque no basic-memory se já existe página para atualizar. Update vence create.
3. **Como**: frontmatter universal (`type,title,created,updated,tags,status`, sem nested objects), wikilinks `[[Assim]]`, filename Title Case.
4. **Ledger** (páginas de `areas/` com registros datados): inserir o registro na posição cronológica correta, consolidar com a seção existente do mesmo período, atualizar título de seção que cite período. Regra completa: CLAUDE.md do vault, seção "Ledgers e páginas datadas". Nunca append cego no fim.
5. **log.md**: adicione a entrada nova NO TOPO (`## [YYYY-MM-DD] Título`), corpo antigo intocado.
6. **hot.md**: se o fato muda o contexto quente, reescreva o hot.md INTEIRO (contrato de 500 palavras; skill hot-cache).

Não rode compile-index manualmente; o hook recompila sozinho.
```

- [ ] **Step 3: `skills/ingest/SKILL.md`**

```markdown
---
name: ingest
description: Ingerir um source (arquivo em .raw/, texto colado, transcript) no vault Obsidian criando/atualizando páginas atômicas. Use com "ingest <arquivo>", "processa esse source", "ingere isso no vault".
---

# Ingest de source

1. Source é arquivo? Mova/copie para `.raw/` primeiro (imutável: nunca edite um arquivo existente lá; o validador bloqueia).
2. Leia o source inteiro e liste os fatos/entidades/decisões que merecem página.
3. Para CADA candidato: busque no basic-memory se já existe página. Existir = atualizar (update-não-duplica). Página nova só para conceito realmente novo.
4. Páginas atômicas: uma página, um assunto. Frontmatter universal + `sources:` apontando o arquivo em `.raw/` (provenance).
5. Wikilinks entre as páginas tocadas; entrada nova no topo do `log.md` (`## [YYYY-MM-DD] Ingest: <source>`) listando páginas criadas/atualizadas.
6. Batch ("ingest all of these") = repetir por source, um de cada vez, mesmo rigor.

Hooks validam cada escrita e recompilam o index; não rode compile-index manualmente.
```

- [ ] **Step 4: `skills/lint/SKILL.md`**

```markdown
---
name: lint
description: Health check do vault Obsidian. Use com "lint the wiki", "lint o vault", "saúde do vault", "checa o vault". Roda o linter determinístico e interpreta; propor fix é separado de aplicar.
---

# Lint do vault

1. Rode: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" lint --json`
2. Agrupe por severidade. `error` = quebra contrato (schema, hot.md); `warning` = degradação (link morto, seção vazia, index velho); `info` = revisão humana (órfã, [!stale]).
3. Interprete: separe o que é fix mecânico (rodar compile-index, corrigir frontmatter) do que exige decisão do usuário (órfã pode ser intencional).
4. Proponha os fixes. SÓ aplique após aprovação explícita. Relatório persistido: `... lint --write` grava `wiki/meta/lint-report.md`.
```

- [ ] **Step 5: `skills/fold/SKILL.md`**

```markdown
---
name: fold
description: Compactar o log.md do vault movendo entradas antigas para arquivos mensais em wiki/folds/. Use com "fold the log", "compacta o log", "arquiva o log".
---

# Fold do log

1. Preview: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" fold` (dry-run; mostra quantas entradas ficam e quantas vão para cada `log-archive-YYYY-MM.md`).
2. Mostre o resumo ao usuário.
3. SÓ com aprovação: `... fold --apply`. O apply reescreve o log.md e atualiza o estado de validação sozinho.
```

- [ ] **Step 6: `skills/hot-cache/SKILL.md`**

```markdown
---
name: hot-cache
description: Atualizar o wiki/hot.md do vault (contexto quente, contrato de 500 palavras). Use com "update hot cache", "atualiza o hot", "refresh do hot.md".
---

# Hot cache

Contrato: `wiki/hot.md` tem NO MÁXIMO 500 palavras e é SOBRESCRITO por inteiro. Nunca existe seção "anterior".

1. Arquive a versão atual: append do conteúdo (sem frontmatter) em `wiki/folds/hot-cache-archive-<YYYY-Qn>.md` (crie com frontmatter `type: meta` se não existir).
2. Reescreva `wiki/hot.md` inteiro: seções `## Last Updated` (parágrafo único do estado atual), `## Key Recent Facts` (fatos datados, 1 linha cada), `## Active Threads` (pendências vivas). Poder de síntese: o que saiu do hot continua acessível via busca.
3. Confira: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" hot-check` (exit 0 = dentro do contrato).
```

- [ ] **Step 7: Verificação estrutural + commit**

Run: `python -c "from pathlib import Path; [print(p) for p in Path('skills').rglob('SKILL.md')]"` (deve listar 6)

```bash
git add -A && git commit -m "feat: seis skills de julgamento (save/query/ingest/lint/fold/hot-cache)"
```

---

### Task 15: instalação real, smoke E2E e cutover

**Files:**
- Modify: `README.md` (status), `~/.claude/brain.json` (criar), vault `CLAUDE.md`, vault `_scripts/compile_index.py` (stub), `~/.claude/CLAUDE.md` (global), memória do projeto

Esta task toca ambiente real e arquivos fora do repo: executar com o usuário acompanhando, um passo por vez.

- [ ] **Step 1: Config real**

Criar `~/.claude/brain.json`:

```json
{ "vault": "C:\\path\\to\\vault" }
```

- [ ] **Step 2: Instalar plugin**

```bash
claude plugin marketplace add C:\drive-d\projetos\obsidian-brain
claude plugin install obsidian-brain@obsidian-brain-marketplace
```

- [ ] **Step 3: Smoke no vault real (somente leitura primeiro)**

```bash
python scripts/brain.py extract "Contrato 071-2024 SEMA-FUNADIF" --toc
python scripts/brain.py lint | tail -5
python scripts/brain.py hot-check
python scripts/brain.py fold           # dry-run
```

Expected: TOC da página de 251KB em segundos; lint termina sem traceback (achados são esperados num vault real); hot-check 0; fold mostra plano sem tocar arquivo.

- [ ] **Step 4: Smoke dos hooks em sessão nova do Claude Code**

Numa sessão nova: pedir uma edição trivial numa página de teste do vault (criar `wiki/sources/Teste Brain.md` válida, depois uma inválida sem frontmatter). Expected: a válida passa; a inválida volta com feedback de bloqueio no turno. Apagar as páginas de teste depois.

- [ ] **Step 5: Cutover**

```bash
claude plugin uninstall claude-obsidian
```

Depois, com aprovação do usuário em cada arquivo:

1. Vault `CLAUDE.md`: seção "Skills e Comandos do Plugin" reescrita para os comandos do brain (`/save`, "query o vault", "ingest X", "lint the wiki", "fold the log", "update hot cache"); remover menções ao plugin `claude-obsidian`/`v1.6.0`; trocar "rodar `python _scripts/compile_index.py`" por "o hook recompila sozinho".
2. Vault `_scripts/compile_index.py` vira stub:

```python
#!/usr/bin/env python3
"""Moved into the obsidian-brain plugin. Kept as a pointer because vault
pages still reference this path."""
print("compile_index moved: use 'brain compile-index' (obsidian-brain plugin); the plugin hook also runs it automatically")
```

3. `~/.claude/CLAUDE.md` global, seção "Vault Obsidian — Second Brain (Work)": triggers de escrita passam a citar a skill `save` do obsidian-brain; leitura cita a skill `query`.
4. Memória do projeto: atualizar `claude_obsidian_vault_nunca_readotado.md` com o desfecho (substituído pelo obsidian-brain em <data>) e adicionar pointer novo no `MEMORY.md`.

- [ ] **Step 6: README status + commit final**

No `README.md`, trocar a seção Status por: instalado e operacional; spec e plano em `docs/superpowers/`.

```bash
git add -A && git commit -m "docs: status operacional e stub de cutover"
git push
```

---

## Self-Review (executada na escrita do plano)

- **Cobertura da spec:** extract/validate/lint/compile-index/hot-check/fold = Tasks 4-11; hooks = 12-13; skills = 14; instalação/cutover/config = 1 e 15; debounce 30s = 13; `.raw` imutável e manifest = 6; log append-topo com estado = 7; ledger warning = 8; teste cp1252 = constraint global; página 251KB = teste sintético na Task 5 e smoke real na 15. Fora de escopo da spec mantido fora.
- **Placeholders:** nenhum TBD; todos os passos têm código. Único código deliberadamente provisório: `recompile-index.py` stub na Task 12, substituído na 13.
- **Consistência de tipos:** `Report(errors, warnings, ok)` usado em 6-8 e no CLI; `Section(level,title,start,end,tokens)` em 4-5; `Finding(severity,path,message)` em 10; `FoldPlan(fm_block,keep,archive)` em 11; `update_log_state` definida em 7 e consumida em 11. `check_schema` definida em 6, consumida em 10.
- **Correção aplicada inline:** um resto de rascunho em `split()` (Task 3) foi removido do bloco de código na revisão.
