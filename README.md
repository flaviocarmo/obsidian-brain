# obsidian-brain

A [Claude Code](https://claude.com/claude-code) plugin that turns an [Obsidian](https://obsidian.md) vault into a reliable second brain: direct writes guarded by validation hooks, retrieval powered by [basic-memory](https://github.com/basicmachines-co/basic-memory), and a single dependency-free CLI for everything deterministic. Built Windows-first, works everywhere Python runs.

**[English](#english) · [Português](#português-brasil)**

---

## English

### Why

LLM-maintained knowledge bases fail in predictable ways: the hot-context file grows past its budget, compiled indexes get edited by hand, chronological ledger pages receive blind appends, and huge pages get loaded whole into context when only one section matters. obsidian-brain moves that discipline out of prompt prose and into tested code, then lets the model do only what models are good at: judgment.

- **Write directly, validate immediately.** Claude writes with its normal Write/Edit tools. A `PostToolUse` hook validates every write inside the vault and feeds violations straight back to the model, which fixes them in the next turn. No staging area, no transaction engine, safe for vaults synced by Dropbox/OneDrive/Syncthing because nothing ever rolls files back behind your back.
- **Section extractor for big pages.** Real vaults grow 250 KB ledger pages. `brain extract` returns a token-estimated table of contents, then just the section you ask for, fence-aware (headings inside code blocks are not headings).
- **Search stays external.** basic-memory indexes the vault locally (FTS + vector, zero LLM tokens). This plugin implements what comes after search, not search itself.
- **Everything deterministic is code with tests.** 81 pytest tests, Windows-native, cp1252-console safe, pure stdlib.

### Requirements

- Python 3.11+ (no packages needed, stdlib only)
- Claude Code with plugin and hook support
- An Obsidian vault (or any folder of Markdown with YAML frontmatter)
- Optional but recommended: [basic-memory](https://github.com/basicmachines-co/basic-memory) pointed at the vault for search; without it the query skill falls back to grep

### Install

```
claude plugin marketplace add <path-or-git-url-of-this-repo>
claude plugin install obsidian-brain@obsidian-brain-marketplace
```

On first use, Claude notices there is no vault configured and asks you where it lives, then writes `~/.claude/brain.json` for you. You can also create it yourself:

```json
{ "vault": "C:\\path\\to\\YourVault" }
```

The `BRAIN_VAULT` environment variable overrides the file when set. Start a new Claude Code session and the skills and hooks are live.

### Vault layout (data-derived taxonomy)

Structure follows the data, not note kinds (note kind already lives in frontmatter `type`):

```
YourVault/
├── .raw/          # immutable sources (the validator blocks edits to existing files)
├── wiki/
│   ├── hot.md     # hot context, 500-word budget, always overwritten whole
│   ├── index.md   # compiled catalog, never hand-edited (a hook recompiles it)
│   ├── log.md     # append-only log, newest entry on top
│   ├── journal/   # dated session pages (time series)
│   ├── contracts/ # living client/contract pages treated as chronological ledgers
│   ├── domains/   # technical knowledge clustered by your real domains (subfolders)
│   ├── people/
│   ├── meta/      # lint reports
│   └── folds/     # archives (old log entries, old hot caches)
```

Every wiki page carries frontmatter: `type`, `title`, `created`, `updated`, `tags`, `status` (with a small canonical vocabulary), no nested objects.

### Use it through skills (inside Claude Code)

| Say | Skill | What happens |
|---|---|---|
| "query the vault: ..." | `query` | hot.md, then basic-memory search, then `extract --toc`/`--heading` on big pages; answers cite `[[Page#Heading]]` |
| `/save` or "save this to the vault" | `save` | picks note type and folder, updates instead of duplicating, inserts ledger records in chronological position |
| "ingest file.md" | `ingest` | source goes to `.raw/`, becomes atomic pages with provenance |
| "lint the wiki" | `lint` | runs the deterministic linter, interprets, proposes fixes (applying is a separate approval) |
| "fold the log" | `fold` | dry-run of the log rollup into monthly archives; `--apply` only after approval |
| "update hot cache" | `hot-cache` | archives the current hot.md, rewrites it whole within the 500-word budget |

### Use it from any shell (CLI)

```
python <plugin>/scripts/brain.py extract "Some Big Page" --toc
python <plugin>/scripts/brain.py extract "Some Big Page" --heading "Invoices 2026"
python <plugin>/scripts/brain.py validate path/to/page.md
python <plugin>/scripts/brain.py lint --json
python <plugin>/scripts/brain.py compile-index
python <plugin>/scripts/brain.py hot-check
python <plugin>/scripts/brain.py fold            # dry-run; add --apply to execute
```

Exit codes: 0 ok, 1 violation found, 2 usage or config error.

### What the hooks enforce

- Frontmatter present and on schema for every wiki page
- `hot.md` at 500 words or less, no "previous" sections
- `index.md` untouchable by hand (and recompiled automatically after writes, 30 s debounce)
- `log.md` accepts new entries at the top only; editing history is blocked
- `.raw/` files are immutable once created
- Ledger pages out of chronological order get a warning
- A hook failure never breaks the session: worst case degrades to a plain write

### Development

```
python -m pytest -v      # 81 tests, Windows-native
```

Design spec and implementation plan live in [`docs/superpowers/`](docs/superpowers/).

---

## Português (Brasil)

### Por quê

Bases de conhecimento mantidas por LLM falham de formas previsíveis: o arquivo de contexto quente estoura o orçamento, o índice compilado é editado à mão, páginas de ledger cronológico recebem appends cegos e páginas enormes entram inteiras no contexto quando só uma seção importa. O obsidian-brain tira essa disciplina da prosa de prompt e a coloca em código testado, deixando para o modelo só o que modelo faz bem: julgamento.

- **Escreve direto, valida na hora.** O Claude escreve com Write/Edit normais. Um hook `PostToolUse` valida cada escrita no vault e devolve a violação ao modelo, que corrige no turno seguinte. Sem staging, sem motor de transação, seguro para vault em Dropbox/OneDrive/Syncthing porque nada faz rollback de arquivo pelas suas costas.
- **Extrator de seção para páginas grandes.** Vault real cria páginas de ledger de 250 KB. `brain extract` devolve um sumário com estimativa de tokens por seção e depois só a seção pedida, ciente de code fences (heading dentro de bloco de código não é heading).
- **Busca fica de fora.** O basic-memory indexa o vault localmente (FTS + vetorial, zero tokens de LLM). Este plugin implementa o que vem depois da busca, não a busca.
- **Tudo que é determinístico é código com teste.** 81 testes pytest, Windows nativo, seguro em console cp1252, stdlib pura.

### Requisitos

- Python 3.11+ (sem pacotes, só stdlib)
- Claude Code com suporte a plugins e hooks
- Um vault Obsidian (ou qualquer pasta de Markdown com frontmatter YAML)
- Opcional e recomendado: [basic-memory](https://github.com/basicmachines-co/basic-memory) apontado para o vault; sem ele a skill de query cai para grep

### Instalação

```
claude plugin marketplace add <path-ou-url-git-deste-repo>
claude plugin install obsidian-brain@obsidian-brain-marketplace
```

No primeiro uso, o Claude percebe que não há vault configurado, pergunta onde ele fica e grava o `~/.claude/brain.json` por você. Também dá para criar à mão:

```json
{ "vault": "C:\\caminho\\para\\SeuVault" }
```

A variável de ambiente `BRAIN_VAULT` tem precedência quando definida. Abra uma sessão nova do Claude Code e as skills e hooks estarão ativos.

### Layout do vault (taxonomia derivada do dado)

O mesmo da seção em inglês: `.raw/` imutável; `wiki/` com `hot.md` (500 palavras, sobrescrito inteiro), `index.md` (compilado, nunca à mão), `log.md` (append no topo), `journal/` (sessões datadas), `contracts/` (ledgers cronológicos de cliente/contrato), `domains/` (conhecimento por domínio real, em subpastas) e `people/`. A estrutura segue o dado; o tipo da nota já vive no frontmatter `type/title/created/updated/tags/status`, sem objetos aninhados.

### Uso por skills (dentro do Claude Code)

| Diga | Skill | O que acontece |
|---|---|---|
| "query o vault: ..." | `query` | hot.md, busca basic-memory, `extract --toc`/`--heading` em página grande; resposta cita `[[Página#Heading]]` |
| `/save` ou "salve no vault" | `save` | decide tipo e pasta, atualiza em vez de duplicar, insere registro de ledger na posição cronológica |
| "ingest arquivo.md" | `ingest` | source vai para `.raw/` e vira páginas atômicas com proveniência |
| "lint the wiki" | `lint` | roda o linter determinístico, interpreta, propõe fixes (aplicar é aprovação separada) |
| "fold the log" | `fold` | dry-run do rollup do log em arquivos mensais; `--apply` só com aprovação |
| "update hot cache" | `hot-cache` | arquiva o hot.md atual e o reescreve inteiro dentro das 500 palavras |

### Uso por CLI (qualquer shell)

Os mesmos comandos da seção em inglês: `extract`, `validate`, `lint`, `compile-index`, `hot-check`, `fold`. Exit codes: 0 ok, 1 violação, 2 erro de uso ou config.

### O que os hooks garantem

Frontmatter no schema em toda página; `hot.md` dentro do contrato de 500 palavras; `index.md` intocável à mão (e recompilado sozinho, debounce de 30 s); `log.md` só aceita entrada nova no topo; `.raw/` imutável; ledger fora de ordem cronológica gera aviso. Falha de hook nunca quebra a sessão: o pior caso degrada para uma escrita simples.

### Desenvolvimento

```
python -m pytest -v      # 81 testes, Windows nativo
```

Spec de design e plano de implementação em [`docs/superpowers/`](docs/superpowers/).

---

## Credits / Créditos

Inspired by / Inspirado pelo [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian), by [AgriciDaniel](https://github.com/AgriciDaniel) (MIT).
